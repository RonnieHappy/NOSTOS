import numpy as np
import pytest

from nostos.evaluation.participant import participant_metrics
from nostos.modeling.grouped_ridge import (
    grouped_nested_ridge_predictions,
    locked_ridge_predictions,
    participant_permutation_test,
)


def test_grouped_nested_ridge_predicts_repeated_participant_signal() -> None:
    rng = np.random.default_rng(12)
    groups = np.repeat([f"{index:03d}" for index in range(30)], 2)
    participant_signal = np.repeat(np.linspace(-2.0, 2.0, 30), 2)
    features = np.column_stack(
        [participant_signal + rng.normal(0, 0.05, len(groups)), rng.normal(size=len(groups))]
    )
    outcome = 3.0 * participant_signal + rng.normal(0, 0.05, len(groups))
    result = grouped_nested_ridge_predictions(features, outcome, groups)
    metrics = participant_metrics(groups, outcome, result.predicted)
    assert metrics.r_squared > 0.95
    for fold in np.unique(result.outer_fold):
        test_groups = set(groups[result.outer_fold == fold])
        assert all(np.unique(result.outer_fold[groups == group]).size == 1 for group in test_groups)


def test_participant_permutation_falsifies_strong_signal() -> None:
    rng = np.random.default_rng(7)
    participants = np.array([f"P{index:03}" for index in range(30)])
    outcome = np.linspace(-2, 2, len(participants))
    features = np.column_stack(
        (outcome + rng.normal(0, 0.02, len(outcome)), rng.normal(size=len(outcome)))
    )
    result = participant_permutation_test(
        features, outcome, participants, iterations=20, outer_splits=3, inner_splits=2
    )
    assert result["observed_mae"] < result["null_mae_mean"]
    assert result["permutation_p_lower_mae"] <= 2 / 21


def test_locked_predictions_reject_participant_overlap() -> None:
    features = np.arange(20, dtype=float)[:, None]
    outcome = np.arange(20, dtype=float)
    with pytest.raises(ValueError, match="leakage"):
        locked_ridge_predictions(
            features[:15], outcome[:15], np.array([f"P{i}" for i in range(15)]),
            features[15:], outcome[15:], np.array(["P0", "P16", "P17", "P18", "P19"]),
        )
