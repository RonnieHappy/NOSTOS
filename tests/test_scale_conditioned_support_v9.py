from __future__ import annotations

import pytest

from nostos.validation.scale_conditioned_support_v9 import (
    attach_v9_scale_conditioned_score,
    evaluate_v9_scale_conditioned_confirmation,
    scale_conditioned_acquisition_support,
)


def _row(endpoint: str, samples: float = 4.0) -> dict:
    return {
        "endpoint_family": endpoint,
        "support_components": {
            "acquisition_qc": 0.3,
            "physical_sampling": 0.0,
            "perturbation_stability": 0.1,
            "measurement_identifiability": 0.0,
            "samples_per_scale": samples,
        },
        "scores": {"full_contract": 0.8},
        "metadata": {},
    }


def test_scale_conditioned_support_relaxes_at_larger_supported_scales() -> None:
    small = scale_conditioned_acquisition_support(
        _row("tensor_coherence", 4.0),
        minimum_samples_per_scale=4.0,
        exponent=0.5,
        acceptance_boundary=0.3,
    )
    large = scale_conditioned_acquisition_support(
        _row("tensor_coherence", 16.0),
        minimum_samples_per_scale=4.0,
        exponent=0.5,
        acceptance_boundary=0.3,
    )
    assert small["normalized_score"] == 1.0
    assert large["normalized_score"] == 0.5


def test_v9_replaces_only_coherence_acceptance_score() -> None:
    rows = [
        _row("tensor_coherence"),
        _row("tensor_orientation_distribution"),
    ]
    attached = attach_v9_scale_conditioned_score(
        rows,
        minimum_samples_per_scale=4.0,
        exponent=0.5,
        acceptance_boundary=0.2,
    )
    assert attached[0]["scores"]["full_contract_v7"] == 0.8
    assert attached[0]["scores"]["full_contract"] == pytest.approx(1.5)
    assert attached[1]["scores"]["full_contract"] == 0.8
    assert attached[1]["metadata"]["v9_scale_conditioned_support"] is None


def _evaluation_row(
    *, field: str, condition: str, invalid: bool, full_score: float
) -> dict:
    return {
        "case_id": f"{field}|{condition}|coherence",
        "pair_id": f"{field}|{condition}",
        "reference_group_id": field,
        "structure": "test_structure",
        "endpoint_family": "tensor_coherence",
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
            "measurement_identifiability": 0.0,
            "samples_per_scale": 4.0,
        },
        "metadata": {
            "degradation_id": condition,
            "degradation_family": (
                "negative_control" if condition == "clean" else "isotropic_blur"
            ),
            "severity_rank": 0 if condition == "clean" else 1,
        },
    }


def test_v9_confirmation_requires_positive_clustered_evidence() -> None:
    coherence = []
    for field in ("field-1", "field-2"):
        coherence.extend(
            [
                _evaluation_row(
                    field=field,
                    condition="clean",
                    invalid=False,
                    full_score=0.2,
                ),
                _evaluation_row(
                    field=field,
                    condition="blur",
                    invalid=True,
                    full_score=2.0,
                ),
            ]
        )
    orientation = []
    for row in coherence:
        copied = {**row, "scores": dict(row["scores"]), "metadata": dict(row["metadata"])}
        copied["case_id"] = copied["case_id"].replace("coherence", "orientation")
        copied["endpoint_family"] = "tensor_orientation_distribution"
        orientation.append(copied)
    gates = {
        "bootstrap_replicates": 100,
        "bootstrap_seed": 19,
        "minimum_negative_control_coverage": 0.8,
        "maximum_negative_control_risk": 0.1,
        "minimum_overall_coverage": 0.3,
        "maximum_overall_risk": 0.1,
        "maximum_cluster_bootstrap_risk_upper95": 0.25,
        "minimum_comparator_invalid_emissions": 2,
        "minimum_invalid_reference_fields": 2,
        "minimum_relative_risk_reduction_vs_qc": 0.25,
        "minimum_invalid_fraction_among_qc_only_rejections": 0.25,
        "minimum_bootstrap_probability_full_better": 0.9,
    }
    result = evaluate_v9_scale_conditioned_confirmation(
        [*coherence, *orientation], gates=gates
    )
    assert result["status"] == "pass"
    assert result["checks"]["bootstrap_ci_excludes_zero"] is True
