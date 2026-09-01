import numpy as np
from nostos.validation.bone_network_3d import _perturb, measure_network


def test_network_metrics_are_physical_and_finite():
    seg = np.zeros((24, 32, 32), dtype=np.uint8)
    seg[12, 4:28, 16] = 1
    seg[12, 16, 4:28] = 1
    seg[8:16, 15:18, 15:18] = 2
    result = measure_network(seg, (0.3, 0.18, 0.18))
    assert result["skeleton_length_density_per_um2"] > 0
    assert 0 < result["largest_component_fraction"] <= 1
    assert all(np.isfinite(value) for value in result.values())


def test_perturbation_is_deterministic_and_only_deletes_canaliculi():
    seg = np.ones((24, 32, 32), dtype=np.uint8)
    a = _perturb(seg, 4, (4, 8, 8), 7)
    b = _perturb(seg, 4, (4, 8, 8), 7)
    assert np.array_equal(a, b)
    assert np.count_nonzero(a == 1) < np.count_nonzero(seg == 1)
