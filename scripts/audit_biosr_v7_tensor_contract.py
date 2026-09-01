"""Audit one v7 tensor development run with per-combination field clustering."""

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


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development",
        type=Path,
        default=ROOT
        / "outputs/nostos0-biosr-v7-tensor-contract-development/tensor_contract_development.json",
    )
    parser.add_argument(
        "--rows",
        type=Path,
        default=ROOT
        / "outputs/nostos0-biosr-v7-tensor-contract-development/tensor_cases.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "outputs/nostos0-biosr-v7-tensor-contract-development/tensor_contract_audit.json",
    )
    args = parser.parse_args()
    development = json.loads(args.development.read_text(encoding="utf-8"))
    expected_rows = development["artifacts"]["tensor_cases"]
    if args.rows.stat().st_size != int(expected_rows["bytes"]):
        raise RuntimeError("Tensor-row byte count differs from the development receipt.")
    if sha256_file(args.rows) != str(expected_rows["sha256"]):
        raise RuntimeError("Tensor-row hash differs from the development receipt.")
    rows = [
        json.loads(line)
        for line in args.rows.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    observed_structures = {str(row["structure"]) for row in rows}
    if observed_structures != {"CCPs", "ER", "Microtubules"}:
        raise ValueError(f"Unexpected development structures: {observed_structures}")
    if any("F-actin" in json.dumps(row) for row in rows):
        raise RuntimeError("F-actin content appeared in the development rows.")

    full = summarize_policy(rows, condition="full_contract")
    qc = summarize_policy(rows, condition="conventional_acquisition_qc")
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
    overall_pass = bool(
        full["coverage"] >= rules["minimum_overall_coverage"]
        and full["risk"] is not None
        and full["risk"] <= rules["target_observed_risk"]
        and full["cluster_bootstrap_risk_upper95"] is not None
        and full["cluster_bootstrap_risk_upper95"]
        <= rules["maximum_cluster_bootstrap_risk_upper95"]
    )
    combination_pass = all(
        item["coverage"] >= rules["minimum_structure_family_coverage"]
        and item["risk"] is not None
        and item["risk"] <= rules["target_observed_risk"]
        and item["cluster_bootstrap_risk_upper95"] is not None
        and item["cluster_bootstrap_risk_upper95"]
        <= rules["maximum_cluster_bootstrap_risk_upper95"]
        for item in full["combinations"]
    )
    comparator_pass = bool(
        comparator["full_minus_comparator_risk"]
        <= rules["maximum_full_minus_qc_risk"]
        and comparator["coverage_loss_vs_comparator"]
        <= rules["maximum_coverage_loss_vs_qc"]
        and comparator["invalid_enrichment_among_comparator_only_rejections"]
        is not None
        and comparator["invalid_enrichment_among_comparator_only_rejections"]
        >= rules["minimum_invalid_enrichment_among_qc_only_rejections"]
    )
    failures = [
        {
            "structure": item["structure"],
            "endpoint_family": item["endpoint_family"],
            "coverage": item["coverage"],
            "risk": item["risk"],
            "cluster_bootstrap_risk_upper95": item[
                "cluster_bootstrap_risk_upper95"
            ],
            "worst_field_risk": item["worst_field_risk"],
        }
        for item in full["combinations"]
        if not (
            item["coverage"] >= rules["minimum_structure_family_coverage"]
            and item["risk"] is not None
            and item["risk"] <= rules["target_observed_risk"]
            and item["cluster_bootstrap_risk_upper95"] is not None
            and item["cluster_bootstrap_risk_upper95"]
            <= rules["maximum_cluster_bootstrap_risk_upper95"]
        )
    ]
    passed = overall_pass and combination_pass and comparator_pass
    payload = {
        "schema_version": "nostos-biosr-v7-tensor-contract-audit/1.0",
        "status": "pass" if passed else "fail",
        "development_boolean_reported_by_runner": development["development_gate"][
            "passes"
        ],
        "audit_supersedes_runner_boolean": True,
        "reason": "The audit adds the required field-clustered upper-risk gate to every structure-family combination and the complete incremental-comparator criteria.",
        "rules": rules,
        "gates": {
            "overall": overall_pass,
            "every_structure_family": combination_pass,
            "incremental_comparator": comparator_pass,
        },
        "full_contract": full,
        "conventional_acquisition_qc": qc,
        "incremental_comparator": comparator,
        "failed_structure_families": failures,
        "lineage": {
            "development": _artifact(args.development),
            "rows": _artifact(args.rows),
            "audit_implementation": _artifact(Path(__file__)),
            "audit_module": _artifact(
                ROOT / "src/nostos/validation/tensor_contract_audit_v7.py"
            ),
        },
        "f_actin_image_members_decoded": 0,
        "decision": (
            "Do not freeze v7; repair or restrict the unstable structure-family endpoint using development data only."
            if not passed
            else "Eligible for a separate pre-F-actin freeze audit."
        ),
        "claim_boundary": "Development audit only; not confirmation, clinical validation or submission readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**_artifact(args.output), "status": payload["status"]}, indent=2))


if __name__ == "__main__":
    main()
