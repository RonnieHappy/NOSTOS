import numpy as np

from nostos.validation.local_orientation import _case_measurements, _reference_tangents


def test_reference_tangent_for_horizontal_centerline():
    label = np.zeros((64, 64), dtype=bool)
    label[32, 10:54] = True
    coordinates, angles, anisotropy = _reference_tangents(label)
    assert len(coordinates) > 30
    assert np.median(np.minimum(angles, 180 - angles)) < 1
    assert np.min(anisotropy) > 0.9


def test_local_measurement_recovers_bright_horizontal_line():
    image = np.zeros((64, 64), dtype=float)
    image[31:34, 8:56] = 1.0
    label = np.zeros_like(image, dtype=bool)
    label[32, 10:54] = True
    result = _case_measurements(image, label)
    assert np.median(result["nostos_error"]) < 2.0
    assert np.median(result["sigma2_error"]) < 2.0
