import numpy as np

from nostos.features.response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    local_thickness_response,
    structure_tensor_response,
)
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.phantoms import generate_phantom


def test_structure_tensor_recovers_programmed_orientation():
    phantom = generate_phantom("orientation", angle_degrees=37, scale_um=24)
    response = structure_tensor_response(phantom.image, spacing_um=(1, 1), scales_um=(1, 2, 4))
    assert max(axial_angular_error_degrees(value, 37) for value in response.orientation_degrees) < 1
    assert min(response.coherency) > 0.8


def test_hessian_response_is_finite_and_scale_resolved():
    phantom = generate_phantom("blob", scale_um=20)
    response = hessian_morphology_response(phantom.image, spacing_um=(1, 1), scales_um=(2, 4, 6, 8, 10))
    assert response.winning_class in {"blob", "tube"}
    assert response.winning_scale_um in response.scales_um
    assert np.isfinite(response.blob).all()


def test_3d_hessian_recovers_each_analytic_morphology():
    for morphology in ("blob", "tube", "sheet"):
        phantom = generate_phantom(morphology, shape=(48, 48, 48), spacing_um=(1, 1, 1), scale_um=12)
        response = hessian_morphology_response(phantom.image, spacing_um=(1, 1, 1), scales_um=(1.5, 3, 4.5, 6))
        assert response.winning_class == morphology


def test_distance_thickness_is_in_physical_units():
    phantom = generate_phantom("sheet", scale_um=20)
    response = local_thickness_response(phantom.mask, spacing_um=(1, 1))
    assert 19 <= response.p95_thickness_um <= 23
    scaled = local_thickness_response(phantom.mask, spacing_um=(2, 2))
    assert scaled.p95_thickness_um == 2 * response.p95_thickness_um


def test_network_erosion_curve_tracks_survival():
    phantom = generate_phantom("network", scale_um=20)
    response = erosion_survival_response(phantom.mask, spacing_um=(1, 1), thresholds_um=(0, 2, 4, 8))
    assert response.surviving_fraction[0] == 1
    assert all(a >= b for a, b in zip(response.surviving_fraction, response.surviving_fraction[1:]))
    assert len(response.component_count) == 4


def test_network_erosion_uses_boundary_not_background_center_distance():
    mask = np.ones((9, 9), dtype=bool)
    mask[[0, -1], :] = False
    mask[:, [0, -1]] = False
    response = erosion_survival_response(mask, spacing_um=(2.0, 2.0), thresholds_um=(0.0, 2.0), boundary_corrected=True)
    assert response.surviving_fraction[1] < 1.0


def test_directional_variogram_detects_anisotropy():
    phantom = generate_phantom("heterogeneity", correlation_length_um=12, anisotropy_ratio=3)
    response = directional_variogram(phantom.image, spacing_um=(1, 1), separations_um=(1, 2, 4, 8, 12, 16, 24, 32))
    assert response.estimated_range_horizontal_um != response.estimated_range_vertical_um
    assert len(response.horizontal) == 8
