"""Freeze the complete NOSTOS BioSR v6 initial-confirmation package."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nostos.core.measurement_profile import MeasurementProfile
from nostos.validation.paired_acquisition_support import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "manifests" / "paired_acquisition_support_v6_confirmation_lock.json"
)
CONFIG = PROJECT_ROOT / "configs" / "paired_acquisition_support_v6.locked.json"
PROFILE = (
    PROJECT_ROOT / "configs" / "biosr_widefield_measurement_profile_v2.locked.json"
)
DEVELOPMENT_AUDIT = (
    PROJECT_ROOT
    / "outputs"
    / "nostos0-biosr-v6-family-threshold-development"
    / "family_threshold_calibration.json"
)
IMPLEMENTATION_FILES = (
    PROJECT_ROOT / "scripts" / "run_biosr_paired_support_v6.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "paired_acquisition_support.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "selective_policy_v6.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "confirmation_v6.py",
    PROJECT_ROOT / "src" / "nostos" / "features" / "spatial_fft.py",
    PROJECT_ROOT / "src" / "nostos" / "features" / "response_modules.py",
    PROJECT_ROOT / "src" / "nostos" / "core" / "qc.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "metrics.py",
    PROJECT_ROOT / "pyproject.toml",
    PROJECT_ROOT / "uv.lock",
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _implementation_receipt() -> dict[str, Any]:
    files = [_artifact(path) for path in IMPLEMENTATION_FILES]
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite the v6 confirmation lock: {args.output}")

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    development = json.loads(DEVELOPMENT_AUDIT.read_text(encoding="utf-8"))
    profile = MeasurementProfile.from_path(PROFILE)
    if config["protocol_version"] != "nostos-paired-acquisition-support/6.0":
        raise ValueError("Unexpected v6 protocol version.")
    if development["status"] != "development_pass_pending_implementation_freeze":
        raise ValueError("v6 development gate has not passed.")
    if development["policies"]["full_contract"]["status"] != "pass":
        raise ValueError("The full-contract family policy did not pass development.")
    expected_thresholds = {
        family: result["threshold"]
        for family, result in development["policies"]["full_contract"][
            "families"
        ].items()
    }
    if config["policy_thresholds"]["full_contract"] != expected_thresholds:
        raise ValueError("Frozen thresholds differ from the development audit.")
    if profile.status != "threshold_calibrated":
        raise ValueError("BioSR v2 profile is not threshold calibrated.")
    if set(profile.eligible_endpoints) != {
        endpoint
        for endpoints in config["endpoint_families"].values()
        for endpoint in endpoints
    }:
        raise ValueError("Profile and v6 endpoint families disagree.")
    if set(config["initial_confirmation"]["structures"]) != {
        "Microtubules",
        "F-actin_linear",
        "F-actin_nonlinear",
    }:
        raise ValueError("Confirmation structures differ from the frozen program.")
    if int(config["initial_confirmation"]["fields_per_structure"]) != 8:
        raise ValueError("Initial confirmation tranche must remain eight fields per structure.")

    implementation = _implementation_receipt()
    supporting_paths = [
        PROJECT_ROOT / "manifests" / "biosr_paired_acquisition_sources.json",
        PROJECT_ROOT
        / "manifests"
        / "paired_acquisition_support_threshold_failure_receipt_v5.json",
        PROJECT_ROOT
        / "manifests"
        / "paired_acquisition_support_v5_comparator_semantics_addendum_receipt.json",
        PROJECT_ROOT / "docs" / "NOSTOS0_V5_COMPARATOR_SEMANTICS_ADDENDUM.md",
        PROJECT_ROOT / "configs" / "paired_acquisition_support_v6_development.json",
        PROJECT_ROOT
        / "outputs"
        / "nostos0-biosr-v6-family-calibration-development"
        / "candidate_benchmark.json",
        DEVELOPMENT_AUDIT,
        DEVELOPMENT_AUDIT.parent / "family_thresholds_candidate.json",
        DEVELOPMENT_AUDIT.parent / "family_policy_comparison.csv",
        DEVELOPMENT_AUDIT.parent / "DEVELOPMENT_VERDICT.md",
        CONFIG,
        PROFILE,
        PROJECT_ROOT / "src" / "nostos" / "features" / "intrinsic_variogram.py",
        PROJECT_ROOT / "src" / "nostos" / "validation" / "family_risk_calibration.py",
        PROJECT_ROOT / "scripts" / "develop_biosr_v6_family_calibration.py",
        PROJECT_ROOT / "scripts" / "calibrate_biosr_v6_family_thresholds.py",
        PROJECT_ROOT / "scripts" / "audit_biosr_v6_confirmation.py",
        Path(__file__).resolve(),
        PROJECT_ROOT / "tests" / "test_intrinsic_variogram.py",
        PROJECT_ROOT / "tests" / "test_family_risk_calibration.py",
        PROJECT_ROOT / "tests" / "test_selective_policy_v6.py",
        PROJECT_ROOT / "tests" / "test_confirmation_v6.py",
        PROJECT_ROOT / "tests" / "test_biosr_profile_v2.py",
        PROJECT_ROOT / "tests" / "test_biosr_v6_freeze_contract.py",
    ]
    unique: dict[str, dict[str, Any]] = {
        item["path"]: item
        for item in [*implementation["files"], *[_artifact(path) for path in supporting_paths]]
    }
    payload = {
        "schema_version": "nostos-paired-acquisition-v6-confirmation-lock/1.0",
        "locked_at_utc": _utc_now(),
        "status": "locked_before_any_v6_confirmation_archive_download_or_access",
        "protocol_version": config["protocol_version"],
        "implementation_sha256": implementation["sha256"],
        "config": _artifact(CONFIG),
        "profile": _artifact(PROFILE),
        "development_gate": {
            "status": development["status"],
            "reference_fields": development["scope"]["reference_fields"],
            "paired_acquisitions": development["scope"]["paired_acquisitions"],
            "full_contract": development["policies"]["full_contract"]["overall"],
            "thresholds": expected_thresholds,
            "structure_specific_thresholds": False,
        },
        "confirmation": {
            "structures": config["initial_confirmation"]["structures"],
            "fields_per_structure": config["initial_confirmation"][
                "fields_per_structure"
            ],
            "field_selection_rule": config["initial_confirmation"][
                "field_selection_rule"
            ],
            "threshold_refitting_permitted": False,
            "endpoint_addition_or_removal_permitted": False,
            "archive_integrity_source": "manifests/biosr_paired_acquisition_sources.json locked before development",
        },
        "access_state": {
            "CCPs_and_ER": "development_closed",
            "Microtubules": "sealed_not_downloaded_not_listed_not_decoded_before_this_lock",
            "F_actin_linear": "sealed_not_downloaded_not_listed_not_decoded_before_this_lock",
            "F_actin_nonlinear": "sealed_not_downloaded_not_listed_not_decoded_before_this_lock",
            "authorized_after_lock": "download and integrity verification of all three archives; index all fields for hash-only selection; decode only the selected eight fields per structure",
        },
        "files": [unique[key] for key in sorted(unique)],
        "verification": {
            "pytest_command": "uv run --frozen pytest -q",
            "pytest_result": "242 passed, 4 skipped, 12 dependency deprecation warnings",
            "pytest_exit_code": 0,
            "compile_command": "uv run --frozen python -m compileall -q src scripts",
            "compile_exit_code": 0,
        },
        "claim_boundary": config["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_artifact(args.output), indent=2))


if __name__ == "__main__":
    main()
