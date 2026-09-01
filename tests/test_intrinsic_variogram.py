from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from nostos.features.intrinsic_variogram import intrinsic_variogram_2d
from nostos.validation.metrics import axial_angular_error_degrees


SEPARATIONS = (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 16.0)


def _anisotropic_field(seed: int = 7) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(size=(160, 160))
    return ndimage.gaussian_filter(noise, sigma=(2.0, 10.0), mode="reflect")


def test_intrinsic_curves_are_invariant_to_quarter_turn() -> None:
    original = intrinsic_variogram_2d(
        _anisotropic_field(),
        spacing_um=(1.0, 1.0),
        separations_um=SEPARATIONS,
    )
    rotated = intrinsic_variogram_2d(
        np.rot90(_anisotropic_field()),
        spacing_um=(1.0, 1.0),
        separations_um=SEPARATIONS,
    )
    assert np.asarray(rotated.angular_mean_curve) == pytest.approx(
        original.angular_mean_curve,
        rel=0.03,
        abs=1e-8,
    )
    assert np.asarray(rotated.angular_anisotropy_curve) == pytest.approx(
        original.angular_anisotropy_curve,
        abs=0.03,
    )
    assert np.asarray(rotated.major_correlation_curve) == pytest.approx(
        original.major_correlation_curve,
        rel=0.05,
        abs=1e-8,
    )
    assert np.asarray(rotated.minor_correlation_curve) == pytest.approx(
        original.minor_correlation_curve,
        rel=0.05,
        abs=1e-8,
    )


def test_consensus_axis_is_equivariant_to_quarter_turn() -> None:
    original = intrinsic_variogram_2d(
        _anisotropic_field(),
        spacing_um=(1.0, 1.0),
        separations_um=SEPARATIONS,
    )
    rotated = intrinsic_variogram_2d(
        np.rot90(_anisotropic_field()),
        spacing_um=(1.0, 1.0),
        separations_um=SEPARATIONS,
    )
    assert original.axis_consensus_degrees is not None
    assert rotated.axis_consensus_degrees is not None
    observed_turn = axial_angular_error_degrees(
        original.axis_consensus_degrees,
        rotated.axis_consensus_degrees,
    )
    assert observed_turn == pytest.approx(90.0, abs=3.0)


def test_isotropic_gaussian_abstains_from_axis() -> None:
    yy, xx = np.mgrid[-64:64, -64:64]
    image = np.exp(-(xx**2 + yy**2) / (2.0 * 12.0**2))
    response = intrinsic_variogram_2d(
        image,
        spacing_um=(1.0, 1.0),
        separations_um=SEPARATIONS,
    )
    assert response.axis_consensus_degrees is None
    assert "directional_axis_not_identifiable" in response.abstention_reasons


def test_constant_image_abstains_from_ranges_and_axis() -> None:
    response = intrinsic_variogram_2d(
        np.ones((64, 64)),
        spacing_um=(1.0, 1.0),
        separations_um=(1.0, 2.0, 4.0, 8.0),
    )
    assert response.axis_consensus_degrees is None
    assert response.range_identifiable is False
    assert response.major_e_fold_range_um is None
    assert response.minor_e_fold_range_um is None


def test_physical_spacing_units_are_respected() -> None:
    image = _anisotropic_field()
    micrometres = intrinsic_variogram_2d(
        image,
        spacing_um=(1.0, 1.0),
        separations_um=SEPARATIONS,
    )
    doubled_units = intrinsic_variogram_2d(
        image,
        spacing_um=(2.0, 2.0),
        separations_um=tuple(2.0 * value for value in SEPARATIONS),
    )
    assert doubled_units.angular_mean_curve == pytest.approx(
        micrometres.angular_mean_curve,
        rel=1e-12,
        abs=1e-12,
    )
    if micrometres.major_e_fold_range_um is not None:
        assert doubled_units.major_e_fold_range_um == pytest.approx(
            2.0 * micrometres.major_e_fold_range_um
        )
