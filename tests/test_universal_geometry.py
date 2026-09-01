import numpy as np
import pytest
from pathlib import Path

from nostos.core.measurement_profile import MeasurementProfile
from nostos.features.universal import analyze_response_geometry
from nostos.validation.phantoms import generate_phantom


def _historical_v1_profile() -> MeasurementProfile:
    root = Path(__file__).resolve().parents[1]
    pilot_audit = root / "outputs" / "nostos0-biosr-small-pilot-v5-audit" / "pilot_audit.json"
    if not pilot_audit.is_file():
        pytest.skip(
            "The private-path-bearing historical pilot audit is intentionally omitted from the portable release."
        )
    return MeasurementProfile.from_path(
        root / "configs" / "biosr_widefield_measurement_profile_v1.locked.json"
    )


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
    assert result.status in {"valid", "review"}
    assert result.to_dict()["calibration"]["specimen_reference"] == 100
    assert result.to_dict()["evidence_status"] == "unvalidated"


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


def test_spectral_measurements_are_separate_and_unit_safe():
    phantom = generate_phantom("orientation", angle_degrees=37, scale_um=24)
    result = analyze_response_geometry(phantom.image, spacing_um=(1, 1), mask=phantom.mask)
    surfaces = {(item.module, item.measurement): item for item in result.responses}
    assert ("spectral", "summary") not in surfaces
    assert surfaces[("spectral", "orientation")].amplitude_unit == "degrees"
    assert surfaces[("spectral", "anisotropy")].amplitude_unit == "dimensionless"
    assert surfaces[("spectral", "angular_entropy")].amplitude_unit == "dimensionless"
    assert surfaces[("spectral", "characteristic_wavelength")].amplitude_unit == "um"


def test_measurement_profile_disables_failed_scalar_and_marks_developmental_evidence():
    profile = _historical_v1_profile()
    assert len(profile.verified_artifacts) == 3
    phantom = generate_phantom("orientation", angle_degrees=37, scale_um=24)
    result = analyze_response_geometry(
        phantom.image,
        spacing_um=(0.0626, 0.0626),
        mask=phantom.mask,
        measurement_profile=profile,
    )
    surfaces = {(item.module, item.measurement): item for item in result.responses}
    assert ("spectral", "characteristic_wavelength") not in surfaces
    assert any(
        item.code == "ACQUISITION_PROFILE_DISABLED"
        and item.requested_measurement == "spectral.characteristic_wavelength"
        for item in result.abstentions
    )
    assert surfaces[("spectral", "anisotropy")].evidence_status == "developmental"
    assert surfaces[("tensor", "coherency")].evidence_status == "developmental"
    assert surfaces[("hessian", "blob_shape")].evidence_status == "developmental"
    assert surfaces[("hessian", "blob_response")].evidence_status == "unvalidated"
    assert surfaces[("spatial", "variogram_horizontal_shape")].evidence_status == "developmental"
    assert surfaces[("spatial", "variogram_horizontal")].evidence_status == "unvalidated"
    assert ("hessian", "blob_scale") not in surfaces
    assert ("hessian", "tube_scale") not in surfaces
    assert sum(item.code == "ACQUISITION_PROFILE_DISABLED" for item in result.abstentions) == 3
    profile_provenance = result.provenance["measurement_profile"]
    assert profile_provenance["machine_compatibility"] == "compatible"
    assert tuple(item.axes[0].values for item in result.responses if item.measurement == "blob_shape")[0] == profile.analysis_scales
    orientation = surfaces[("tensor", "orientation")]
    assert orientation.validity_mask is not None
    assert len(orientation.validity_mask) == len(orientation.values)


def test_incompatible_profile_cannot_confer_evidence_or_disable_measurements():
    profile = _historical_v1_profile()
    phantom = generate_phantom("orientation", angle_degrees=37, scale_um=24)
    result = analyze_response_geometry(
        phantom.image,
        spacing_um=(1.0, 1.0),
        mask=phantom.mask,
        measurement_profile=profile,
    )
    surfaces = {(item.module, item.measurement): item for item in result.responses}
    assert all(item.evidence_status == "unvalidated" for item in result.responses)
    assert ("spectral", "characteristic_wavelength") in surfaces
    assert ("hessian", "blob_scale") in surfaces
    assert any(item.code == "ACQUISITION_PROFILE_INCOMPATIBLE" for item in result.abstentions)
    assert not any(item.code == "ACQUISITION_PROFILE_DISABLED" for item in result.abstentions)


def test_micrometre_and_millimetre_inputs_preserve_values_and_units():
    phantom = generate_phantom("orientation", angle_degrees=37, scale_um=24)
    in_um = analyze_response_geometry(phantom.image, spacing_um=(1.0, 1.0), spatial_unit="um")
    in_mm = analyze_response_geometry(phantom.image, spacing_um=(0.001, 0.001), spatial_unit="mm")
    um_surfaces = {(item.module, item.measurement): item for item in in_um.responses}
    mm_surfaces = {(item.module, item.measurement): item for item in in_mm.responses}
    assert np.isclose(
        um_surfaces[("spectral", "anisotropy")].values[0],
        mm_surfaces[("spectral", "anisotropy")].values[0],
    )
    wavelength_um = um_surfaces[("spectral", "characteristic_wavelength")]
    wavelength_mm = mm_surfaces[("spectral", "characteristic_wavelength")]
    assert wavelength_um.amplitude_unit == "um"
    assert wavelength_mm.amplitude_unit == "mm"
    assert np.isclose(wavelength_um.values[0] / 1000.0, wavelength_mm.values[0])


def test_validated_v26_spatial_endpoint_emits_only_when_supported():
    phantom = generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=812345,
        correlation_length_um=18.0,
        anisotropy_ratio=2.5,
    )
    result = analyze_response_geometry(
        phantom.image,
        spacing_um=(1.0, 1.0),
        specimen_direction_degrees=17.0,
    )
    surfaces = {(item.module, item.measurement): item for item in result.responses}
    ratio = surfaces[("spatial", "gradient_anisotropy_ratio_v2_6")].values[0]
    image_axis = surfaces[("spatial", "gradient_axis_image_v2_6")].values[0]
    specimen_axis = surfaces[("spatial", "gradient_axis_specimen_v2_6")].values[0]
    assert ratio == pytest.approx(2.5, rel=0.25)
    assert specimen_axis == pytest.approx((image_axis + 17.0) % 180.0)
    assert not any(
        item.code == "SPATIAL_ANISOTROPY_UNSUPPORTED"
        for item in result.abstentions
    )
    method = result.provenance["validated_core_v2_6"]
    assert method["confirmation_sha256"] == (
        "f64b85c86f8e415526d2938618cdbda4974bad0094082c44713f52230f2001fc"
    )


def test_validated_v26_spatial_endpoint_refuses_under_supported_field():
    phantom = generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=2084179,
        correlation_length_um=34.0,
        anisotropy_ratio=1.7,
    )
    result = analyze_response_geometry(phantom.image, spacing_um=(1.0, 1.0))
    measurements = {
        (item.module, item.measurement) for item in result.responses
    }
    assert ("spatial", "gradient_characteristic_spans_v2_6") in measurements
    assert ("spatial", "gradient_anisotropy_ratio_v2_6") not in measurements
    assert any(
        item.code == "SPATIAL_ANISOTROPY_UNSUPPORTED"
        and "fewer_than_2_25_characteristic_spans" in item.reason
        for item in result.abstentions
    )
