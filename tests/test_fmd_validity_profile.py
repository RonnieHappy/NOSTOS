from __future__ import annotations

import numpy as np

from nostos.validation.fmd_validity_profile import (
    _convert_dimensionless_rows,
    attach_declared_capture_stability_score,
    measure_selected_with_mild_probes,
)
from nostos.validation.paired_acquisition_support import (
    audit_pair_registration,
    evaluate_precomputed_pair,
    measure_with_mild_probes,
)


def _config() -> dict:
    return {
        "measurement": {
            "included_endpoints": [
                "tensor_orientation",
                "tensor_coherence",
                "spectral_anisotropy",
                "spectral_entropy",
            ],
            "endpoint_families": {
                "tensor_orientation_distribution": ["tensor_orientation"],
                "tensor_coherence": ["tensor_coherence"],
                "spectral_order": ["spectral_anisotropy", "spectral_entropy"],
            },
        }
    }


def _internal_config() -> dict:
    return {
        "physical_scales_um": [4.0, 8.0, 16.0],
        "minimum_samples_per_scale": 4.0,
        "spectral_analysis": {
            "minimum_fraction_of_effective_input_nyquist": 0.02,
            "maximum_fraction_of_effective_input_nyquist": 0.9,
        },
        "reference_eligibility": {
            "minimum_orientation_resultant": 0.15,
            "minimum_spectral_orientation_anisotropy": 0.15,
            "maximum_cross_estimator_orientation_disagreement_degrees": 20.0,
            "maximum_reference_orientation_probe_drift_degrees": 5.0,
            "maximum_reference_scalar_probe_drift": 0.1,
            "minimum_normalized_curve_energy": 1e-6,
        },
        "invalidity_tolerances": {
            "tensor_orientation_degrees": 10.0,
            "tensor_coherence_absolute": 0.15,
            "spectral_anisotropy_absolute": 0.15,
            "spectral_entropy_absolute": 0.1,
            "spectral_scale_relative": 0.25,
            "normalized_response_curve_distance": 0.25,
            "winning_scale_log2_absolute": 0.5,
            "normalized_variogram_curve_distance": 0.25,
            "variogram_range_relative": 0.5,
        },
    }


def _rows(base, probes, reference, reference_probes, registration) -> list[dict]:
    rows = evaluate_precomputed_pair(
        pair_id="pair",
        reference_group_id="field",
        structure="structure",
        effective_input_spacing_um=1.0,
        registration=registration,
        input_base=base,
        input_probes=probes,
        reference_base=reference,
        reference_probes=reference_probes,
        config=_internal_config(),
        metadata={},
    )
    return _convert_dimensionless_rows(rows, config=_config(), split="development")


def test_selected_fmd_path_is_numerically_identical_for_retained_endpoints() -> None:
    rng = np.random.default_rng(12)
    reference_image = rng.normal(size=(64, 64))
    input_image = reference_image + rng.normal(scale=0.1, size=(64, 64))
    scales = (4.0, 8.0, 16.0)
    band = (10.0, 450.0)
    registration = audit_pair_registration(
        input_image,
        reference_image,
        reference_spacing_um=1.0,
        effective_input_spacing_um=1.0,
    )
    full_input = measure_with_mild_probes(
        input_image,
        grid_spacing_um=1.0,
        effective_spacing_um=1.0,
        scales_um=scales,
        spectral_band_cycles_per_mm=band,
    )
    full_reference = measure_with_mild_probes(
        reference_image,
        grid_spacing_um=1.0,
        effective_spacing_um=1.0,
        scales_um=scales,
        spectral_band_cycles_per_mm=band,
    )
    selected_input = measure_selected_with_mild_probes(
        input_image, scales_px=scales, spectral_band_cycles_per_mm=band
    )
    selected_reference = measure_selected_with_mild_probes(
        reference_image, scales_px=scales, spectral_band_cycles_per_mm=band
    )
    full_rows = _rows(*full_input, *full_reference, registration)
    selected_rows = _rows(*selected_input, *selected_reference, registration)
    assert len(full_rows) == len(selected_rows) == 8
    for full, selected in zip(full_rows, selected_rows, strict=True):
        assert full["case_id"] == selected["case_id"]
        for key in (
            "error",
            "invalid",
            "reference_eligible",
            "reference_probe_instability",
            "hard_abstention",
            "hard_abstention_reasons",
            "scores",
            "support_components",
            "input_measurement",
            "reference_measurement",
        ):
            if isinstance(full[key], float):
                assert selected[key] == full[key]
            else:
                assert selected[key] == full[key]


def test_fmd_conversion_removes_false_physical_unit_labels() -> None:
    row = {
        "endpoint": "tensor_coherence",
        "requested_scale_um": 8.0,
        "development_partition": "score_design",
        "support_components": {"physical_sampling": 0.0, "samples_per_scale": 8.0},
        "scores": {"physical_sampling_only": 0.0},
        "metadata": {},
    }
    converted = _convert_dimensionless_rows([row], config=_config(), split="development")[0]
    assert "requested_scale_um" not in converted
    assert converted["requested_scale_unit"] == "px"
    assert converted["physical_unit_output_eligible"] is False
    assert "physical_sampling" not in converted["support_components"]
    assert "physical_sampling_only" not in converted["scores"]


def test_capture_stability_score_is_reference_label_blind() -> None:
    config = _config()
    config["measurement"]["input_only_score"] = {
        "score_key": "declared_capture_stability_contract",
        "formula": "capture_weight * max(0, sqrt(target_averaged_captures / averaged_captures) - 1) + perturbation_weight * perturbation_stability",
        "target_averaged_captures": 16,
        "capture_weight": 1.0,
        "perturbation_weight": 1.0,
    }
    first = {
        "invalid": False,
        "reference_measurement": 0.2,
        "metadata": {"averaged_captures": 4},
        "support_components": {"perturbation_stability": 0.3},
        "scores": {},
    }
    second = {
        **first,
        "invalid": True,
        "reference_measurement": 0.9,
        "metadata": dict(first["metadata"]),
        "support_components": dict(first["support_components"]),
        "scores": {},
    }
    attach_declared_capture_stability_score(first, config=config)
    attach_declared_capture_stability_score(second, config=config)
    assert first["scores"] == second["scores"]
    assert first["scores"]["declared_capture_stability_contract"] == 1.3
