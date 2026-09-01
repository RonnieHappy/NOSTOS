"""Boundary-robust and field-supported NOSTOS response wrappers v2.6."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from nostos.features.spatial_fft import SpatialFFTFeatures, extract_spatial_fft
from nostos.features.validated_responses_v2_5 import (
    ValidatedHessianResponse,
    ValidatedSpatialResponse,
    ValidatedTensorResponse,
    validated_hessian_morphology,
    validated_intrinsic_variogram_2d,
    validated_tensor_orientation_2d,
)


PROFILE_VERSION = "nostos-validated-responses/2.6"


@dataclass(frozen=True)
class BoundaryRobustGradientResponse:
    ratio: float
    major_axis_degrees: float | None
    full_field_eigenvalues: tuple[float, float]
    tapered_eigenvalues: tuple[float, float]
    tapered_ratio: float
    axis_identifiable: bool
    method: str = "full_ratio_hann_tapered_physical_gradient_axis_v1"


@dataclass(frozen=True)
class ValidatedBoundaryRobustGradientResponse:
    response: BoundaryRobustGradientResponse
    spectral_support: SpatialFFTFeatures
    characteristic_wavelength_um: float
    characteristic_spans: float
    quadrant_median_log_drift: float
    nested_log_drift: float
    stability_score: float
    supported: bool
    abstention_reasons: tuple[str, ...]


def _validate_image_and_spacing(
    image: np.ndarray, spacing_um: tuple[float, float], *, minimum_size: int
) -> tuple[np.ndarray, np.ndarray]:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < minimum_size or not np.isfinite(data).all():
        raise ValueError(
            f"A finite 2-D image of at least {minimum_size} x {minimum_size} pixels is required."
        )
    spacing = np.asarray(spacing_um, dtype=float)
    if spacing.shape != (2,) or np.any(spacing <= 0) or not np.isfinite(spacing).all():
        raise ValueError("spacing_um must contain two finite positive values in y, x order.")
    return data, spacing


def _gradient_eigensystem(
    data: np.ndarray,
    spacing: np.ndarray,
    weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    gy, gx = np.gradient(data, float(spacing[0]), float(spacing[1]))
    normalized = np.asarray(weights, dtype=float)
    normalized /= float(np.sum(normalized))
    covariance = np.asarray(
        [
            [
                np.sum(normalized * gx * gx),
                np.sum(normalized * gx * gy),
            ],
            [
                np.sum(normalized * gx * gy),
                np.sum(normalized * gy * gy),
            ],
        ],
        dtype=float,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues[-1] <= np.finfo(float).eps:
        return eigenvalues, eigenvectors, 1.0
    floor = max(float(eigenvalues[-1]) * 1e-12, np.finfo(float).eps)
    positive = np.maximum(eigenvalues, floor)
    ratio = float(np.sqrt(positive[-1] / positive[0]))
    return eigenvalues, eigenvectors, ratio


def boundary_robust_gradient_anisotropy_2d(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    minimum_axis_ratio: float = 1.65,
) -> BoundaryRobustGradientResponse:
    """Measure full-field anisotropy and a tapered, boundary-robust axis."""

    data, spacing = _validate_image_and_spacing(
        image, spacing_um, minimum_size=16
    )
    full_values, _, ratio = _gradient_eigensystem(
        data, spacing, np.ones(data.shape, dtype=float)
    )
    taper = np.outer(np.hanning(data.shape[0]), np.hanning(data.shape[1]))
    tapered_values, tapered_vectors, tapered_ratio = _gradient_eigensystem(
        data, spacing, taper
    )
    identifiable = min(ratio, tapered_ratio) >= minimum_axis_ratio
    axis = None
    if identifiable:
        vector = tapered_vectors[:, 0]
        axis = float(np.mod(np.degrees(np.arctan2(vector[1], vector[0])), 180.0))
    return BoundaryRobustGradientResponse(
        ratio=ratio,
        major_axis_degrees=axis,
        full_field_eigenvalues=(float(full_values[0]), float(full_values[1])),
        tapered_eigenvalues=(float(tapered_values[0]), float(tapered_values[1])),
        tapered_ratio=tapered_ratio,
        axis_identifiable=identifiable,
    )


def _spectral_field_support(
    data: np.ndarray,
    spacing: np.ndarray,
) -> tuple[SpatialFFTFeatures, float, float]:
    target_spacing = float(np.max(spacing))
    zoom_factors = tuple(float(value / target_spacing) for value in spacing)
    spectral_image = data
    if not np.allclose(zoom_factors, (1.0, 1.0), rtol=0.0, atol=1e-12):
        spectral_image = ndimage.zoom(
            data,
            zoom=zoom_factors,
            order=1,
            mode="reflect",
            prefilter=False,
        )
    if min(spectral_image.shape) < 32:
        raise ValueError(
            "The coarsest-spacing spectral support image is smaller than 32 x 32 pixels."
        )
    spectral = extract_spatial_fft(
        spectral_image,
        pixel_size_um=target_spacing,
    )
    wavelength_um = float(
        1000.0 / spectral.characteristic_frequency_cycles_per_mm
    )
    physical_extent_um = min(
        float(size) * float(pixel_spacing)
        for size, pixel_spacing in zip(data.shape, spacing, strict=True)
    )
    spans = float(physical_extent_um / wavelength_um)
    return spectral, wavelength_um, spans


def validated_boundary_robust_gradient_anisotropy_2d(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    minimum_axis_ratio: float = 1.65,
    maximum_stability_score: float = 0.20,
    minimum_characteristic_spans: float = 2.25,
) -> ValidatedBoundaryRobustGradientResponse:
    """Emit an anisotropy ratio only with stable and sufficient field support."""

    data, spacing = _validate_image_and_spacing(
        image, spacing_um, minimum_size=64
    )
    if maximum_stability_score < 0 or not np.isfinite(maximum_stability_score):
        raise ValueError("maximum_stability_score must be finite and non-negative.")
    if minimum_characteristic_spans <= 0 or not np.isfinite(
        minimum_characteristic_spans
    ):
        raise ValueError("minimum_characteristic_spans must be finite and positive.")

    full = boundary_robust_gradient_anisotropy_2d(
        data,
        spacing_um=(float(spacing[0]), float(spacing[1])),
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
            boundary_robust_gradient_anisotropy_2d(
                quadrant,
                spacing_um=(float(spacing[0]), float(spacing[1])),
                minimum_axis_ratio=minimum_axis_ratio,
            ).ratio
            for quadrant in quadrants
        ],
        dtype=float,
    )
    margin_y = int(round(height * 0.125))
    margin_x = int(round(width * 0.125))
    nested = data[margin_y : height - margin_y, margin_x : width - margin_x]
    nested_ratio = boundary_robust_gradient_anisotropy_2d(
        nested,
        spacing_um=(float(spacing[0]), float(spacing[1])),
        minimum_axis_ratio=minimum_axis_ratio,
    ).ratio
    quadrant_drift = float(
        np.median(np.abs(np.log(quadrant_ratios / full.ratio)))
    )
    nested_drift = abs(float(np.log(nested_ratio / full.ratio)))
    stability_score = max(quadrant_drift, nested_drift)
    spectral, wavelength_um, characteristic_spans = _spectral_field_support(
        data, spacing
    )
    reasons = []
    if stability_score > maximum_stability_score:
        reasons.append("gradient_anisotropy_unstable_across_quadrants_or_nested_crop")
    if characteristic_spans < minimum_characteristic_spans:
        reasons.append("field_contains_fewer_than_2_25_characteristic_spans")
    return ValidatedBoundaryRobustGradientResponse(
        response=full,
        spectral_support=spectral,
        characteristic_wavelength_um=wavelength_um,
        characteristic_spans=characteristic_spans,
        quadrant_median_log_drift=quadrant_drift,
        nested_log_drift=nested_drift,
        stability_score=stability_score,
        supported=not reasons,
        abstention_reasons=tuple(reasons),
    )


__all__ = [
    "PROFILE_VERSION",
    "BoundaryRobustGradientResponse",
    "ValidatedBoundaryRobustGradientResponse",
    "ValidatedHessianResponse",
    "ValidatedSpatialResponse",
    "ValidatedTensorResponse",
    "boundary_robust_gradient_anisotropy_2d",
    "validated_boundary_robust_gradient_anisotropy_2d",
    "validated_hessian_morphology",
    "validated_intrinsic_variogram_2d",
    "validated_tensor_orientation_2d",
]
