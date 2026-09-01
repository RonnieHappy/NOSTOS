"""Fail-closed v2 wrappers around calibrated NOSTOS response modules.

The numerical estimators remain unchanged. These wrappers attach input-known
support decisions selected only on the opened synthetic physical-truth v2
development cases.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from nostos.features.intrinsic_variogram import (
    IntrinsicVariogramResponse,
    intrinsic_variogram_2d,
)
from nostos.features.response_modules import (
    HessianResponse,
    TensorResponse,
    hessian_morphology_response,
    structure_tensor_response,
)
from nostos.features.spatial_fft import SpatialFFTFeatures, extract_spatial_fft


PROFILE_VERSION = "nostos-validated-responses/2.4"


@dataclass(frozen=True)
class ValidatedTensorResponse:
    tensor: TensorResponse
    spectral: SpatialFFTFeatures
    characteristic_wavelength_um: float
    samples_per_characteristic_wavelength: float
    supported: bool
    abstention_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedHessianResponse:
    hessian: HessianResponse
    samples_per_winning_scale: float
    supported: bool
    abstention_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedSpatialResponse:
    variogram: IntrinsicVariogramResponse
    median_angular_anisotropy: float
    anisotropy_ratio: float | None
    supported: bool
    abstention_reasons: tuple[str, ...]


@dataclass(frozen=True)
class GradientMomentAnisotropyResponse:
    ratio: float
    major_axis_degrees: float | None
    eigenvalues: tuple[float, float]
    axis_identifiable: bool
    method: str = "physical_gradient_covariance_eigenratio_v1"


@dataclass(frozen=True)
class ValidatedGradientMomentResponse:
    response: GradientMomentAnisotropyResponse
    quadrant_median_log_drift: float
    nested_log_drift: float
    stability_score: float
    supported: bool
    abstention_reasons: tuple[str, ...]


def validated_tensor_orientation_2d(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    scales_um: tuple[float, ...],
    minimum_samples_per_characteristic_wavelength: float = 6.0,
    minimum_spectral_anisotropy: float = 0.50,
) -> ValidatedTensorResponse:
    """Measure orientation and abstain when scale/direction are unsupported."""

    if not np.isclose(spacing_um[0], spacing_um[1], rtol=0.0, atol=1e-12):
        raise ValueError("Validated FFT-coupled tensor v2.1 requires isotropic 2-D spacing.")
    spectral = extract_spatial_fft(image, pixel_size_um=float(spacing_um[0]))
    wavelength = float(1000.0 / spectral.characteristic_frequency_cycles_per_mm)
    samples = wavelength / max(spacing_um)
    reasons = []
    if samples < minimum_samples_per_characteristic_wavelength:
        reasons.append("characteristic_wavelength_below_six_samples")
    if spectral.anisotropy < minimum_spectral_anisotropy:
        reasons.append("spectral_orientation_not_identifiable")
    tensor = structure_tensor_response(
        image,
        spacing_um=spacing_um,
        scales_um=scales_um,
    )
    return ValidatedTensorResponse(
        tensor=tensor,
        spectral=spectral,
        characteristic_wavelength_um=wavelength,
        samples_per_characteristic_wavelength=samples,
        supported=not reasons,
        abstention_reasons=tuple(reasons),
    )


def validated_hessian_morphology(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, ...],
    scales_um: tuple[float, ...],
    minimum_samples_per_winning_scale: float = 3.5,
) -> ValidatedHessianResponse:
    """Classify Hessian morphology only where the winning scale is sampled."""

    hessian = hessian_morphology_response(
        image,
        spacing_um=spacing_um,
        scales_um=scales_um,
    )
    samples = hessian.winning_scale_um / max(spacing_um)
    reasons = () if samples >= minimum_samples_per_winning_scale else (
        "winning_hessian_scale_below_3_5_samples",
    )
    return ValidatedHessianResponse(
        hessian=hessian,
        samples_per_winning_scale=float(samples),
        supported=not reasons,
        abstention_reasons=reasons,
    )


def validated_intrinsic_variogram_2d(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    separations_um: tuple[float, ...],
    minimum_median_angular_anisotropy: float = 0.20,
) -> ValidatedSpatialResponse:
    """Return intrinsic range anisotropy only when direction and ranges resolve."""

    response = intrinsic_variogram_2d(
        image,
        spacing_um=spacing_um,
        separations_um=separations_um,
    )
    median_anisotropy = float(np.median(response.angular_anisotropy_curve))
    reasons = list(response.abstention_reasons)
    if median_anisotropy < minimum_median_angular_anisotropy:
        reasons.append("spatial_anisotropy_below_0_20")
    if not response.range_identifiable:
        reasons.append("intrinsic_ranges_not_identifiable")
    supported = not reasons
    ratio = None
    if supported:
        assert response.major_e_fold_range_um is not None
        assert response.minor_e_fold_range_um is not None
        ratio = float(response.major_e_fold_range_um / response.minor_e_fold_range_um)
    return ValidatedSpatialResponse(
        variogram=response,
        median_angular_anisotropy=median_anisotropy,
        anisotropy_ratio=ratio,
        supported=supported,
        abstention_reasons=tuple(dict.fromkeys(reasons)),
    )


def gradient_moment_anisotropy_2d(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    minimum_axis_ratio: float = 1.55,
) -> GradientMomentAnisotropyResponse:
    """Estimate scale-free structural anisotropy from physical gradients.

    The square root of the global gradient-covariance eigenvalue ratio is one
    for isotropic differentiable random fields and tracks the ratio of their
    principal correlation lengths. The axis with smaller gradient variance is
    the major structural axis. Near isotropy the ratio remains reportable but
    the axis abstains.
    """

    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 16 or not np.isfinite(data).all():
        raise ValueError("A finite 2-D image of at least 16 x 16 pixels is required.")
    spacing = np.asarray(spacing_um, dtype=float)
    if spacing.shape != (2,) or np.any(spacing <= 0):
        raise ValueError("spacing_um must contain two positive values in y, x order.")
    gy, gx = np.gradient(data, float(spacing[0]), float(spacing[1]))
    covariance = np.asarray(
        [
            [np.mean(gx * gx), np.mean(gx * gy)],
            [np.mean(gx * gy), np.mean(gy * gy)],
        ],
        dtype=float,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues[-1] <= np.finfo(float).eps:
        return GradientMomentAnisotropyResponse(
            ratio=1.0,
            major_axis_degrees=None,
            eigenvalues=(float(eigenvalues[0]), float(eigenvalues[1])),
            axis_identifiable=False,
        )
    floor = max(float(eigenvalues[-1]) * 1e-12, np.finfo(float).eps)
    positive = np.maximum(eigenvalues, floor)
    ratio = float(np.sqrt(positive[-1] / positive[0]))
    axis = None
    identifiable = ratio >= minimum_axis_ratio
    if identifiable:
        vector = eigenvectors[:, 0]
        axis = float(np.mod(np.degrees(np.arctan2(vector[1], vector[0])), 180.0))
    return GradientMomentAnisotropyResponse(
        ratio=ratio,
        major_axis_degrees=axis,
        eigenvalues=(float(eigenvalues[0]), float(eigenvalues[1])),
        axis_identifiable=identifiable,
    )


def validated_gradient_moment_anisotropy_2d(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    minimum_axis_ratio: float = 1.55,
    maximum_stability_score: float = 0.20,
) -> ValidatedGradientMomentResponse:
    """Measure anisotropy only when it is stable across internal views.

    Support is determined without outcome labels.  The full-field estimate is
    compared with four non-overlapping quadrants and with a centered 75% crop.
    The frozen v2.4 stability score is the larger of the median quadrant log
    drift and the nested-crop log drift.
    """

    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 64 or not np.isfinite(data).all():
        raise ValueError("A finite 2-D image of at least 64 x 64 pixels is required.")
    if not np.isfinite(maximum_stability_score) or maximum_stability_score < 0:
        raise ValueError("maximum_stability_score must be finite and non-negative.")

    full = gradient_moment_anisotropy_2d(
        data,
        spacing_um=spacing_um,
        minimum_axis_ratio=minimum_axis_ratio,
    )
    height, width = data.shape
    quadrants = (
        data[: height // 2, : width // 2],
        data[: height // 2, width // 2 :],
        data[height // 2 :, : width // 2],
        data[height // 2 :, width // 2 :],
    )
    quadrant_ratios = np.asarray(
        [
            gradient_moment_anisotropy_2d(
                quadrant,
                spacing_um=spacing_um,
                minimum_axis_ratio=minimum_axis_ratio,
            ).ratio
            for quadrant in quadrants
        ],
        dtype=float,
    )
    margin_y = int(round(height * 0.125))
    margin_x = int(round(width * 0.125))
    nested = data[margin_y : height - margin_y, margin_x : width - margin_x]
    nested_response = gradient_moment_anisotropy_2d(
        nested,
        spacing_um=spacing_um,
        minimum_axis_ratio=minimum_axis_ratio,
    )
    quadrant_median_log_drift = float(
        np.median(np.abs(np.log(quadrant_ratios / full.ratio)))
    )
    nested_log_drift = abs(float(np.log(nested_response.ratio / full.ratio)))
    stability_score = max(quadrant_median_log_drift, nested_log_drift)
    reasons: tuple[str, ...] = ()
    if stability_score > maximum_stability_score:
        reasons = ("gradient_anisotropy_unstable_across_quadrants_or_nested_crop",)
    return ValidatedGradientMomentResponse(
        response=full,
        quadrant_median_log_drift=quadrant_median_log_drift,
        nested_log_drift=nested_log_drift,
        stability_score=stability_score,
        supported=not reasons,
        abstention_reasons=reasons,
    )


__all__ = [
    "PROFILE_VERSION",
    "GradientMomentAnisotropyResponse",
    "ValidatedGradientMomentResponse",
    "ValidatedHessianResponse",
    "ValidatedSpatialResponse",
    "ValidatedTensorResponse",
    "validated_hessian_morphology",
    "gradient_moment_anisotropy_2d",
    "validated_gradient_moment_anisotropy_2d",
    "validated_intrinsic_variogram_2d",
    "validated_tensor_orientation_2d",
]
