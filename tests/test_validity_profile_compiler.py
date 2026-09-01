from __future__ import annotations

from copy import deepcopy

import pytest

from nostos.validation.validity_profile_compiler import (
    apply_score_profile,
    assign_group_folds,
    audit_validity_profile,
    candidate_hard_abstention,
    compile_validity_profile,
    verify_profile,
)


def _config() -> dict:
    return {
        "protocol_id": "test-profile-v1",
        "scope": {
            "study_type": "computation_only",
            "claim": "test",
            "excluded_claims": ["clinical"],
        },
        "measurement": {"primary_endpoint_family": "tensor_coherence"},
        "compiler": {
            "primary_score": "full_contract",
            "score_candidates": [
                "full_contract",
                "conventional_acquisition_qc",
                "full_contract_without_qc",
            ],
            "folds": 3,
            "fold_seed": 17,
            "calibration_bins": 4,
            "prior_alpha": 0.5,
            "prior_beta": 0.5,
            "operating_point": {
                "target_observed_risk": 0.1,
                "maximum_cluster_bootstrap_risk_upper95": 0.25,
                "minimum_coverage": 0.25,
                "bootstrap_replicates": 100,
                "bootstrap_seed": 19,
            },
        },
        "confirmation_gates": {
            "minimum_independent_groups": 6,
            "minimum_coverage": 0.25,
            "maximum_observed_risk": 0.15,
            "maximum_cluster_bootstrap_risk_upper95": 0.35,
            "minimum_relative_risk_reduction_vs_acquisition_qc": 0.2,
            "minimum_invalid_acquisition_qc_emissions": 5,
            "require_positive_aurc_difference": True,
            "require_aurc_bootstrap_ci_lower_above_zero": True,
            "bootstrap_replicates": 200,
            "bootstrap_seed": 23,
        },
    }


def _rows(prefix: str) -> list[dict]:
    rows = []
    for group_index in range(6):
        for index in range(20):
            invalid = index >= 10
            full = (0.05 + index / 200) if not invalid else (0.8 + index / 200)
            rows.append(
                {
                    "case_id": f"{prefix}{group_index}|{index:02d}",
                    "reference_group_id": f"{prefix}{group_index}",
                    "endpoint_family": "tensor_coherence",
                    "pair_registration_eligible": True,
                    "reference_eligible": True,
                    "invalid": invalid,
                    "hard_abstention": False,
                    "hard_abstention_reasons": [],
                    "group_stratum": "modality-a" if group_index % 2 else "modality-b",
                    "scores": {
                        "full_contract": full,
                        "conventional_acquisition_qc": (
                            (index * 7 + group_index) % 20
                        )
                        / 20,
                        "full_contract_without_qc": full,
                    },
                }
            )
    return rows


def test_group_folds_never_split_an_independent_group() -> None:
    rows = _rows("d")
    assignments = assign_group_folds(rows, folds=3, seed=7)
    assert set(assignments.values()) == {0, 1, 2}
    for group_index in range(6):
        group_rows = [row for row in rows if row["reference_group_id"] == f"d{group_index}"]
        assert {assignments[row["reference_group_id"]] for row in group_rows} == {
            assignments[f"d{group_index}"]
        }


def test_comparator_does_not_inherit_full_contract_hard_gates() -> None:
    row = {
        "hard_abstention_reasons": [
            "input_orientation_resultant_below_minimum",
            "acquisition_qc_abstain",
        ]
    }
    assert candidate_hard_abstention(row, "full_contract")
    assert candidate_hard_abstention(row, "conventional_acquisition_qc")
    assert candidate_hard_abstention(row, "full_contract_without_qc")
    row["hard_abstention_reasons"] = ["acquisition_qc_abstain"]
    assert not candidate_hard_abstention(row, "full_contract_without_qc")
    row["hard_abstention_reasons"] = ["input_orientation_resultant_below_minimum"]
    assert not candidate_hard_abstention(row, "conventional_acquisition_qc")


def test_compiler_cross_fits_and_emits_hash_verifiable_profile() -> None:
    profile, audit, scored = compile_validity_profile(_rows("d"), config=_config())
    assert profile["status"] == "operating_point_selected"
    verify_profile(profile)
    assert audit["status"] == profile["status"]
    assert len(scored) == 120
    assert all(len(row["cross_fitted_calibrated_risk"]) == 3 for row in scored)
    damaged = deepcopy(profile)
    damaged["primary_score"] = "changed"
    with pytest.raises(ValueError, match="content hash mismatch"):
        verify_profile(damaged)


def test_confirmation_is_applied_without_refitting_and_beats_qc() -> None:
    profile, _, _ = compile_validity_profile(_rows("d"), config=_config())
    audit, scored = audit_validity_profile(_rows("c"), profile=profile)
    assert audit["status"] == "pass"
    assert audit["confirmation"]["development_group_overlap"] == []
    assert audit["primary_operating_point"]["risk"] == 0.0
    assert audit["acquisition_qc_matched_count"]["invalid"] >= 5
    assert audit["acquisition_qc_matched_count"]["tie_robust_risk_bounds"] is not None
    assert (
        audit["relative_risk_reduction_vs_acquisition_qc"]
        ["conservative_lower_bound_over_boundary_tie"]
        >= 0.2
    )
    assert audit["risk_coverage"]["cluster_bootstrap_aurc_difference"]["observed"] > 0
    assert len(scored) == 120


def test_confirmation_group_overlap_fails_closed() -> None:
    profile, _, _ = compile_validity_profile(_rows("d"), config=_config())
    with pytest.raises(ValueError, match="group leakage"):
        audit_validity_profile(_rows("d"), profile=profile)


def test_apply_profile_uses_serialized_map_and_candidate_specific_hard_gate() -> None:
    profile, _, _ = compile_validity_profile(_rows("d"), config=_config())
    rows = _rows("c")[:2]
    rows[0]["hard_abstention"] = True
    rows[0]["hard_abstention_reasons"] = [
        "input_orientation_resultant_below_minimum"
    ]
    applied = apply_score_profile(
        rows,
        score_key="conventional_acquisition_qc",
        risk_maps=profile["calibration"]["candidates"][
            "conventional_acquisition_qc"
        ]["risk_maps"],
    )
    assert applied[0]["candidate_hard_abstention"] is False
    assert 0.0 <= applied[0]["calibrated_risk"] <= 1.0


def test_cross_fitting_adapts_fold_count_for_sparse_endpoint_family() -> None:
    rows = _rows("d")
    for group_index in range(3):
        for index in range(4):
            invalid = index >= 2
            rows.append(
                {
                    "case_id": f"sparse-{group_index}|{index}",
                    "reference_group_id": f"d{group_index}",
                    "endpoint_family": "sparse_orientation",
                    "pair_registration_eligible": True,
                    "reference_eligible": True,
                    "invalid": invalid,
                    "hard_abstention": False,
                    "hard_abstention_reasons": [],
                    "group_stratum": "sparse",
                    "scores": {
                        "full_contract": 0.1 if not invalid else 0.9,
                        "conventional_acquisition_qc": 0.5,
                        "full_contract_without_qc": 0.1 if not invalid else 0.9,
                    },
                }
            )
    profile, _, scored = compile_validity_profile(rows, config=_config())
    assert profile["status"] == "operating_point_selected"
    sparse = [row for row in scored if row["endpoint_family"] == "sparse_orientation"]
    assert len(sparse) == 12
    assert {
        row["calibration_fold"]["full_contract"] for row in sparse
    } == {0, 1, 2}


def test_underrepresented_or_unseen_acquisition_strata_fail_closed() -> None:
    config = _config()
    config["compiler"]["acquisition_stratum_support"] = {
        "metadata_key": "acquisition_modality",
        "minimum_independent_development_groups": 2,
    }
    rows = _rows("d")
    for row in rows:
        group_index = int(str(row["reference_group_id"])[1:])
        row["metadata"] = {
            "acquisition_modality": "supported-a" if group_index < 5 else "singleton-b"
        }

    profile, _, scored = compile_validity_profile(rows, config=config)

    support = profile["acquisition_stratum_support"]
    assert support["supported_strata"] == ["supported-a"]
    assert support["unsupported_strata"] == ["singleton-b"]
    singleton_rows = [
        row
        for row in scored
        if row["metadata"]["acquisition_modality"] == "singleton-b"
    ]
    assert singleton_rows
    assert all(
        row["candidate_hard_abstention"]["full_contract"] for row in singleton_rows
    )
    assert all(
        row["cross_fitted_calibrated_risk"]["full_contract"] == 1.0
        for row in singleton_rows
    )

    confirmation = _rows("c")[:2]
    for row in confirmation:
        row["metadata"] = {"acquisition_modality": "never-seen-c"}
    applied = apply_score_profile(
        confirmation,
        score_key="full_contract",
        risk_maps=profile["calibration"]["candidates"]["full_contract"][
            "risk_maps"
        ],
        stratum_support=support,
    )
    assert all(row["candidate_hard_abstention"] for row in applied)
    assert all(row["calibrated_risk"] == 1.0 for row in applied)
    assert all(
        row["profile_hard_abstention_reason"]
        == "acquisition_stratum_underrepresented_in_development"
        for row in applied
    )
