from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nostos.validation.fmd_widefield_profile import verify_widefield_archive
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    sha256_file,
    verify_profile,
    write_json,
)


LOCKED_IMPLEMENTATION_PATHS = (
    "pyproject.toml",
    "configs/fmd_widefield_validity_profile_v1_3.locked.json",
    "docs/NOSTOS0_FMD_WIDEFIELD_VALIDITY_PROFILE_V1_3_PROTOCOL.md",
    "src/nostos/core/qc.py",
    "src/nostos/features/response_modules.py",
    "src/nostos/features/spatial_fft.py",
    "src/nostos/validation/paired_acquisition_support.py",
    "src/nostos/validation/fmd_validity_profile.py",
    "src/nostos/validation/fmd_widefield_profile.py",
    "src/nostos/validation/validity_profile_compiler.py",
    "scripts/run_fmd_widefield_validity_profile_v1_3.py",
    "scripts/freeze_fmd_widefield_confirmation_v1_3.py",
    "tests/test_fmd_validity_profile.py",
    "tests/test_fmd_widefield_profile.py",
    "tests/test_validity_profile_compiler.py",
)


def _relative(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the executable FMD widefield one-shot confirmation lineage."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/fmd_widefield_validity_profile_v1_3.locked.json"),
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--confirmation-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    config_path = args.config.resolve()
    profile_path = args.profile.resolve()
    development = args.development.resolve()
    confirmation_output = args.confirmation_output.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite a confirmation lock: {output_path}")
    if confirmation_output.exists():
        raise FileExistsError(
            "Refusing to freeze after the declared confirmation output already exists: "
            f"{confirmation_output}"
        )

    config = json.loads(config_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    verify_profile(profile)
    if profile["config_sha256"] != canonical_sha256(config):
        raise ValueError("Profile and prospective protocol config do not match.")
    root = f"{config['source']['acquisition_modality']}_{config['source']['sample']}"
    expected_development_groups = sorted(
        f"{root}|fov{int(field)}"
        for field in config["selection"]["development_fields"]
    )
    if sorted(profile["development"]["independent_groups"]) != expected_development_groups:
        raise ValueError("Profile development groups differ from the prospective split.")

    _, archive_identity = verify_widefield_archive(args.data.resolve(), config)
    evidence_paths = (
        development / "development_pair_index.json",
        development / "development_evidence_receipt.json",
        development / "development_rows.jsonl",
        profile_path,
        profile_path.parent / "development_audit.json",
        profile_path.parent / "development_scored.jsonl",
    )
    artifact_paths = [project_root / path for path in LOCKED_IMPLEMENTATION_PATHS]
    artifact_paths.extend(evidence_paths)
    if config_path not in artifact_paths:
        artifact_paths.append(config_path)
    unique_paths = sorted({path.resolve() for path in artifact_paths}, key=str)
    artifacts = []
    for path in unique_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Cannot freeze missing artifact: {path}")
        artifacts.append(
            {
                "path": _relative(project_root, path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    payload = {
        "schema_version": "nostos-fmd-widefield-confirmation-lock/1.0",
        "protocol_id": config["protocol_id"],
        "locked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "confirmation_status_at_lock": "pixels_not_decoded_for_measurement_analysis",
        "confirmation_output_absent_at_lock": str(confirmation_output),
        "archive_sha256": archive_identity["sha256"],
        "archive_md5": archive_identity["md5"],
        "config_content_sha256": canonical_sha256(config),
        "config_file_sha256": sha256_file(config_path),
        "profile_content_sha256": profile["content_sha256"],
        "profile_file_sha256": sha256_file(profile_path),
        "development_fields": [
            int(value) for value in config["selection"]["development_fields"]
        ],
        "confirmation_fields": [
            int(value) for value in config["selection"]["confirmation_fields"]
        ],
        "confirmation_realization_indices": {
            str(field): config["selection"]["realization_indices"][str(field)]
            for field in config["selection"]["confirmation_fields"]
        },
        "profile_operating_point": profile["operating_point"]["selected"],
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
