from __future__ import annotations

import pytest

from nostos.validation.tensor_evidence_v7 import (
    attach_family_specific_resolution_margin,
    clustered_coherence_aurc_difference,
    tied_score_aurc,
)


def _row(
    case_id: str,
    *,
    field: str,
    family: str,
    invalid: bool,
    qc_score: float,
    full_score: float | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "structure": "ER",
        "reference_group_id": field,
        "endpoint_family": family,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "invalid": invalid,
        "scores": {
            "full_contract": qc_score if full_score is None else full_score,
            "conventional_acquisition_qc": qc_score,
        },
    }


def test_family_specific_margin_governs_coherence_only() -> None:
    rows = [
        _row(
            "coherence",
            field="ER|1",
            family="tensor_coherence",
            invalid=True,
            qc_score=0.2,
        ),
        _row(
            "distribution",
            field="ER|1",
            family="tensor_orientation_distribution",
            invalid=True,
            qc_score=0.2,
        ),
    ]
    drift = [
        {
            "case_id": row["case_id"],
            "resolution_margin_drift": 0.15,
            "normalized_resolution_margin_drift": 1.0,
        }
        for row in rows
    ]
    result = attach_family_specific_resolution_margin(
        rows, drift, coherence_threshold_fraction=0.5
    )
    assert result[0]["scores"]["full_contract"] == 2.0
    assert result[0]["resolution_margin"]["governs_acceptance"] is True
    assert result[1]["scores"]["full_contract"] == 0.2
    assert result[1]["resolution_margin"]["governs_acceptance"] is False


def test_family_specific_margin_requires_exact_case_coverage() -> None:
    rows = [
        _row(
            "a",
            field="ER|1",
            family="tensor_coherence",
            invalid=False,
            qc_score=0.1,
        )
    ]
    with pytest.raises(ValueError, match="cover every tensor row"):
        attach_family_specific_resolution_margin(
            rows, [], coherence_threshold_fraction=0.5
        )


def test_tied_score_aurc_rewards_valid_first_ranking() -> None:
    ordered = [
        _row(
            "valid",
            field="ER|1",
            family="tensor_coherence",
            invalid=False,
            qc_score=0.1,
            full_score=0.1,
        ),
        _row(
            "invalid",
            field="ER|2",
            family="tensor_coherence",
            invalid=True,
            qc_score=0.1,
            full_score=0.9,
        ),
    ]
    assert tied_score_aurc(ordered, condition="full_contract") < tied_score_aurc(
        ordered, condition="conventional_acquisition_qc"
    )


def test_clustered_coherence_bootstrap_reports_positive_direction() -> None:
    rows = []
    for index in range(1, 7):
        invalid = index >= 5
        rows.append(
            _row(
                f"case-{index}",
                field=f"ER|{index}",
                family="tensor_coherence",
                invalid=invalid,
                qc_score=0.1,
                full_score=0.9 if invalid else 0.1,
            )
        )
    result = clustered_coherence_aurc_difference(rows, draws=500, seed=7)
    assert result["observed"]["comparator_minus_full"] > 0
    assert result["bootstrap"]["probability_full_better"] > 0.5
    assert result["invalid_reference_fields"] == 2
