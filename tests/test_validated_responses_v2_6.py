from __future__ import annotations

from nostos.features.validated_responses_v2_6 import (
    boundary_robust_gradient_anisotropy_2d,
    validated_boundary_robust_gradient_anisotropy_2d,
)
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.phantoms import generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


def test_v26_tapered_axis_is_rotation_equivariant() -> None:
    phantom = generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=2076270,
        correlation_length_um=26.0,
        anisotropy_ratio=2.7,
    )
    rotated = apply_perturbation(phantom, Perturbation("rotation", 43.0))
    reference = boundary_robust_gradient_anisotropy_2d(
        phantom.image, spacing_um=(1.0, 1.0)
    )
    transformed = boundary_robust_gradient_anisotropy_2d(
        rotated.image, spacing_um=(1.0, 1.0)
    )
    assert reference.major_axis_degrees is not None
    assert transformed.major_axis_degrees is not None
    observed_turn = axial_angular_error_degrees(
        reference.major_axis_degrees, transformed.major_axis_degrees
    )
    assert abs(observed_turn - 43.0) <= 3.0


def test_v26_rejects_field_with_too_few_characteristic_spans() -> None:
    phantom = generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=2084179,
        correlation_length_um=34.0,
        anisotropy_ratio=1.7,
    )
    response = validated_boundary_robust_gradient_anisotropy_2d(
        phantom.image, spacing_um=(1.0, 1.0)
    )
    assert response.characteristic_spans < 2.25
    assert response.supported is False
    assert "field_contains_fewer_than_2_25_characteristic_spans" in (
        response.abstention_reasons
    )


def test_v26_accepts_stable_large_field() -> None:
    phantom = generate_phantom(
        "heterogeneity",
        shape=(384, 384),
        spacing_um=(1.0, 1.0),
        seed=2618220,
        correlation_length_um=18.0,
        anisotropy_ratio=2.2,
    )
    response = validated_boundary_robust_gradient_anisotropy_2d(
        phantom.image, spacing_um=(1.0, 1.0)
    )
    assert response.characteristic_spans >= 2.25
    assert response.stability_score <= 0.20
    assert response.supported is True
