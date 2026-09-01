import numpy as np
import pytest

from nostos.evaluation.participant import (
    assert_disjoint_participant_splits,
    paired_participant_bootstrap,
    participant_metrics,
)


def test_repeated_tiles_are_collapsed_before_metrics() -> None:
    ids = ["001", "001", "002", "002"]
    observed = [1.0, 1.0, 3.0, 3.0]
    predicted = [0.0, 2.0, 2.0, 4.0]
    metrics = participant_metrics(ids, observed, predicted)
    assert metrics.participant_count == 2
    assert metrics.mae == 0.0
    assert metrics.spearman_rho == pytest.approx(1.0)


def test_paired_bootstrap_favors_better_model() -> None:
    ids = [f"{index:03d}" for index in range(1, 31)]
    observed = np.linspace(0.0, 10.0, len(ids))
    worse = observed + 2.0
    better = observed + 0.2
    result = paired_participant_bootstrap(ids, observed, worse, better, iterations=500)
    assert result["difference"] < 0
    assert result["probability_b_better"] > 0.99


def test_leakage_audit_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="leakage"):
        assert_disjoint_participant_splits({"train": ["001"], "test": ["001"]})
