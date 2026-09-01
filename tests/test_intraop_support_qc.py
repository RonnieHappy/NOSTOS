import numpy as np

from nostos.core.qc import acquisition_qc
from nostos.intraop.support_qc import acquisition_qc_on_support


def _supported_texture() -> tuple[np.ndarray, np.ndarray]:
    image = np.zeros((128, 128), dtype=float)
    support = np.zeros_like(image, dtype=bool)
    support[24:104, 24:104] = True
    y, x = np.mgrid[:80, :80]
    image[24:104, 24:104] = 100.0 + 30.0 * np.sin((x + 2.0 * y) / 7.0)
    return image, support


def test_unsupported_zero_background_does_not_trigger_endpoint_review() -> None:
    image, support = _supported_texture()
    assert acquisition_qc(image)["status"] == "review"
    result = acquisition_qc_on_support(image, support)
    assert result["status"] == "pass"
    assert result["outside_support_used"] is False


def test_support_qc_is_invariant_to_values_outside_support() -> None:
    image, support = _supported_texture()
    altered = image.copy()
    altered[~support] = np.linspace(-1000.0, 1000.0, np.sum(~support))
    first = acquisition_qc_on_support(image, support)
    second = acquisition_qc_on_support(altered, support)
    for key in (
        "status",
        "robust_dynamic_range",
        "variance",
        "normalized_laplacian_focus",
        "tenengrad_focus_v2",
        "contrast_to_residual",
        "observed_endpoint_fraction",
    ):
        assert first[key] == second[key]


def test_constant_supported_signal_abstains() -> None:
    image = np.zeros((64, 64), dtype=float)
    support = np.zeros_like(image, dtype=bool)
    support[8:56, 8:56] = True
    image[support] = 5.0
    result = acquisition_qc_on_support(image, support)
    assert result["status"] == "abstain"
    assert "LOW_DYNAMIC_RANGE" in result["flags"]
