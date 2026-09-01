import numpy as np
import pytest

from nostos.evaluation.robustness import (
    apply_gaussian_noise,
    apply_rotation,
    apply_smooth_illumination,
    evaluate_fft_perturbation,
    evaluate_robustness_suite,
)
from nostos.features.spatial_fft import extract_spatial_fft


def _stripes(size: int = 256, period: float = 16.0) -> np.ndarray:
    _, x = np.mgrid[:size, :size]
    return 100.0 + 50.0 * np.sin(2 * np.pi * x / period)


def test_fft_is_stable_to_smooth_illumination_after_detrending() -> None:
    drift = evaluate_fft_perturbation(
        _stripes(),
        lambda image: apply_smooth_illumination(
            image, gain=1.2, offset_fraction=0.1, gradient_fraction=0.2
        ),
        pixel_size_um=1.71,
    )
    assert drift["orientation_degrees_absolute_drift"] < 1.0
    assert drift["anisotropy_relative_drift"] < 0.05
    assert drift["angular_entropy_relative_drift"] < 0.05


def test_orientation_rotates_but_scalar_spectrum_is_invariant():
    reference = extract_spatial_fft(_stripes(), pixel_size_um=1.72)
    rotated = extract_spatial_fft(apply_rotation(_stripes(), 90), pixel_size_um=1.72)
    difference = abs(reference.orientation_degrees - rotated.orientation_degrees) % 180
    assert min(difference, 180 - difference) == pytest.approx(90, abs=1)
    assert rotated.anisotropy == pytest.approx(reference.anisotropy, rel=0.05)


def test_noise_is_seeded_and_suite_reports_failures_instead_of_dropping_cases():
    first = apply_gaussian_noise(_stripes(), 0.01, seed=7)
    second = apply_gaussian_noise(_stripes(), 0.01, seed=7)
    assert np.array_equal(first, second)
    rows = evaluate_robustness_suite(_stripes(), pixel_size_um=1.72)
    assert len(rows) == 7
    assert all("success" in row for row in rows)
