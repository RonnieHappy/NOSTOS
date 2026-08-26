import numpy as np

from nostos.features.canonical_geometry import canonical_response_vector
from nostos.features.universal import analyze_response_geometry
from nostos.validation.phantoms import generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


def _geometry(image):
    return analyze_response_geometry(image, spacing_um=(1, 1), mask=None,
                                     scales_um=(2, 4, 8, 16), separations_um=(1, 2, 4, 8, 16, 24))


def test_rotation_quotient_reduces_distance_without_mutating_raw_direction():
    phantom = generate_phantom("orientation", shape=(96, 96), angle_degrees=21, scale_um=16)
    rotated = apply_perturbation(phantom, Perturbation("rotation", 47))
    first, second = _geometry(phantom.image), _geometry(rotated.image)
    raw_first = canonical_response_vector(first, quotient_global_rotation=False)
    raw_second = canonical_response_vector(second, quotient_global_rotation=False)
    canonical_first = canonical_response_vector(first)
    canonical_second = canonical_response_vector(second)
    assert np.linalg.norm(canonical_first - canonical_second) < np.linalg.norm(raw_first - raw_second)
    assert any(surface.measurement == "orientation" for surface in first.responses)


def test_canonical_vector_is_finite_and_deterministic():
    geometry = _geometry(generate_phantom("heterogeneity", shape=(96, 96), seed=44).image)
    first = canonical_response_vector(geometry)
    second = canonical_response_vector(geometry)
    np.testing.assert_array_equal(first, second)
    assert np.isfinite(first).all()
