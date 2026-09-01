"""Fail-closed v2.5 thresholds developed only on opened v2.4 failures.

The v2.4 implementation remains immutable for receipt verification.  This
module changes support thresholds, not the underlying numerical estimators.
"""

from __future__ import annotations

from nostos.features.response_modules import hessian_morphology_response
from nostos.features.validated_responses import (
    GradientMomentAnisotropyResponse,
    ValidatedGradientMomentResponse,
    ValidatedHessianResponse,
    ValidatedSpatialResponse,
    ValidatedTensorResponse,
    gradient_moment_anisotropy_2d as _gradient_moment_anisotropy_2d,
    validated_gradient_moment_anisotropy_2d as _validated_gradient_moment_anisotropy_2d,
    validated_intrinsic_variogram_2d,
    validated_tensor_orientation_2d,
)


PROFILE_VERSION = "nostos-validated-responses/2.5"


def validated_hessian_morphology(
    image,
    *,
    spacing_um: tuple[float, ...],
    scales_um: tuple[float, ...],
    minimum_samples_per_winning_scale: float = 5.0,
) -> ValidatedHessianResponse:
    """Classify Hessian morphology only at five samples per winning scale."""

    hessian = hessian_morphology_response(
        image,
        spacing_um=spacing_um,
        scales_um=scales_um,
    )
    samples = hessian.winning_scale_um / max(spacing_um)
    reasons = () if samples >= minimum_samples_per_winning_scale else (
        "winning_hessian_scale_below_5_samples",
    )
    return ValidatedHessianResponse(
        hessian=hessian,
        samples_per_winning_scale=float(samples),
        supported=not reasons,
        abstention_reasons=reasons,
    )


def gradient_moment_anisotropy_2d(
    image,
    *,
    spacing_um: tuple[float, float],
    minimum_axis_ratio: float = 1.65,
) -> GradientMomentAnisotropyResponse:
    """Estimate anisotropy while withholding axes below a ratio of 1.65."""

    return _gradient_moment_anisotropy_2d(
        image,
        spacing_um=spacing_um,
        minimum_axis_ratio=minimum_axis_ratio,
    )


def validated_gradient_moment_anisotropy_2d(
    image,
    *,
    spacing_um: tuple[float, float],
    minimum_axis_ratio: float = 1.65,
    maximum_stability_score: float = 0.20,
) -> ValidatedGradientMomentResponse:
    """Apply the v2.4 stability contract and the v2.5 axis threshold."""

    return _validated_gradient_moment_anisotropy_2d(
        image,
        spacing_um=spacing_um,
        minimum_axis_ratio=minimum_axis_ratio,
        maximum_stability_score=maximum_stability_score,
    )


__all__ = [
    "PROFILE_VERSION",
    "GradientMomentAnisotropyResponse",
    "ValidatedGradientMomentResponse",
    "ValidatedHessianResponse",
    "ValidatedSpatialResponse",
    "ValidatedTensorResponse",
    "gradient_moment_anisotropy_2d",
    "validated_gradient_moment_anisotropy_2d",
    "validated_hessian_morphology",
    "validated_intrinsic_variogram_2d",
    "validated_tensor_orientation_2d",
]
