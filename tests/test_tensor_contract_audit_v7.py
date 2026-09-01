from __future__ import annotations

from nostos.validation.tensor_contract_audit_v7 import (
    clustered_risk_upper95,
    incremental_comparator,
    summarize_policy,
)


def row(case: str, field: str, invalid: bool, full: bool = True) -> dict:
    return {
        "case_id": case,
        "structure": "S",
        "reference_group_id": field,
        "endpoint_family": "tensor_orientation",
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "invalid": invalid,
        "hard_abstention_reasons": [] if full else ["input_resultant_below_0.15"],
        "scores": {
            "full_contract": 0.5 if full else 2.0,
            "conventional_acquisition_qc": 0.2,
            "always_emit": 0.0,
            "full_without_jackknife": 0.5 if full else 2.0,
            "full_without_perturbation": 0.5 if full else 2.0,
            "full_without_identifiability": 0.2,
        },
    }


def test_clustered_summary_retains_field_concentration() -> None:
    rows = [
        row("a1", "a", False),
        row("a2", "a", False),
        row("b1", "b", True),
        row("b2", "b", True),
    ]
    summary = summarize_policy(rows, condition="full_contract", draws=1_000, seed=7)
    combination = summary["combinations"][0]
    assert combination["worst_field_risk"] == 1.0
    assert combination["cluster_bootstrap_risk_upper95"] >= 0.5


def test_incremental_comparator_counts_rejected_invalid_cases() -> None:
    rows = [
        row("a", "f1", False),
        row("b", "f1", True, full=False),
        row("c", "f2", False),
    ]
    result = incremental_comparator(rows)
    assert result["comparator_only_rejections"] == 1
    assert result["invalid_comparator_only_rejections"] == 1
    assert result["full_risk"] < result["comparator_risk"]


def test_clustered_risk_is_none_without_eligible_rows() -> None:
    assert clustered_risk_upper95([], condition="full_contract", draws=10) is None
