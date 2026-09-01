"""Development utilities for scale-conditioned acquisition support in tensor v9."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping, Sequence
from typing import Any

from nostos.validation.tensor_contract_audit_v7 import (
    incremental_comparator,
    summarize_policy,
)
from nostos.validation.tensor_evidence_v7 import (
    clustered_coherence_aurc_difference,
)


COHERENCE_FAMILY = "tensor_coherence"


def scale_conditioned_acquisition_support(
    row: Mapping[str, Any],
    *,
    minimum_samples_per_scale: float,
    exponent: float,
    acceptance_boundary: float,
) -> dict[str, float]:
    """Convert acquisition risk into requested-scale support.

    The raw evidence is the existing outcome-blind acquisition-QC risk.  Demand
    decreases with the number of physical samples spanning the requested scale.
    The development boundary converts that evidence to the common score boundary
    of one.
    """

    if minimum_samples_per_scale <= 0 or exponent < 0 or acceptance_boundary <= 0:
        raise ValueError("Scale-support parameters are outside their valid domain.")
    components = row["support_components"]
    samples = float(components["samples_per_scale"])
    if samples <= 0:
        raise ValueError("samples_per_scale must be positive.")
    acquisition = float(components["acquisition_qc"])
    raw = acquisition * (minimum_samples_per_scale / samples) ** exponent
    return {
        "raw_scale_conditioned_acquisition_risk": float(raw),
        "acceptance_boundary": float(acceptance_boundary),
        "normalized_score": float(raw / acceptance_boundary),
        "minimum_samples_per_scale": float(minimum_samples_per_scale),
        "exponent": float(exponent),
    }


def attach_v9_scale_conditioned_score(
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_samples_per_scale: float,
    exponent: float,
    acceptance_boundary: float,
) -> list[dict[str, Any]]:
    """Return rows whose coherence acceptance score uses the v9 repair."""

    result: list[dict[str, Any]] = []
    for source in rows:
        row = deepcopy(dict(source))
        row["scores"]["full_contract_v7"] = float(
            row["scores"]["full_contract"]
        )
        if str(row["endpoint_family"]) == COHERENCE_FAMILY:
            support = scale_conditioned_acquisition_support(
                row,
                minimum_samples_per_scale=minimum_samples_per_scale,
                exponent=exponent,
                acceptance_boundary=acceptance_boundary,
            )
            components = row["support_components"]
            base_without_v7_resolution_margin = max(
                float(components["acquisition_qc"]),
                float(components["physical_sampling"]),
                float(components["perturbation_stability"]),
                float(components.get("measurement_identifiability", 0.0)),
            )
            row["support_components"][
                "scale_conditioned_acquisition_support"
            ] = support["normalized_score"]
            row["scores"]["full_contract"] = float(
                max(base_without_v7_resolution_margin, support["normalized_score"])
            )
            row["metadata"]["v9_scale_conditioned_support"] = support
            row["metadata"]["v7_resolution_margin_acceptance_role"] = (
                "diagnostic_only_after_v8_stable_bias_failure"
            )
        else:
            row["metadata"]["v9_scale_conditioned_support"] = None
            row["metadata"]["v7_resolution_margin_acceptance_role"] = (
                "already_diagnostic_only_for_orientation_distribution"
            )
        result.append(row)
    return result


def _candidate_evaluation(
    rows: Sequence[Mapping[str, Any]],
    *,
    gates: Mapping[str, Any],
    draws: int,
    seed: int,
) -> dict[str, Any]:
    coherence = [
        row for row in rows if str(row["endpoint_family"]) == COHERENCE_FAMILY
    ]
    negative = [
        row
        for row in coherence
        if str(row["metadata"]["degradation_family"]) == "negative_control"
    ]
    full = summarize_policy(
        coherence, condition="full_contract", draws=draws, seed=seed
    )
    qc = summarize_policy(
        coherence,
        condition="conventional_acquisition_qc",
        draws=draws,
        seed=seed + 1,
    )
    negative_full = summarize_policy(
        negative, condition="full_contract", draws=draws, seed=seed + 2
    )
    comparator = incremental_comparator(coherence)
    evidence = clustered_coherence_aurc_difference(
        coherence, draws=draws, seed=seed + 3
    )
    relative_reduction = (
        1.0 - float(full["risk"]) / float(qc["risk"])
        if full["risk"] is not None and qc["risk"] is not None and qc["risk"] > 0
        else None
    )
    invalid_fraction = comparator["comparator_only_rejection_risk"]
    directions = []
    full_by = {str(item["structure"]): item for item in full["combinations"]}
    qc_by = {str(item["structure"]): item for item in qc["combinations"]}
    for structure in sorted(full_by):
        full_risk = full_by[structure]["risk"]
        qc_risk = qc_by[structure]["risk"]
        directions.append(
            {
                "structure": structure,
                "full_risk": full_risk,
                "qc_risk": qc_risk,
                "nonhigher": bool(
                    full_risk is not None
                    and qc_risk is not None
                    and float(full_risk) <= float(qc_risk)
                ),
            }
        )
    checks = {
        "negative_control_coverage": (
            negative_full["coverage"]
            >= float(gates["minimum_negative_control_coverage"])
        ),
        "negative_control_risk": (
            negative_full["risk"] is not None
            and negative_full["risk"] <= float(gates["maximum_negative_control_risk"])
        ),
        "overall_coverage": (
            full["coverage"] >= float(gates["minimum_overall_coverage"])
        ),
        "overall_risk": (
            full["risk"] is not None
            and full["risk"] <= float(gates["maximum_overall_risk"])
        ),
        "risk_upper95": (
            full["cluster_bootstrap_risk_upper95"] is not None
            and full["cluster_bootstrap_risk_upper95"]
            <= float(gates["maximum_cluster_bootstrap_risk_upper95"])
        ),
        "relative_risk_reduction": (
            relative_reduction is not None
            and relative_reduction
            >= float(gates["minimum_relative_risk_reduction_vs_qc"])
        ),
        "rejected_invalid_fraction": (
            invalid_fraction is not None
            and invalid_fraction
            >= float(gates["minimum_invalid_fraction_among_qc_only_rejections"])
        ),
        "positive_aurc_difference": (
            evidence["observed"]["comparator_minus_full"] > 0
        ),
        "bootstrap_probability": (
            evidence["bootstrap"]["probability_full_better"] is not None
            and evidence["bootstrap"]["probability_full_better"]
            >= float(gates["minimum_bootstrap_probability_full_better"])
        ),
        "structure_risk_direction": all(item["nonhigher"] for item in directions),
    }
    return {
        "passes": bool(all(checks.values())),
        "checks": checks,
        "full": full,
        "qc": qc,
        "negative_control_full": negative_full,
        "operating_point": {
            **comparator,
            "relative_risk_reduction_vs_qc": relative_reduction,
        },
        "risk_coverage_evidence": evidence,
        "structure_risk_direction": directions,
    }


def calibrate_v9_scale_conditioned_support(
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_samples_per_scale: float,
    primary_exponent: float,
    candidate_boundaries: Sequence[float],
    sensitivity_exponents: Sequence[float],
    gates: Mapping[str, Any],
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Select the most permissive passing boundary on v8 development evidence."""

    boundaries = sorted({float(value) for value in candidate_boundaries})
    if not boundaries:
        raise ValueError("At least one candidate boundary is required.")
    candidates = []
    for offset, boundary in enumerate(boundaries):
        attached = attach_v9_scale_conditioned_score(
            rows,
            minimum_samples_per_scale=minimum_samples_per_scale,
            exponent=primary_exponent,
            acceptance_boundary=boundary,
        )
        evaluation = _candidate_evaluation(
            attached,
            gates=gates,
            draws=draws,
            seed=seed + 100 * offset,
        )
        candidates.append(
            {
                "exponent": float(primary_exponent),
                "acceptance_boundary": boundary,
                **evaluation,
            }
        )
    passing = [item for item in candidates if item["passes"]]
    selected = max(passing, key=lambda item: item["acceptance_boundary"]) if passing else None
    sensitivities = []
    if selected is not None:
        for offset, exponent in enumerate(sensitivity_exponents):
            attached = attach_v9_scale_conditioned_score(
                rows,
                minimum_samples_per_scale=minimum_samples_per_scale,
                exponent=float(exponent),
                acceptance_boundary=float(selected["acceptance_boundary"]),
            )
            sensitivities.append(
                {
                    "exponent": float(exponent),
                    "acceptance_boundary": float(selected["acceptance_boundary"]),
                    **_candidate_evaluation(
                        attached,
                        gates=gates,
                        draws=draws,
                        seed=seed + 10_000 + 100 * offset,
                    ),
                }
            )
    return {
        "status": "operating_point_selected" if selected is not None else "no_operating_point",
        "selection_rule": (
            "Most permissive boundary in the frozen grid passing every development "
            "gate at the physically prespecified square-root scale exponent."
        ),
        "minimum_samples_per_scale": float(minimum_samples_per_scale),
        "primary_exponent": float(primary_exponent),
        "candidate_boundaries": boundaries,
        "candidates": candidates,
        "selected": selected,
        "exponent_sensitivity_at_selected_boundary": sensitivities,
    }


def evaluate_v9_scale_conditioned_confirmation(
    rows: Sequence[Mapping[str, Any]],
    *,
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate untouched v9 rows against the frozen confirmation gates."""

    draws = int(gates["bootstrap_replicates"])
    seed = int(gates["bootstrap_seed"])
    evaluation = _candidate_evaluation(
        rows,
        gates=gates,
        draws=draws,
        seed=seed,
    )
    evidence = evaluation["risk_coverage_evidence"]
    assessability = {
        "comparator_invalid_emissions": int(evaluation["qc"]["invalid"]),
        "minimum_comparator_invalid_emissions": int(
            gates["minimum_comparator_invalid_emissions"]
        ),
        "invalid_reference_fields": int(evidence["invalid_reference_fields"]),
        "minimum_invalid_reference_fields": int(
            gates["minimum_invalid_reference_fields"]
        ),
    }
    assessable = bool(
        assessability["comparator_invalid_emissions"]
        >= assessability["minimum_comparator_invalid_emissions"]
        and assessability["invalid_reference_fields"]
        >= assessability["minimum_invalid_reference_fields"]
    )
    ci95 = evidence["bootstrap"]["ci95"]
    ci_excludes_zero = bool(ci95[0] is not None and float(ci95[0]) > 0.0)
    checks = {
        **evaluation["checks"],
        "bootstrap_ci_excludes_zero": ci_excludes_zero,
    }
    if not assessable:
        status = "not_assessable_insufficient_invalid_comparator_emissions"
        passes: bool | None = None
    else:
        passes = bool(all(checks.values()))
        status = "pass" if passes else "fail"

    condition_summaries = []
    condition_ids = sorted(
        {str(row["metadata"]["degradation_id"]) for row in rows}
    )
    for offset, condition_id in enumerate(condition_ids):
        subset = [
            row
            for row in rows
            if str(row["endpoint_family"]) == COHERENCE_FAMILY
            and str(row["metadata"]["degradation_id"]) == condition_id
        ]
        first = subset[0]["metadata"]
        condition_summaries.append(
            {
                "degradation_id": condition_id,
                "degradation_family": first["degradation_family"],
                "severity_rank": first["severity_rank"],
                "full_contract": summarize_policy(
                    subset,
                    condition="full_contract",
                    draws=draws,
                    seed=seed + 1000 + 10 * offset,
                ),
                "conventional_acquisition_qc": summarize_policy(
                    subset,
                    condition="conventional_acquisition_qc",
                    draws=draws,
                    seed=seed + 1001 + 10 * offset,
                ),
            }
        )
    orientation = [
        row
        for row in rows
        if str(row["endpoint_family"]) == "tensor_orientation_distribution"
    ]
    return {
        "status": status,
        "passes": passes,
        "assessable": assessable,
        "assessability": assessability,
        "checks": checks,
        "primary_endpoint_family": COHERENCE_FAMILY,
        "full_contract": evaluation["full"],
        "conventional_acquisition_qc": evaluation["qc"],
        "negative_control_full_contract": evaluation["negative_control_full"],
        "operating_point": evaluation["operating_point"],
        "risk_coverage_evidence": evidence,
        "structure_risk_direction": evaluation["structure_risk_direction"],
        "condition_summaries": condition_summaries,
        "secondary_orientation_distribution": {
            "full_contract": summarize_policy(
                orientation,
                condition="full_contract",
                draws=draws,
                seed=seed + 5000,
            ),
            "conventional_acquisition_qc": summarize_policy(
                orientation,
                condition="conventional_acquisition_qc",
                draws=draws,
                seed=seed + 5001,
            ),
        },
        "claim_rule": (
            "A pass confirms selective tensor-coherence support only for the "
            "frozen BioSR degradation challenge. Orientation distribution remains "
            "a safety endpoint, not a v9 superiority endpoint."
        ),
    }
