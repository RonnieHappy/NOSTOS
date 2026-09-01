"""Audit the family-specific v7 tensor contract before F-actin pixel access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nostos.validation.paired_acquisition_support import sha256_file
from nostos.validation.tensor_contract_audit_v7 import (
    incremental_comparator,
    summarize_policy,
)
from nostos.validation.tensor_evidence_v7 import (
    attach_family_specific_resolution_margin,
    clustered_coherence_aurc_difference,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_ROWS = (
    ROOT
    / "outputs/nostos0-biosr-v7-tensor-distribution-development/tensor_cases.jsonl"
)
DRIFT_ROWS = (
    ROOT
    / "outputs/nostos0-biosr-v7-resolution-margin-calibration/resolution_margin_rows.jsonl"
)
CALIBRATION = (
    ROOT
    / "outputs/nostos0-biosr-v7-resolution-margin-calibration/resolution_margin_calibration.json"
)
OUTPUT = ROOT / "outputs/nostos0-biosr-v7-family-specific-evidence-audit"
COHERENCE_THRESHOLD_FRACTION = 0.8479366097649129
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 26_082_929


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    selected = calibration["selected"]
    if selected is None:
        raise ValueError("The resolution-margin calibration selected no threshold.")
    if (
        float(selected["threshold_fraction_of_endpoint_tolerance"])
        != COHERENCE_THRESHOLD_FRACTION
    ):
        raise ValueError("The declared threshold differs from the calibration receipt.")
    if calibration["scope"]["f_actin_image_members_decoded"] != 0:
        raise ValueError("F-actin was not sealed during development calibration.")

    base_rows = _read_jsonl(BASE_ROWS)
    drift_rows = _read_jsonl(DRIFT_ROWS)
    rows = attach_family_specific_resolution_margin(
        base_rows,
        drift_rows,
        coherence_threshold_fraction=COHERENCE_THRESHOLD_FRACTION,
    )
    full = summarize_policy(rows, condition="full_contract")
    qc = summarize_policy(rows, condition="conventional_acquisition_qc")
    comparator = incremental_comparator(rows)
    coherence_evidence = clustered_coherence_aurc_difference(
        rows,
        draws=BOOTSTRAP_DRAWS,
        seed=BOOTSTRAP_SEED,
    )
    bootstrap = coherence_evidence["bootstrap"]
    evidence_strength = {
        "minimum_probability_full_better": 0.95,
        "requires_positive_ci95_lower_bound": True,
        "requires_evaluation_independent_of_threshold_selection": True,
        "evaluation_independent_of_threshold_selection": False,
        "observed_invalid_reference_fields": coherence_evidence[
            "invalid_reference_fields"
        ],
        "selection_warning": "The coherence cutoff was selected from these same development outcomes. A field-cluster bootstrap conditional on that selected cutoff does not account for selection optimism and is descriptive only.",
    }
    benefit_supported = bool(
        evidence_strength["evaluation_independent_of_threshold_selection"]
        and bootstrap["probability_full_better"] is not None
        and bootstrap["probability_full_better"]
        >= evidence_strength["minimum_probability_full_better"]
        and bootstrap["ci95"][0] is not None
        and bootstrap["ci95"][0] > 0
    )
    safety_passes = bool(
        full["coverage"] >= 0.80
        and full["risk"] is not None
        and full["risk"] <= 0.10
        and full["cluster_bootstrap_risk_upper95"] is not None
        and full["cluster_bootstrap_risk_upper95"] <= 0.15
        and all(
            item["coverage"] >= 0.70
            and item["risk"] is not None
            and item["risk"] <= 0.10
            and item["cluster_bootstrap_risk_upper95"] is not None
            and item["cluster_bootstrap_risk_upper95"] <= 0.15
            for item in full["combinations"]
        )
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    governed_rows = OUTPUT / "family_specific_tensor_cases.jsonl"
    with governed_rows.open("w", encoding="utf-8") as stream:
        for row in sorted(rows, key=lambda item: str(item["case_id"])):
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload = {
        "schema_version": "nostos-biosr-v7-family-specific-evidence-audit/1.0",
        "status": (
            "safety_supported_but_incremental_benefit_not_established"
            if safety_passes and not benefit_supported
            else (
                "safety_and_incremental_benefit_supported"
                if safety_passes and benefit_supported
                else "development_safety_failed_do_not_freeze"
            )
        ),
        "family_specific_contract": {
            "tensor_coherence": {
                "strong_resolution_margin_governs": True,
                "sigma_effective_input_pixels": 2.0,
                "threshold_fraction_of_endpoint_tolerance": COHERENCE_THRESHOLD_FRACTION,
                "threshold_absolute_coherence": COHERENCE_THRESHOLD_FRACTION * 0.15,
            },
            "tensor_orientation_distribution": {
                "strong_resolution_margin_governs": False,
                "reason": "Development risk-coverage discrimination was negligible; retaining the component would add rejection without supported benefit.",
            },
        },
        "safety_gate": {
            "passes": safety_passes,
            "full_contract": full,
            "conventional_acquisition_qc": qc,
        },
        "incremental_comparator_operating_point": comparator,
        "coherence_risk_coverage_evidence": coherence_evidence,
        "evidence_strength_gate": {
            **evidence_strength,
            "passes": benefit_supported,
            "decision": (
                "development_supports_incremental-benefit claim"
                if benefit_supported
                else "do not claim incremental benefit from development; require untouched F-actin confirmation"
            ),
        },
        "freeze_decision": {
            "eligible_to_freeze_measurement_safety_contract": safety_passes,
            "eligible_to_freeze_incremental_benefit_claim": benefit_supported,
            "rationale": "A safety-valid estimator may proceed to untouched confirmation even when sparse development failures cannot establish contract superiority. The confirmation lock must keep those claims separate.",
        },
        "scope": {
            "structures": sorted({str(row["structure"]) for row in rows}),
            "reference_fields": len(
                {
                    (str(row["structure"]), str(row["reference_group_id"]))
                    for row in rows
                }
            ),
            "endpoint_rows": len(rows),
            "f_actin_image_members_decoded": 0,
            "f_actin_endpoint_outcomes_computed": 0,
        },
        "lineage": {
            "base_rows_sha256": sha256_file(BASE_ROWS),
            "resolution_margin_rows_sha256": sha256_file(DRIFT_ROWS),
            "calibration_receipt_sha256": sha256_file(CALIBRATION),
            "implementation_sha256": sha256_file(
                ROOT / "src/nostos/validation/tensor_evidence_v7.py"
            ),
            "runner_sha256": sha256_file(Path(__file__)),
        },
        "artifacts": {
            "family_specific_tensor_cases": {
                "path": str(governed_rows.relative_to(ROOT)).replace("\\", "/"),
                "bytes": governed_rows.stat().st_size,
                "sha256": sha256_file(governed_rows),
            }
        },
        "claim_boundary": "Post-failure development only. It supports freezing a family-specific safety contract, not an incremental-superiority claim and not any conclusion about F-actin.",
    }
    output_path = OUTPUT / "family_specific_evidence_audit.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
                "status": payload["status"],
                "safety_passes": safety_passes,
                "incremental_benefit_passes": benefit_supported,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
