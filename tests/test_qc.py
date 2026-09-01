import numpy as np

from nostos.core.qc import acquisition_qc


def test_qc_abstains_on_constant_image():
    result = acquisition_qc(np.ones((32, 32)))
    assert result["status"] == "abstain"
    assert "LOW_DYNAMIC_RANGE" in result["flags"]


def test_qc_focus_score_falls_with_blur():
    rng = np.random.default_rng(7)
    sharp = rng.normal(size=(64, 64))
    from scipy.ndimage import gaussian_filter
    blurred = gaussian_filter(sharp, 4.0)
    assert acquisition_qc(sharp)["tenengrad_focus_v2"] > acquisition_qc(blurred)["tenengrad_focus_v2"]


def test_qc_flags_high_endpoint_fraction_without_calling_it_invalid():
    image = np.zeros((32, 32)); image[8:24, 8:24] = 1
    result = acquisition_qc(image)
    assert result["status"] == "review"
    assert "HIGH_ENDPOINT_FRACTION" in result["flags"]
