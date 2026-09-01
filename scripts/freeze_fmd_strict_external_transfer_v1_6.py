from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nostos.validation.fmd_strict_external_transfer import (
    TRANSFER_LOCK_SCHEMA,
    load_transfer_inputs,
    verify_transfer_selection,
)
from nostos.validation.fmd_widefield_profile import verify_widefield_archive
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    sha256_file,
    write_json,
)


IMPLEMENTATION_PATHS = (
    "pyproject.toml",
    "configs/fmd_strict_external_transfer_v1_6.locked.json",
    "docs/NOSTOS0_FMD_STRICT_EXTERNAL_TRANSFER_V1_6_PROTOCOL.md",
    "src/nostos/validation/fmd_strict_external_transfer.py",
    "scripts/freeze_fmd_strict_external_transfer_v1_6.py",
    "scripts/run_fmd_strict_external_transfer_v1_6.py",
    "scripts/audit_fmd_strict_external_transfer_v1_6.py",
    "tests/test_fmd_strict_external_transfer.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the two-source FMD v1.6 strict external transfer."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--transfer-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config_path = args.config.resolve()
    transfer_output = args.transfer_output.resolve()
    audit_output = args.audit_output.resolve()
    output_path = args.output.resolve()
    for forbidden in (transfer_output, audit_output, output_path):
        if forbidden.exists():
            raise FileExistsError(
                f"Refusing to freeze after an external-transfer artifact exists: {forbidden}"
            )
    config, _development, base, strict, _measurement, refs = load_transfer_inputs(
        project_root, config_path
    )
    verify_transfer_selection(config)
    archive_receipts = []
    for source in config["sources"]:
        _, identity = verify_widefield_archive(
            args.data.resolve(), {"source": source["source"]}
        )
        archive_receipts.append(
            {
                "dataset_key": source["dataset_key"],
                "figshare_file_id": source["figshare_file_id"],
                "archive_name": source["source"]["archive_name"],
                "bytes": identity["bytes"],
                "md5": identity["md5"],
                "sha256": identity["sha256"],
                "confirmation_fields": source["confirmation_fields"],
                "realization_indices": source["realization_indices"],
            }
        )

    paths = [project_root / path for path in IMPLEMENTATION_PATHS]
    paths.extend(refs.values())
    unique = sorted({path.resolve() for path in paths}, key=str)
    artifacts = []
    for path in unique:
        if not path.is_file():
            raise FileNotFoundError(f"Cannot freeze missing transfer artifact: {path}")
        artifacts.append(
            {
                "path": path.relative_to(project_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "schema_version": TRANSFER_LOCK_SCHEMA,
        "protocol_id": config["protocol_id"],
        "locked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "confirmation_status_at_lock": "pixels_not_decoded_for_measurement_analysis",
        "transfer_output_absent_at_lock": str(transfer_output),
        "audit_output_absent_at_lock": str(audit_output),
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "base_profile_content_sha256": base["content_sha256"],
        "strict_profile_content_sha256": strict["content_sha256"],
        "supported_cells": [
            {"key": cell["key"], "values": cell["values"]}
            for cell in strict["supported_cells"]
        ],
        "sources": archive_receipts,
        "source_gates": config["source_gates"],
        "combined_gates": config["combined_gates"],
        "artifacts": artifacts,
    }
    payload["content_sha256"] = canonical_sha256(payload)
    write_json(output_path, payload)
    print(
        json.dumps(
            {
                "status": "external_transfer_locked",
                "lock": str(output_path),
                "content_sha256": payload["content_sha256"],
                "artifact_count": len(artifacts),
                "sources": payload["sources"],
                "supported_cells": payload["supported_cells"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
