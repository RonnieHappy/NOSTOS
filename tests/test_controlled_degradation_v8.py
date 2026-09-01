from __future__ import annotations

import numpy as np

from nostos.validation.controlled_degradation_v8 import (
    apply_controlled_degradation,
    deterministic_condition_seed,
    evaluate_controlled_degradation_pilot,
)


def test_condition_seed_is_stable_and_identifier_specific() -> None:
    first = deterministic_condition_seed(123, pair_id="pair-a", condition_id="noise")
    assert first == deterministic_condition_seed(
        123, pair_id="pair-a", condition_id="noise"
    )
    assert first != deterministic_condition_seed(
        123, pair_id="pair-b", condition_id="noise"
    )


def test_degradations_preserve_shape_and_are_deterministic() -> None:
    y, x = np.mgrid[:48, :64]
    image = np.sin(x / 4.0) + np.cos(y / 7.0)
    specifications = [
        {"operation": "identity"},
        {"operation": "gamma", "gamma": 0.5},
        {"operation": "gaussian_blur", "sigma_input_pixels": 2.0},
        {
            "operation": "anisotropic_gaussian_blur",
            "sigma_yx_input_pixels": [0.5, 3.0],
        },
        {"operation": "downsample_restore", "factor": 4},
        {
            "operation": "gaussian_noise",
            "sigma_fraction_robust_range": 0.08,
        },
    ]
    for specification in specifications:
        first = apply_controlled_degradation(image, specification, seed=91)
        second = apply_controlled_degradation(image, specification, seed=91)
        assert first.shape == image.shape
        assert np.isfinite(first).all()
        np.testing.assert_array_equal(first, second)


def _row(
    *,
    field: str,
    condition: str,
    family: str,
    endpoint: str,
    invalid: bool,
    full_score: float,
) -> dict:
    return {
        "case_id": f"{field}|{condition}|{endpoint}",
        "pair_id": f"{field}|{condition}",
        "reference_group_id": field,
        "structure": "test_structure",
        "endpoint_family": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "invalid": invalid,
        "hard_abstention_reasons": [],
        "scores": {
            "full_contract": full_score,
            "conventional_acquisition_qc": 0.2,
        },
        "support_components": {
            "acquisition_qc": 0.2,
            "physical_sampling": 0.0,
            "perturbation_stability": full_score,
            "resolution_margin": 0.0,
        },
        "metadata": {
            "degradation_id": condition,
            "degradation_family": family,
            "severity_rank": 0 if family == "negative_control" else 1,
        },
    }


def test_pilot_evaluator_detects_selective_risk_reduction() -> None:
    rows = []
    for field in ("field-1", "field-2"):
        for endpoint in ("tensor_coherence", "tensor_orientation_distribution"):
            rows.append(
                _row(
                    field=field,
                    condition="clean",
                    family="negative_control",
                    endpoint=endpoint,
                    invalid=False,
                    full_score=0.2,
                )
            )
            rows.append(
                _row(
                    field=field,
                    condition="blur",
                    family="isotropic_blur",
                    endpoint=endpoint,
                    invalid=True,
                    full_score=2.0,
                )
            )
    gates = {
        "bootstrap_replicates": 100,
        "bootstrap_seed": 17,
        "minimum_negative_control_coverage": 0.8,
        "maximum_negative_control_risk": 0.1,
        "minimum_overall_full_contract_coverage": 0.3,
        "maximum_overall_full_contract_risk": 0.1,
        "maximum_cluster_bootstrap_risk_upper95": 0.25,
        "minimum_comparator_invalid_emissions": 2,
        "minimum_invalid_reference_fields": 2,
        "minimum_relative_risk_reduction_vs_qc": 0.25,
        "minimum_invalid_fraction_among_qc_only_rejections": 0.25,
        "minimum_bootstrap_probability_full_better": 0.9,
        "require_positive_comparator_minus_full_aurc": True,
        "require_nonhigher_full_risk_in_each_assessable_structure": True,
    }
    result = evaluate_controlled_degradation_pilot(rows, gates=gates)
    assert result["status"] == "pass"
    assert result["passes"] is True
    assert result["overall"]["full_contract"]["risk"] == 0.0
    assert result["overall"]["conventional_acquisition_qc"]["risk"] == 0.5

