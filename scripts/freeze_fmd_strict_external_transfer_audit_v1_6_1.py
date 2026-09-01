from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    sha256_file,
    write_json,
)


ARTIFACT_PATHS = (
    "configs/fmd_strict_external_transfer_v1_6.locked.json",
    "manifests/fmd_strict_external_transfer_v1_6_lock.json",
    "src/nostos/validation/fmd_strict_external_transfer.py",
    "src/nostos/validation/fmd_strict_external_transfer_audit_v1_6_1.py",
    "scripts/audit_fmd_strict_external_transfer_v1_6_1.py",
    "scripts/freeze_fmd_strict_external_transfer_audit_v1_6_1.py",
    "tests/test_fmd_strict_external_transfer_audit_v1_6_1.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the post-measurement v1.6.1 audit-only repair."
    )
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    rows_path = args.rows.resolve()
    audit_output = args.audit_output.resolve()
    output_path = args.output.resolve()
    if audit_output.exists() or output_path.exists():
        raise FileExistsError("Refusing to freeze after an audit output or repair lock exists.")
    if not rows_path.is_file():
        raise FileNotFoundError(rows_path)
    artifacts = []
    for relative in ARTIFACT_PATHS:
        path = project_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        artifacts.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "schema_version": "nostos-fmd-strict-external-transfer-audit-repair-lock/1.0",
        "protocol_id": "fmd-strict-external-transfer-v1-6",
        "repair_version": "v1.6.1",
        "locked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status_at_lock": "measurement_complete_original_audit_failed_no_audit_output_exists",
        "scientific_status_already_visible": "strict_external_transfer_fails_without_refitting",
        "scope": "Audit-only repair for undefined row-level interval when a source has zero accepted emissions.",
        "prohibited_changes": [
            "evidence rows",
            "source selection",
            "measurements",
            "invalidity labels",
            "profiles",
            "support cells",
            "thresholds",
            "comparators",
            "gates"
        ],
        "rows": {
            "path": rows_path.relative_to(project_root).as_posix(),
            "bytes": rows_path.stat().st_size,
            "sha256": sha256_file(rows_path),
        },
        "audit_output_absent_at_lock": str(audit_output),
        "artifacts": artifacts,
    }
    payload["content_sha256"] = canonical_sha256(payload)
    write_json(output_path, payload)
    print(json.dumps({"status": "audit_repair_locked", "lock": str(output_path), "content_sha256": payload["content_sha256"], "rows_sha256": payload["rows"]["sha256"]}, indent=2))


if __name__ == "__main__":
    main()

