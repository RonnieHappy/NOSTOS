"""Seal the failed NOSTOS BioSR v5 calibration and its diagnostic evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "manifests"
    / "paired_acquisition_support_threshold_failure_receipt_v5.json"
)
CALIBRATION = (
    PROJECT_ROOT
    / "outputs"
    / "nostos0-biosr-threshold-calibration-v5"
    / "threshold_calibration.json"
)
DIAGNOSTIC = (
    PROJECT_ROOT
    / "outputs"
    / "nostos0-biosr-threshold-calibration-v5"
    / "failure_diagnostics.json"
)
THRESHOLD_LOCK = (
    PROJECT_ROOT
    / "manifests"
    / "paired_acquisition_support_threshold_lock.json"
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(relative: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": relative.replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    diagnostic = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    result = calibration["result"]
    if result["status"] != "fail":
        raise ValueError("Calibration result is not a failure.")
    if result["operating_point"]["status"] != "no_operating_point":
        raise ValueError("A full-contract operating point unexpectedly exists.")
    if calibration.get("confirmation_archives_accessed") is not False:
        raise ValueError("Calibration does not record sealed confirmation data.")
    if diagnostic.get("confirmation_archives_accessed") is not False:
        raise ValueError("Diagnostic does not record sealed confirmation data.")
    if diagnostic["status"] != "diagnostic_only_v5_remains_failed":
        raise ValueError("Diagnostic status is not the expected v5 failure state.")
    if THRESHOLD_LOCK.exists():
        raise FileExistsError(
            "A passing threshold lock exists; refusing to seal an inconsistent failure receipt."
        )

    relative_files = [
        "configs/paired_acquisition_support_v5.locked.json",
        "configs/biosr_widefield_measurement_profile_v1.locked.json",
        "manifests/paired_acquisition_support_score_formula_lock_v2.json",
        "manifests/paired_acquisition_support_profile_lineage_amendment_lock.json",
        "manifests/biosr_small_pilot_v5_selection_lock.json",
        "outputs/nostos0-biosr-ccp-threshold-calibration-v5/archive_receipt.json",
        "outputs/nostos0-biosr-ccp-threshold-calibration-v5/endpoint_cases.jsonl",
        "outputs/nostos0-biosr-ccp-threshold-calibration-v5/pair_index.json",
        "outputs/nostos0-biosr-er-threshold-calibration-v5/archive_receipt.json",
        "outputs/nostos0-biosr-er-threshold-calibration-v5/endpoint_cases.jsonl",
        "outputs/nostos0-biosr-er-threshold-calibration-v5/pair_index.json",
        "outputs/nostos0-biosr-threshold-calibration-v5/threshold_calibration.json",
        "outputs/nostos0-biosr-threshold-calibration-v5/THRESHOLD_VERDICT.md",
        "outputs/nostos0-biosr-threshold-calibration-v5/structure_endpoint_operating_points.csv",
        "outputs/nostos0-biosr-threshold-calibration-v5/failure_diagnostics.json",
        "outputs/nostos0-biosr-threshold-calibration-v5/structure_endpoint_best_points.csv",
        "outputs/nostos0-biosr-threshold-calibration-v5/FAILURE_DIAGNOSTIC.md",
        "src/nostos/validation/threshold_calibration.py",
        "src/nostos/validation/failure_diagnostics.py",
        "scripts/calibrate_biosr_threshold_v5.py",
        "scripts/audit_biosr_threshold_failure_v5.py",
        "scripts/build_biosr_threshold_failure_receipt_v5.py",
        "tests/test_threshold_calibration.py",
        "tests/test_failure_diagnostics.py",
        "tests/test_biosr_lock_lineage.py",
        "docs/NOSTOS0_THRESHOLD_CALIBRATION_V5_FAILURE_AUDIT.md",
        "pyproject.toml",
        "uv.lock",
    ]
    failures = diagnostic["irreducible_combination_failures"]
    payload = {
        "schema_version": "nostos-paired-acquisition-threshold-failure-receipt/1.0",
        "created_at_utc": _utc_now(),
        "status": "threshold_calibration_failed_no_operating_point",
        "protocol_version": "nostos-paired-acquisition-support/5.0",
        "scope": {
            "reference_fields": result["reference_fields"],
            "paired_acquisitions": result["paired_acquisitions"],
            "claim_endpoint_rows": result["endpoint_cases"],
            "reference_eligible_claim_cases": result["reference_eligible_cases"],
            "structures": ["CCPs", "ER"],
        },
        "prospective_result": {
            "operating_point_selected": result["gates"][
                "operating_point_selected"
            ],
            "candidate_thresholds": result["operating_point"][
                "candidate_thresholds"
            ],
            "bootstrap_candidates_evaluated": result["operating_point"][
                "bootstrap_candidates_evaluated"
            ],
            "full_contract_aurc": result["aurc"]["full_contract"],
            "always_emit_aurc": result["aurc"]["always_emit"],
            "conventional_acquisition_qc_aurc": result["aurc"][
                "conventional_acquisition_qc"
            ],
            "aurc_reduction_fraction_vs_always_emit": result["aurc"][
                "reduction_fraction_vs_always_emit"
            ],
            "aurc_gate_passed": result["gates"][
                "minimum_aurc_reduction_fraction"
            ],
        },
        "failure_diagnosis": {
            "irreducible_structure_endpoint_failures": failures,
            "primary_score_scale_conflict": {
                "structure": "ER",
                "endpoint_a": "tensor_coherence",
                "threshold_a": 0.2999141693723138,
                "endpoint_b": "tensor_orientation",
                "threshold_b": 0.9964578203269273,
            },
            "interpretation": "The v5 score ranks error overall but cannot support one commensurate cutoff; ER vertical variogram range also fails independently at the frozen coverage floor.",
        },
        "failure_reasons": [
            "No global threshold met every frozen aggregate and structure-endpoint risk/coverage constraint.",
            "ER vertical variogram range retained 17 invalid cases among 158 at its best diagnostic point, risk 0.10759493670886076.",
            "Endpoint families require non-commensurate raw-score cutoffs.",
            "Conventional acquisition QC also had no operating point under the identical selector.",
        ],
        "threshold_lock_written": False,
        "confirmation_access_authorized": False,
        "confirmation_archives_accessed": False,
        "next_gate": "Prospectively freeze a new v6 endpoint-family-calibrated validity contract and rotation-invariant variogram definition before any confirmation access.",
        "files": [_artifact(relative) for relative in relative_files],
        "verification": {
            "focused_test_command": "uv run --frozen pytest -q tests/test_failure_diagnostics.py tests/test_threshold_calibration.py tests/test_biosr_lock_lineage.py",
            "focused_test_result": "10 passed, 0 failed",
            "full_test_command": "uv run --frozen pytest -q",
            "full_test_result": "224 passed, 4 skipped, 12 dependency deprecation warnings",
            "full_test_exit_code": 0,
            "compile_command": "uv run --frozen python -m compileall -q src scripts",
            "compile_exit_code": 0,
            "passing_threshold_lock_state": "absent",
        },
        "claim_boundary": "This receipt records a failed research validation gate. It does not establish an operating threshold, confirmation, acquisition-family generalization, biological truth, diagnosis, clinical validity, intraoperative utility or submission readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_artifact(str(args.output.relative_to(PROJECT_ROOT))), indent=2))


if __name__ == "__main__":
    main()
