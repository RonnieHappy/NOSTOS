from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nostos.validation.conditional_support_profile import verify_conditional_profile
from nostos.validation.fmd_widefield_profile import verify_widefield_archive
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    sha256_file,
    verify_profile,
    write_json,
)


IMPLEMENTATION_PATHS = (
    "pyproject.toml",
    "configs/fmd_widefield_validity_profile_v1_3.locked.json",
    "configs/fmd_widefield_conditional_support_v1_4.locked.json",
    "docs/NOSTOS0_FMD_WIDEFIELD_CONDITIONAL_SUPPORT_V1_4_PROTOCOL.md",
    "src/nostos/core/qc.py",
    "src/nostos/features/response_modules.py",
    "src/nostos/features/spatial_fft.py",
    "src/nostos/validation/paired_acquisition_support.py",
    "src/nostos/validation/fmd_validity_profile.py",
    "src/nostos/validation/fmd_widefield_profile.py",
    "src/nostos/validation/validity_profile_compiler.py",
    "src/nostos/validation/conditional_support_profile.py",
    "src/nostos/validation/fmd_widefield_conditional_run.py",
    "scripts/compile_fmd_widefield_conditional_v1_4.py",
    "scripts/run_fmd_widefield_conditional_confirmation_v1_4.py",
    "scripts/audit_fmd_widefield_conditional_v1_4.py",
    "scripts/freeze_fmd_widefield_conditional_confirmation_v1_4.py",
    "tests/test_fmd_validity_profile.py",
    "tests/test_fmd_widefield_profile.py",
    "tests/test_validity_profile_compiler.py",
    "tests/test_conditional_support_profile.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the FMD widefield v1.4 one-shot confirmation lineage."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base-profile", type=Path, required=True)
    parser.add_argument("--conditional-development", type=Path, required=True)
    parser.add_argument("--confirmation-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config_path = args.config.resolve()
    base_profile_path = args.base_profile.resolve()
    development = args.conditional_development.resolve()
    conditional_profile_path = development / "conditional_support_profile.json"
    confirmation_output = args.confirmation_output.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite v1.4 lock: {output_path}")
    if confirmation_output.exists():
        raise FileExistsError(
            f"Refusing to freeze after v1.4 confirmation output exists: {confirmation_output}"
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = json.loads(base_profile_path.read_text(encoding="utf-8"))
    conditional = json.loads(conditional_profile_path.read_text(encoding="utf-8"))
    verify_profile(base)
    verify_conditional_profile(conditional)
    if base["content_sha256"] != config["base_profile"]["content_sha256"]:
        raise ValueError("V1.4 base-profile content mismatch.")
    if conditional["config_sha256"] != canonical_sha256(config):
        raise ValueError("V1.4 conditional profile and protocol mismatch.")
    _, archive_identity = verify_widefield_archive(args.data.resolve(), config)

    evidence_paths = (
        base_profile_path,
        development / "conditional_support_profile.json",
        development / "development_audit.json",
        development / "development_scored.jsonl",
        development / "development_receipt.json",
        project_root / config["development_sources"][0]["path"],
        project_root / config["development_sources"][1]["path"],
    )
    paths = [project_root / path for path in IMPLEMENTATION_PATHS]
    paths.extend(evidence_paths)
    unique = sorted({path.resolve() for path in paths}, key=str)
    artifacts = []
    for path in unique:
        if not path.is_file():
            raise FileNotFoundError(f"Cannot freeze missing v1.4 artifact: {path}")
        artifacts.append(
            {
                "path": path.relative_to(project_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "schema_version": "nostos-fmd-widefield-conditional-confirmation-lock/1.0",
        "protocol_id": config["protocol_id"],
        "locked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "confirmation_status_at_lock": "pixels_not_decoded_for_measurement_analysis",
        "confirmation_output_absent_at_lock": str(confirmation_output),
        "archive_sha256": archive_identity["sha256"],
        "archive_md5": archive_identity["md5"],
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "base_profile_file_sha256": sha256_file(base_profile_path),
        "base_profile_content_sha256": base["content_sha256"],
        "conditional_profile_file_sha256": sha256_file(conditional_profile_path),
        "conditional_profile_content_sha256": conditional["content_sha256"],
        "development_fields": [int(value) for value in config["selection"]["development_fields"]],
        "confirmation_fields": [int(value) for value in config["selection"]["confirmation_fields"]],
        "confirmation_realization_indices": {
            str(field): config["selection"]["realization_indices"][str(field)]
            for field in config["selection"]["confirmation_fields"]
        },
        "supported_cells": [
            {"key": cell["key"], "values": cell["values"]}
            for cell in conditional["supported_cells"]
        ],
        "development_operating_point": conditional["development_operating_point"],
        "artifacts": artifacts,
    }
    payload["content_sha256"] = canonical_sha256(payload)
    write_json(output_path, payload)
    print(
        json.dumps(
            {
                "status": "confirmation_locked",
                "lock": str(output_path),
                "content_sha256": payload["content_sha256"],
                "artifact_count": len(artifacts),
                "confirmation_fields": payload["confirmation_fields"],
                "supported_cells": payload["supported_cells"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
