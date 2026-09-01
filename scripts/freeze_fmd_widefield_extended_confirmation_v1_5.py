from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nostos.validation.fmd_widefield_extended_confirmation import (
    EXTENDED_LOCK_SCHEMA,
    load_extension_inputs,
    verify_extension_selection,
)
from nostos.validation.fmd_widefield_profile import verify_widefield_archive
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    sha256_file,
    write_json,
)


IMPLEMENTATION_PATHS = (
    "pyproject.toml",
    "configs/fmd_widefield_extended_confirmation_v1_5.locked.json",
    "docs/NOSTOS0_FMD_WIDEFIELD_EXTENDED_CONFIRMATION_V1_5_PROTOCOL.md",
    "src/nostos/validation/fmd_widefield_extended_confirmation.py",
    "scripts/freeze_fmd_widefield_extended_confirmation_v1_5.py",
    "scripts/run_fmd_widefield_extended_confirmation_v1_5.py",
    "scripts/audit_fmd_widefield_extended_confirmation_v1_5.py",
    "tests/test_fmd_widefield_extended_confirmation.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the no-refit seven-field FMD widefield v1.5 extension."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--extension-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config_path = args.config.resolve()
    extension_output = args.extension_output.resolve()
    audit_output = args.audit_output.resolve()
    output_path = args.output.resolve()
    for forbidden in (extension_output, audit_output, output_path):
        if forbidden.exists():
            raise FileExistsError(
                f"Refusing to freeze after an extension artifact exists: {forbidden}"
            )
    (
        config,
        _base_config,
        base_profile,
        conditional_profile,
        _measurement,
        refs,
    ) = load_extension_inputs(project_root, config_path)
    verify_extension_selection(config)
    _, archive_identity = verify_widefield_archive(args.data.resolve(), config)

    paths = [project_root / path for path in IMPLEMENTATION_PATHS]
    paths.extend(refs.values())
    unique = sorted({path.resolve() for path in paths}, key=str)
    artifacts = []
    for path in unique:
        if not path.is_file():
            raise FileNotFoundError(f"Cannot freeze missing v1.5 artifact: {path}")
        artifacts.append(
            {
                "path": path.relative_to(project_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "schema_version": EXTENDED_LOCK_SCHEMA,
        "protocol_id": config["protocol_id"],
        "locked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "confirmation_status_at_lock": "pixels_not_decoded_for_measurement_analysis",
        "extension_output_absent_at_lock": str(extension_output),
        "audit_output_absent_at_lock": str(audit_output),
        "archive_sha256": archive_identity["sha256"],
        "archive_md5": archive_identity["md5"],
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "base_profile_file_sha256": sha256_file(refs["base_profile"]),
        "base_profile_content_sha256": base_profile["content_sha256"],
        "conditional_profile_file_sha256": sha256_file(refs["conditional_profile"]),
        "conditional_profile_content_sha256": conditional_profile["content_sha256"],
        "previously_opened_fields": [
            int(value) for value in config["selection"]["previously_opened_fields"]
        ],
        "extension_fields": [
            int(value) for value in config["selection"]["confirmation_fields"]
        ],
        "extension_realization_indices": {
            str(field): config["selection"]["realization_indices"][str(field)]
            for field in config["selection"]["confirmation_fields"]
        },
        "supported_cells": [
            {"key": cell["key"], "values": cell["values"]}
            for cell in conditional_profile["supported_cells"]
        ],
        "extension_gates": config["extension_gates"],
        "cumulative_gates": config["cumulative_gates"],
        "artifacts": artifacts,
    }
    payload["content_sha256"] = canonical_sha256(payload)
    write_json(output_path, payload)
    print(
        json.dumps(
            {
                "status": "extended_confirmation_locked",
                "lock": str(output_path),
                "content_sha256": payload["content_sha256"],
                "artifact_count": len(artifacts),
                "extension_fields": payload["extension_fields"],
                "supported_cells": payload["supported_cells"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
