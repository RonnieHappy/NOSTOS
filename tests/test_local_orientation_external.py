import numpy as np

from nostos.validation.local_orientation_external import _bootstrap_median


def test_group_bootstrap_median_is_bounded_by_data():
    groups = [np.asarray([1.0, 2.0, 3.0]), np.asarray([4.0, 5.0]), np.asarray([6.0])]
    low, high = _bootstrap_median(groups, draws=200)
    assert 1.0 <= low <= high <= 6.0
