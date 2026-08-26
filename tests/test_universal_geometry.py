import numpy as np

from nostos.features.universal import analyze_response_geometry
from nostos.validation.phantoms import generate_phantom


def test_universal_analyzer_emits_shared_geometry():
    phantom = generate_phantom("network", scale_um=16)
    result = analyze_response_geometry(
        phantom.image,
        spacing_um=(1, 1),
        mask=phantom.mask,
        specimen_reference_um=100,
    )
    modules = {response.module for response in result.responses}
    assert {"spectral", "tensor", "hessian", "geometry", "network", "spatial"} <= modules
    assert result.status == "valid"
    assert result.to_dict()["calibration"]["specimen_reference"] == 100


def test_universal_analyzer_abstains_transparently_without_mask():
    phantom = generate_phantom("orientation")
    result = analyze_response_geometry(phantom.image, spacing_um=(1, 1))
    assert result.status == "review"
    assert any(item.code == "MASK_NOT_SUPPLIED" for item in result.abstentions)


def test_low_coverage_mask_is_not_silently_measured():
    phantom = generate_phantom("orientation")
    mask = np.zeros_like(phantom.image, dtype=bool)
    mask[:2, :2] = True
    result = analyze_response_geometry(phantom.image, spacing_um=(1, 1), mask=mask)
    assert any(item.code == "MASK_COVERAGE_LOW" for item in result.abstentions)
