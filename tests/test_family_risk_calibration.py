from __future__ import annotations

import numpy as np

from nostos.validation.family_risk_calibration import (
    assign_stratified_group_folds,
    calibrated_operating_summary,
    cross_fitted_family_risk,
    fit_isotonic_risk_map,
    risk_coverage_auc,
)


def _row(
    case: int,
    *,
    group: str,
    structure: str,
    endpoint: str,
    score: float,
    invalid: bool,
    hard: bool = False,
) -> dict:
    return {
        "case_id": f"{structure}|{group}|{case}",
        "reference_group_id": f"{structure}|{group}",
        "structure": structure,
        "endpoint": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": hard,
        "invalid": invalid,
        "scores": {"full_contract": score},
    }


def test_isotonic_map_is_monotone_and_finite_with_zero_failures() -> None:
    fitted = fit_isotonic_risk_map(
        np.linspace(0.0, 1.0, 100),
        np.zeros(100, dtype=bool),
        bins=5,
    )
    predictions = fitted.predict(np.linspace(-1.0, 2.0, 200))
    assert np.all(np.diff(predictions) >= -1e-12)
    assert np.all((predictions > 0.0) & (predictions < 1.0))


def test_group_fold_assignment_never_splits_a_field() -> None:
    rows = [
        _row(
            index,
            group=f"field_{index // 3}",
            structure="ER" if index % 2 else "CCPs",
            endpoint="coherence",
            score=index / 30,
            invalid=index > 20,
        )
        for index in range(30)
    ]
    assignments = assign_stratified_group_folds(rows, folds=3, seed=12)
    for row in rows:
        key = (row["structure"], row["reference_group_id"])
        assert key in assignments
        assert assignments[key] in {0, 1, 2}


def test_cross_fit_emits_one_prediction_per_eligible_case() -> None:
    rows = []
    for group_index in range(12):
        for case_index in range(4):
            score = (group_index * 4 + case_index) / 48
            rows.append(
                _row(
                    case_index,
                    group=f"field_{group_index}",
                    structure="ER" if group_index % 2 else "CCPs",
                    endpoint="coherence",
                    score=score,
                    invalid=score > 0.75,
                )
            )
    augmented, maps = cross_fitted_family_risk(
        rows,
        family_map={"tensor_order": ["coherence"]},
        raw_score="full_contract",
        bins=4,
        folds=3,
        seed=7,
    )
    assert len(augmented) == len(rows)
    assert set(maps) == {"tensor_order"}
    assert all(0.0 <= row["calibrated_risk"] <= 1.0 for row in augmented)


def test_operating_summary_keeps_hard_abstention_in_denominator() -> None:
    rows = [
        {
            **_row(
                index,
                group="field",
                structure="ER",
                endpoint="coherence",
                score=0.1,
                invalid=False,
                hard=index == 0,
            ),
            "endpoint_family": "tensor_order",
            "calibrated_risk": 0.01 if index else 1.0,
        }
        for index in range(4)
    ]
    summary = calibrated_operating_summary(rows, maximum_predicted_risk=0.1)
    assert summary["coverage"] == 0.75


def test_risk_coverage_auc_rewards_correct_ordering() -> None:
    rows = [
        {"case_id": "a", "predicted": 0.1, "invalid": False},
        {"case_id": "b", "predicted": 0.2, "invalid": False},
        {"case_id": "c", "predicted": 0.9, "invalid": True},
    ]
    reversed_rows = [
        {**row, "predicted": 1.0 - row["predicted"]}
        for row in rows
    ]
    assert risk_coverage_auc(rows, score_key="predicted") < risk_coverage_auc(
        reversed_rows,
        score_key="predicted",
    )
