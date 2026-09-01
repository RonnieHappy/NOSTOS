import numpy as np
import pytest

from nostos.features.response_modules import hessian_morphology_maps


def test_hessian_polarity_separates_bright_and_dark_blobs() -> None:
    y, x = np.mgrid[-16:17, -16:17]
    bright = np.exp(-(x**2 + y**2) / (2 * 4**2))
    dark = 1.0 - bright
    bright_response = hessian_morphology_maps(bright, spacing_um=(1, 1), scales_um=(4,), polarity="bright")["blob"][0]
    wrong_response = hessian_morphology_maps(bright, spacing_um=(1, 1), scales_um=(4,), polarity="dark")["blob"][0]
    dark_response = hessian_morphology_maps(dark, spacing_um=(1, 1), scales_um=(4,), polarity="dark")["blob"][0]
    assert bright_response[16, 16] > wrong_response[16, 16]
    assert dark_response[16, 16] > 0


def test_hessian_polarity_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="polarity"):
        hessian_morphology_maps(np.ones((8, 8)), spacing_um=(1, 1), scales_um=(2,), polarity="unknown")
