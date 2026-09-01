from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from nostos.features.physical_tensor import (
    axial_circular_wasserstein_degrees,
    physical_structure_tensor_response,
    shift_axial_histogram,
)


def axial_error(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def grating(shape: tuple[int, int], spacing: float, angle: float, wavelength: float) -> np.ndarray:
    y, x = np.indices(shape, dtype=float)
    x = (x - (shape[1] - 1) / 2.0) * spacing
    y = (y - (shape[0] - 1) / 2.0) * spacing
    normal = np.deg2rad(angle + 90.0)
    coordinate = np.cos(normal) * x + np.sin(normal) * y
    return 0.5 + 0.5 * np.sin(2.0 * np.pi * coordinate / wavelength)


@pytest.mark.parametrize("angle", [0.0, 23.0, 67.0, 119.0, 166.0])
def test_grating_orientation_is_accurate(angle: float) -> None:
    image = grating((256, 256), 0.1, angle, 1.6)
    response = physical_structure_tensor_response(
        image,
        spacing_um=(0.1, 0.1),
        scales_um=(0.4, 0.8),
    )
    assert max(axial_error(value, angle) for value in response.orientation_degrees) < 0.35
    assert min(response.orientation_resultant) > 0.98


def test_physical_resampling_preserves_orientation_and_coherency() -> None:
    fine = grating((256, 256), 0.1, 37.0, 2.0)
    coarse = ndimage.zoom(fine, 0.5, order=1, prefilter=False)
    fine_response = physical_structure_tensor_response(
        fine,
        spacing_um=(0.1, 0.1),
        scales_um=(0.5, 1.0),
    )
    coarse_response = physical_structure_tensor_response(
        coarse,
        spacing_um=(0.2, 0.2),
        scales_um=(0.5, 1.0),
    )
    assert max(
        axial_error(first, second)
        for first, second in zip(
            fine_response.orientation_degrees,
            coarse_response.orientation_degrees,
            strict=True,
        )
    ) < 0.25
    assert np.max(
        np.abs(np.asarray(fine_response.coherency) - np.asarray(coarse_response.coherency))
    ) < 0.02


def test_crossing_gratings_have_low_single_axis_resultant() -> None:
    first = grating((256, 256), 0.1, 20.0, 2.0)
    second = grating((256, 256), 0.1, 110.0, 2.0)
    response = physical_structure_tensor_response(
        0.5 * first + 0.5 * second,
        spacing_um=(0.1, 0.1),
        scales_um=(0.5,),
    )
    assert response.orientation_resultant[0] < 0.1
    assert abs(sum(response.orientation_histograms[0]) - 1.0) < 1e-12


def test_invalid_arguments_fail_closed() -> None:
    image = np.arange(64 * 64, dtype=float).reshape(64, 64)
    with pytest.raises(ValueError, match="spacing_um"):
        physical_structure_tensor_response(
            image,
            spacing_um=(0.0, 0.1),
            scales_um=(0.5,),
        )
    with pytest.raises(ValueError, match="scale factors"):
        physical_structure_tensor_response(
            image,
            spacing_um=(0.1, 0.1),
            scales_um=(0.5,),
            derivative_scale_fraction=0.0,
        )


def test_axial_circular_transport_handles_wrap_and_fractional_shift() -> None:
    histogram = np.zeros(36, dtype=float)
    histogram[35] = 1.0
    shifted = shift_axial_histogram(histogram, 5.0)
    assert np.argmax(shifted) == 0
    assert axial_circular_wasserstein_degrees(histogram, shifted) == pytest.approx(5.0)
    recovered = shift_axial_histogram(shifted, -5.0)
    assert axial_circular_wasserstein_degrees(histogram, recovered) < 1e-12
