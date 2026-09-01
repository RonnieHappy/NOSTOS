from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.conditional_support_profile import (
    compile_conditional_support_profile,
)
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    read_jsonl,
    sha256_file,
    verify_profile,
    write_json,
    write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile the post-v1.3 FMD hierarchical conditional-support profile."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/fmd_widefield_conditional_support_v1_4.locked.json"),
    )
    parser.add_argument("--base-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config_path = args.config.resolve()
    base_profile_path = args.base_profile.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite conditional development: {output}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_profile = json.loads(base_profile_path.read_text(encoding="utf-8"))
    verify_profile(base_profile)
    if sha256_file(base_profile_path) != config["base_profile"]["file_sha256"]:
        raise ValueError("Base-profile file hash differs from the v1.4 lock.")
    if base_profile["content_sha256"] != config["base_profile"]["content_sha256"]:
        raise ValueError("Base-profile content hash differs from the v1.4 lock.")

    rows = []
    source_rows = []
    for source in config["development_sources"]:
        path = project_root / str(source["path"])
        if sha256_file(path) != str(source["sha256"]):
            raise ValueError(f"Conditional-development source hash mismatch: {path}")
        loaded = read_jsonl(path)
        rows.extend(loaded)
        source_rows.append(
            {
                "path": str(source["path"]),
                "sha256": str(source["sha256"]),
                "rows": len(loaded),
                "original_role": str(source["original_role"]),
            }
        )
    case_ids = [str(row["case_id"]) for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Post-v1.3 conditional-development rows contain duplicate cases.")
    source_receipt = {
        "source_rows": source_rows,
        "combined_rows": len(rows),
        "combined_case_set_sha256": canonical_sha256(sorted(case_ids)),
        "explicit_role": "post_v1_3_opened_development",
    }
    profile, audit, scored = compile_conditional_support_profile(
        rows,
        config=config,
        base_profile=base_profile,
        source_receipt=source_receipt,
    )
    output.mkdir(parents=True)
    profile_path = output / "conditional_support_profile.json"
    audit_path = output / "development_audit.json"
    scored_path = output / "development_scored.jsonl"
    write_json(profile_path, profile)
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    receipt = {
        "schema_version": "nostos-fmd-widefield-conditional-development/1.0",
        "status": profile["status"],
        "protocol_id": config["protocol_id"],
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "base_profile_file_sha256": sha256_file(base_profile_path),
        "base_profile_content_sha256": base_profile["content_sha256"],
        "profile_file_sha256": sha256_file(profile_path),
        "profile_content_sha256": profile["content_sha256"],
        "audit_file_sha256": sha256_file(audit_path),
        "scored_rows_sha256": sha256_file(scored_path),
        "development_sources": source_rows,
        "development_operating_point": profile["development_operating_point"],
        "supported_cells": [
            {"values": cell["values"], "key": cell["key"]}
            for cell in profile["supported_cells"]
        ],
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    receipt_path = output / "development_receipt.json"
    write_json(receipt_path, receipt)
    print(
        json.dumps(
            {
                "status": profile["status"],
                "profile": str(profile_path),
                "profile_file_sha256": sha256_file(profile_path),
                "audit": str(audit_path),
                "receipt": str(receipt_path),
                "supported_cells": len(profile["supported_cells"]),
                "unsupported_cells": len(profile["unsupported_cells"]),
                "development_operating_point": profile["development_operating_point"],
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
