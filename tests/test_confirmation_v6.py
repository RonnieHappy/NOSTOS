from __future__ import annotations

from nostos.validation.confirmation_v6 import evaluate_v6_confirmation


def _row(
    case: int,
    *,
    structure: str,
    endpoint: str,
    score: float,
    qc_score: float,
    invalid: bool,
) -> dict:
    return {
        "case_id": f"{structure}|field_{case // 4}|{case}|{endpoint}",
        "pair_id": f"{structure}|field_{case // 4}|pair_{case}",
        "reference_group_id": f"{structure}|field_{case // 4}",
        "structure": structure,
        "endpoint": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": False,
        "hard_abstention_reasons": [],
        "invalid": invalid,
        "scores": {
            "full_contract": score,
            "conventional_acquisition_qc": qc_score,
            "full_contract_without_sampling": score,
            "full_contract_without_perturbation": qc_score,
            "full_contract_without_identifiability": score,
            "always_emit": 0.0,
        },
    }


def test_confirmation_uses_frozen_family_thresholds_without_refit() -> None:
    rows = []
    for structure in ("Microtubules", "F-actin_linear", "F-actin_nonlinear"):
        for case in range(32):
            invalid = case >= 30
            rows.append(
                _row(
                    case,
                    structure=structure,
                    endpoint="tensor_coherence",
                    score=0.2 if not invalid else 0.8,
                    qc_score=0.2 if case < 31 else 0.8,
                    invalid=invalid,
                )
            )
    thresholds = {"tensor_coherence": 0.5}
    config = {
        "endpoint_families": {"tensor_coherence": ["tensor_coherence"]},
        "policy_thresholds": {
            "full_contract": thresholds,
            "conventional_acquisition_qc": thresholds,
            "full_contract_without_sampling": thresholds,
            "full_contract_without_perturbation": thresholds,
            "full_contract_without_identifiability": thresholds,
        },
        "initial_confirmation": {
            "structures": ["Microtubules", "F-actin_linear", "F-actin_nonlinear"],
            "minimum_total_reference_fields": 24,
            "target_observed_risk": 0.1,
            "maximum_cluster_bootstrap_risk_upper95": 0.15,
            "minimum_overall_coverage": 0.8,
            "minimum_structure_family_coverage": 0.7,
            "minimum_aurc_reduction_fraction_vs_always_emit": 0.2,
            "bootstrap_replicates": 500,
            "bootstrap_seed": 4,
            "incremental_comparator_gate": {
                "maximum_full_minus_qc_risk": 0.0,
                "maximum_full_coverage_loss_vs_qc": 0.1,
                "minimum_invalid_enrichment_among_qc_only_rejections": 2.0,
            },
        },
    }
    result = evaluate_v6_confirmation(rows, config=config)
    assert result["confirmation_thresholds_refit"] is False
    assert result["safety_gate_passed"] is True
    assert result["policies"]["full_contract"]["invalid"] == 0
