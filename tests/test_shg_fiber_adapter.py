from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from nostos.features.shg_fiber_adapter import shg_fiber_adapter


def _fibers() -> np.ndarray:
    yy, xx = np.mgrid[:128, :128]
    image = 0.10 + 0.001 * yy
    for centre, slope in ((35.0, 0.2), (70.0, -0.15), (96.0, 0.05)):
        distance = np.abs(yy - (centre + slope * xx)) / np.sqrt(1.0 + slope**2)
        image += np.exp(-(distance**2) / (2.0 * 2.0**2))
    return ndimage.gaussian_filter(image, 0.5)


def test_adapter_is_deterministic_and_scale_calibrated() -> None:
    image = _fibers()
    kwargs = dict(
        spacing_um=(0.5, 0.5),
        background_opening_radius_um=10.0,
        ridge_scales_um=(1.0, 2.0, 4.0),
        foreground_quantile=0.75,
    )
    first = shg_fiber_adapter(image, **kwargs)
    second = shg_fiber_adapter(image, **kwargs)
    assert np.array_equal(first.mask, second.mask)
    assert np.array_equal(first.ridge_response, second.ridge_response)
    assert 0.01 < first.foreground_fraction < 0.60
    assert first.status in {"pass", "review"}


def test_adapter_rejects_constant_image() -> None:
    result = shg_fiber_adapter(
        np.ones((64, 64)),
        spacing_um=(1.0, 1.0),
        background_opening_radius_um=8.0,
        ridge_scales_um=(1.0, 2.0),
        foreground_quantile=0.75,
    )
    assert result.status == "abstain"
    assert "LOW_DYNAMIC_RANGE" in result.flags


def test_adapter_validates_physical_parameters() -> None:
    with pytest.raises(ValueError):
        shg_fiber_adapter(
            _fibers(),
            spacing_um=(0.0, 1.0),
            background_opening_radius_um=8.0,
            ridge_scales_um=(1.0,),
            foreground_quantile=0.75,
        )

