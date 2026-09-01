from __future__ import annotations

import numpy as np
import pytest

from nostos.features.validated_responses import (
    gradient_moment_anisotropy_2d,
    validated_gradient_moment_anisotropy_2d,
    validated_hessian_morphology,
    validated_intrinsic_variogram_2d,
    validated_tensor_orientation_2d,
)
from nostos.validation.phantoms import generate_phantom


def test_validated_tensor_rejects_under_sampled_characteristic_scale() -> None:
    phantom = generate_phantom(
        "orientation",
        spacing_um=(1.5, 1.5),
        angle_degrees=31.0,
        scale_um=8.0,
    )
    response = validated_tensor_orientation_2d(
        phantom.image,
        spacing_um=(1.5, 1.5),
        scales_um=(1.0, 2.0, 4.0),
    )
    assert response.supported is False
    assert "characteristic_wavelength_below_six_samples" in response.abstention_reasons


def test_validated_tensor_accepts_resolved_directional_signal() -> None:
    phantom = generate_phantom(
        "orientation",
        spacing_um=(1.0, 1.0),
        angle_degrees=31.0,
        scale_um=24.0,
    )
    response = validated_tensor_orientation_2d(
        phantom.image,
        spacing_um=(1.0, 1.0),
        scales_um=(1.0, 2.0, 4.0),
    )
    assert response.supported is True
    assert response.abstention_reasons == ()


def test_validated_hessian_rejects_unresolved_winning_scale() -> None:
    phantom = generate_phantom(
        "blob",
        shape=(48, 48, 48),
        spacing_um=(1.0, 1.0, 2.0),
        scale_um=8.0,
    )
    response = validated_hessian_morphology(
        phantom.image,
        spacing_um=(1.0, 1.0, 2.0),
        scales_um=(2.0, 3.0, 4.0, 5.0, 6.0),
    )
    assert response.supported is False
    assert "winning_hessian_scale_below_3_5_samples" in response.abstention_reasons


def test_validated_spatial_rejects_constant_field() -> None:
    response = validated_intrinsic_variogram_2d(
        np.ones((64, 64), dtype=float),
        spacing_um=(1.0, 1.0),
        separations_um=(2.0, 4.0, 8.0, 16.0),
    )
    assert response.supported is False
    assert response.anisotropy_ratio is None


def test_gradient_moment_ratio_tracks_programmed_anisotropy() -> None:
    phantom = generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=812345,
        correlation_length_um=18.0,
        anisotropy_ratio=2.5,
    )
    response = gradient_moment_anisotropy_2d(
        phantom.image,
        spacing_um=(1.0, 1.0),
    )
    assert response.axis_identifiable is True
    assert response.major_axis_degrees is not None
    assert response.ratio == pytest.approx(2.5, rel=0.25)


def test_gradient_moment_axis_abstains_for_isotropic_gaussian_blob() -> None:
    yy, xx = np.mgrid[-64:64, -64:64]
    image = np.exp(-(xx**2 + yy**2) / (2.0 * 12.0**2))
    response = gradient_moment_anisotropy_2d(
        image,
        spacing_um=(1.0, 1.0),
    )
    assert response.axis_identifiable is False
    assert response.major_axis_degrees is None


def test_validated_gradient_moment_accepts_stable_anisotropic_field() -> None:
    phantom = generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=812345,
        correlation_length_um=18.0,
        anisotropy_ratio=2.5,
    )
    response = validated_gradient_moment_anisotropy_2d(
        phantom.image,
        spacing_um=(1.0, 1.0),
    )
    assert response.supported is True
    assert response.stability_score <= 0.20
    assert response.abstention_reasons == ()


def test_validated_gradient_moment_rejects_spatially_inconsistent_field() -> None:
    rng = np.random.default_rng(91)
    image = np.empty((128, 128), dtype=float)
    image[:64, :] = (
        np.sin(np.arange(128, dtype=float)[None, :] * 2.0 * np.pi / 12.0)
        + 0.05 * rng.normal(size=(64, 128))
    )
    image[64:, :] = rng.normal(size=(64, 128))
    response = validated_gradient_moment_anisotropy_2d(
        image,
        spacing_um=(1.0, 1.0),
    )
    assert response.supported is False
    assert response.stability_score > 0.20
    assert response.abstention_reasons == (
        "gradient_anisotropy_unstable_across_quadrants_or_nested_crop",
    )
