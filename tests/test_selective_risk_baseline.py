from __future__ import annotations

import numpy as np

from nostos.validation.selective_risk_baseline import (
    DomainSpec,
    _feature_matrix,
    _feature_schema,
    _fit_predictors,
    _nearest_tied_indices,
    _risk_coverage_auc,
)


def _rows(prefix: str, groups: int, repeats: int) -> list[dict]:
    rows = []
    for group in range(groups):
        for repeat in range(repeats):
            value = (group + repeat / repeats) / groups
            rows.append(
                {
                    "case_id": f"{prefix}-{group}-{repeat}",
                    "reference_group_id": f"{prefix}-{group}",
                    "endpoint": "orientation",
                    "pair_registration_eligible": True,
                    "reference_eligible": True,
                    "invalid": bool(value > 0.55),
                    "support_components": {
                        "acquisition": value,
                        "stability": abs(0.5 - value),
                    },
                    "scores": {
                        "full_contract": value,
                        "acquisition_qc": value,
                    },
                }
            )
    return rows


def _spec() -> DomainSpec:
    return DomainSpec(
        name="synthetic",
        development="unused",
        confirmation="unused",
        nostos_score="full_contract",
        acquisition_score="acquisition_qc",
        endpoint_score=None,
        feature_source="support_components",
        bootstrap_group_field="reference_group_id",
        historical_accepted=3,
    )


def test_tied_risk_coverage_auc_keeps_complete_score_groups():
    scores = np.asarray([0.0, 0.0, 1.0, 1.0])
    invalid = np.asarray([0, 1, 1, 1])
    value = _risk_coverage_auc(scores, invalid)
    expected = np.trapezoid([0.0, 0.5, 0.75], [0.0, 0.5, 1.0])
    assert value == expected


def test_nearest_tied_selection_never_splits_boundary_tie():
    scores = np.asarray([0.0, 0.0, 0.5, 0.5, 1.0])
    selected = _nearest_tied_indices(scores, 3)
    assert len(selected) == 4
    assert set(selected.tolist()) == {0, 1, 2, 3}


def test_feature_schema_is_label_blind_and_fixed_from_development():
    development = _rows("dev", 4, 6)
    confirmation = _rows("conf", 2, 6)
    spec = _spec()
    numeric, endpoints = _feature_schema(development, confirmation, spec)
    original, names = _feature_matrix(confirmation, spec, numeric, endpoints)
    complemented = [dict(row, invalid=not row["invalid"]) for row in confirmation]
    mutated, mutated_names = _feature_matrix(complemented, spec, numeric, endpoints)
    assert names == mutated_names
    np.testing.assert_array_equal(original, mutated)


def test_fixed_learned_comparators_are_deterministic_and_finite():
    development = _rows("dev", 4, 8)
    confirmation = _rows("conf", 2, 8)
    first = _fit_predictors(development, confirmation, _spec())
    second = _fit_predictors(development, confirmation, _spec())
    np.testing.assert_array_equal(first["logistic_score"], second["logistic_score"])
    np.testing.assert_array_equal(first["boosted_score"], second["boosted_score"])
    assert np.isfinite(first["logistic_score"]).all()
    assert np.isfinite(first["boosted_score"]).all()
    assert first["label_blind"] is True
