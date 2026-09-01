from __future__ import annotations

from copy import deepcopy

import pytest

from nostos.validation.conditional_support_profile import (
    apply_conditional_support,
    compile_conditional_support_profile,
    verify_conditional_profile,
)
from nostos.validation.validity_profile_compiler import canonical_sha256


def _risk_map(low: float, high: float) -> dict:
    return {
        "method": "quantile_binned_jeffreys_isotonic",
        "x_thresholds": [0.0, 1.0],
        "y_thresholds": [low, high],
        "training_cases": 40,
        "training_invalid": 10,
        "bins": 2,
        "prior_alpha": 0.5,
        "prior_beta": 0.5,
    }


def _base_profile() -> dict:
    payload = {
        "schema_version": "nostos-validity-profile/1.0",
        "compiler_version": "fixture",
        "protocol_id": "base",
        "status": "operating_point_selected",
        "claim_boundary": {"claim": "fixture"},
        "measurement": {"primary_endpoint_family": "tensor_coherence"},
        "primary_score": "full_contract",
        "score_candidates": ["full_contract", "conventional_acquisition_qc"],
        "primary_endpoint_family": "tensor_coherence",
        "development": {"independent_groups": ["base-only"]},
        "acquisition_stratum_support": None,
        "calibration": {
            "candidates": {
                "full_contract": {
                    "risk_maps": {"tensor_coherence": _risk_map(0.05, 0.9)}
                },
                "conventional_acquisition_qc": {
                    "risk_maps": {"tensor_coherence": _risk_map(0.2, 0.8)}
                },
            }
        },
        "operating_point": {
            "selected": {"predicted_risk_threshold": 0.1}
        },
        "confirmation_gates": {},
        "config_sha256": "fixture",
    }
    payload["content_sha256"] = canonical_sha256(payload)
    return payload


def _rows() -> list[dict]:
    rows = []
    for field in range(1, 5):
        for repeat in range(4):
            for level, scale, invalid in (
                ("avg16", 4.0, False),
                ("avg8", 8.0, True),
            ):
                rows.append(
                    {
                        "case_id": f"WideField_BPAE_R|fov{field}|{repeat}|{level}|{scale}",
                        "reference_group_id": f"WideField_BPAE_R|fov{field}",
                        "endpoint_family": "tensor_coherence",
                        "pair_registration_eligible": True,
                        "reference_eligible": True,
                        "invalid": invalid,
                        "hard_abstention": False,
                        "hard_abstention_reasons": [],
                        "requested_scale_value": scale,
                        "metadata": {
                            "acquisition_level": level,
                            "acquisition_modality": "WideField",
                        },
                        "scores": {
                            "full_contract": 0.0,
                            "conventional_acquisition_qc": 0.0,
                        },
                    }
                )
    return rows


def _config(base: dict) -> dict:
    return {
        "protocol_id": "conditional-fixture",
        "scope": {"claim": "fixture"},
        "source": {"acquisition_modality": "WideField", "sample": "BPAE_R"},
        "selection": {"development_fields": [1, 2, 3, 4]},
        "base_profile": {
            "content_sha256": base["content_sha256"],
            "file_sha256": "f" * 64,
            "primary_score": "full_contract",
            "predicted_risk_threshold": 0.1,
        },
        "conditional_compiler": {
            "cell_dimensions": [
                {"source": "metadata", "key": "acquisition_level"},
                {"source": "row", "key": "requested_scale_value"},
            ],
            "minimum_accepted_cases_per_cell": 8,
            "minimum_accepted_independent_groups_per_cell": 4,
            "maximum_observed_risk_per_cell": 0.1,
            "maximum_cluster_bootstrap_risk_upper95_per_cell": 0.3,
            "bootstrap_replicates": 100,
            "bootstrap_seed": 11,
            "development_gates": {
                "minimum_coverage": 0.2,
                "maximum_observed_risk": 0.1,
                "maximum_cluster_bootstrap_risk_upper95": 0.3,
            },
        },
        "confirmation_gates": {},
    }


def test_conditional_support_blocks_a_pooled_unsafe_cell() -> None:
    base = _base_profile()
    profile, audit, scored = compile_conditional_support_profile(
        _rows(), config=_config(base), base_profile=base
    )
    verify_conditional_profile(profile)
    assert profile["status"] == "operating_point_selected"
    assert [cell["values"] for cell in profile["supported_cells"]] == [
        ["avg16", 4.0]
    ]
    assert [cell["values"] for cell in profile["unsupported_cells"]] == [
        ["avg8", 8.0]
    ]
    assert audit["development_operating_point"]["risk"] == 0.0
    unsafe = [row for row in scored if row["metadata"]["acquisition_level"] == "avg8"]
    assert unsafe and all(row["candidate_hard_abstention"] for row in unsafe)


def test_unseen_conditional_cell_hard_abstains_and_tampering_fails() -> None:
    base = _base_profile()
    profile, _, _ = compile_conditional_support_profile(
        _rows(), config=_config(base), base_profile=base
    )
    unseen = deepcopy(_rows()[0])
    unseen["case_id"] = "unseen"
    unseen["metadata"]["acquisition_level"] = "avg4"
    applied = apply_conditional_support(
        [unseen], base_profile=base, conditional_profile=profile
    )
    assert applied[0]["candidate_hard_abstention"] is True
    assert applied[0]["calibrated_risk"] == 1.0
    damaged = deepcopy(profile)
    damaged["supported_cells"] = []
    with pytest.raises(ValueError, match="content hash mismatch"):
        verify_conditional_profile(damaged)
