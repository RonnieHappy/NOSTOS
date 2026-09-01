"""Finalize the v7 tensor-distribution development receipt from completed rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nostos.validation.paired_acquisition_support import sha256_file
from nostos.validation.tensor_contract_audit_v7 import (
    incremental_comparator,
    summarize_policy,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "outputs/nostos0-biosr-v7-tensor-distribution-development"
FAILURE_RECEIPT = ROOT / "manifests/paired_acquisition_support_v6_confirmation_failure_receipt.json"
SOURCE_INDEXES = (
    ROOT / "outputs/nostos0-biosr-ccp-threshold-calibration-v5/pair_index.json",
    ROOT / "outputs/nostos0-biosr-er-threshold-calibration-v5/pair_index.json",
    ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation/pair_index.json",
)
CONDITIONS = (
    "full_contract",
    "conventional_acquisition_qc",
    "full_without_jackknife",
    "full_without_perturbation",
    "full_without_identifiability",
    "always_emit",
)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    directory = args.directory.resolve()
    rows_path = directory / "tensor_cases.jsonl"
    output_path = directory / "tensor_distribution_development.json"
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite finalized receipt: {output_path}")
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 5_400:
        raise ValueError(f"Expected 5,400 completed tensor rows; observed {len(rows)}.")
    if {row["endpoint"] for row in rows} != {
        "tensor_orientation_distribution",
        "tensor_coherence",
    }:
        raise ValueError("Completed rows do not contain the v7 distribution endpoint set.")
    if {row["structure"] for row in rows} != {"CCPs", "ER", "Microtubules"}:
        raise ValueError("Completed rows do not contain the three development structures.")
    if any("F-actin" in json.dumps(row) for row in rows):
        raise RuntimeError("F-actin content appeared in development rows.")

    policies = {
        condition: summarize_policy(rows, condition=condition)
        for condition in CONDITIONS
    }
    full = policies["full_contract"]
    comparator = incremental_comparator(rows)
    rules = {
        "target_observed_risk": 0.10,
        "maximum_cluster_bootstrap_risk_upper95": 0.15,
        "minimum_overall_coverage": 0.80,
        "minimum_structure_family_coverage": 0.70,
        "maximum_full_minus_qc_risk": 0.0,
        "maximum_coverage_loss_vs_qc": 0.10,
        "minimum_invalid_enrichment_among_qc_only_rejections": 2.0,
    }
    every_combination = all(
        item["coverage"] >= rules["minimum_structure_family_coverage"]
        and item["risk"] is not None
        and item["risk"] <= rules["target_observed_risk"]
        and item["cluster_bootstrap_risk_upper95"] is not None
        and item["cluster_bootstrap_risk_upper95"]
        <= rules["maximum_cluster_bootstrap_risk_upper95"]
        for item in full["combinations"]
    )
    passes = bool(
        full["coverage"] >= rules["minimum_overall_coverage"]
        and full["risk"] is not None
        and full["risk"] <= rules["target_observed_risk"]
        and full["cluster_bootstrap_risk_upper95"] is not None
        and full["cluster_bootstrap_risk_upper95"]
        <= rules["maximum_cluster_bootstrap_risk_upper95"]
        and every_combination
        and comparator["full_minus_comparator_risk"]
        <= rules["maximum_full_minus_qc_risk"]
        and comparator["coverage_loss_vs_comparator"]
        <= rules["maximum_coverage_loss_vs_qc"]
        and comparator["invalid_enrichment_among_comparator_only_rejections"]
        is not None
        and comparator["invalid_enrichment_among_comparator_only_rejections"]
        >= rules["minimum_invalid_enrichment_among_qc_only_rejections"]
    )
    source_receipts = []
    for path in SOURCE_INDEXES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_receipts.append(
            {
                **artifact(path),
                "structure": payload["structure"],
                "fields": len({row["cell_id"] for row in payload["records"]}),
                "pairs": len(payload["records"]),
            }
        )
    payload = {
        "schema_version": "nostos-biosr-v7-tensor-distribution-development/1.0",
        "status": (
            "development_pass_pending_v7_freeze"
            if passes
            else "development_fail_do_not_freeze"
        ),
        "finalized_from_completed_rows_after_path_serialization_error": True,
        "path_error_effect_on_scientific_rows": "none; all 5,400 rows were written before receipt serialization failed",
        "scope": {
            "structures": ["CCPs", "ER", "Microtubules"],
            "reference_fields": len(
                {(row["structure"], row["reference_group_id"]) for row in rows}
            ),
            "paired_acquisitions": len({row["pair_id"] for row in rows}),
            "endpoint_rows": len(rows),
            "f_actin_image_members_decoded": 0,
            "f_actin_endpoint_outcomes_computed": 0,
        },
        "endpoint_decision": {
            "retained_claim_endpoints": [
                "tensor_orientation_distribution",
                "tensor_coherence",
            ],
            "scalar_axis": "diagnostic_only_claim_eligible_false",
            "orientation_distribution_error": "axial circular Wasserstein-1 distance in degrees over 36 five-degree bins",
            "distribution_invalidity_tolerance_degrees": 10.0,
            "reason": "The scalar global axis failed field-clustered development in heterogeneous ER; the preserved orientation distribution measures mixed and crossing directions without forcing a single axis.",
        },
        "selected_tensor": {
            "derivative_scale_fraction": 0.5,
            "integration_scale_factor": 1.0,
            "selection_screen": artifact(
                ROOT
                / "outputs/nostos0-biosr-v7-physical-tensor-cross-domain-development/candidate_screen.json"
            ),
        },
        "rules": rules,
        "policies": policies,
        "incremental_comparator": comparator,
        "development_gate": {
            "passes": passes,
            "every_structure_family_passes": every_combination,
        },
        "sources": source_receipts,
        "lineage": {
            "v6_failure_receipt": artifact(FAILURE_RECEIPT),
            "physical_tensor": artifact(
                ROOT / "src/nostos/features/physical_tensor.py"
            ),
            "tensor_support": artifact(
                ROOT / "src/nostos/validation/tensor_support_v7.py"
            ),
            "development_runner": artifact(
                ROOT / "scripts/develop_biosr_v7_tensor_contract.py"
            ),
            "finalizer": artifact(Path(__file__)),
        },
        "artifacts": {"tensor_cases": artifact(rows_path)},
        "claim_boundary": "Development evidence only. F-actin remains untouched at the pixel and endpoint level; no confirmation, clinical or submission-ready claim is made.",
    }
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {**artifact(output_path), "development_gate_passed": passes},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
