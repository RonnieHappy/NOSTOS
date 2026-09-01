import numpy as np

from nostos.evaluation.cpu_confounding import partial_rank_correlation
from nostos.reporting.cpu_pilot import benjamini_hochberg


def test_benjamini_hochberg_is_monotone_in_rank_and_bounded():
    p = np.array([0.01, 0.04, 0.03, 0.8])
    q = benjamini_hochberg(p)
    assert np.all((q >= 0) & (q <= 1))
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= -1e-12)


def test_partial_rank_removes_linear_covariate_signal():
    covariate = np.arange(30, dtype=float)
    x = covariate + 10 * np.sin(covariate)
    y = covariate + 10 * np.cos(covariate)
    adjusted = partial_rank_correlation(x, y, covariate[:, None])
    assert abs(adjusted) < 0.5
