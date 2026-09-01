"""Frozen v6 confirmation evaluation for paired-acquisition support."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from nostos.validation.family_risk_calibration import endpoint_family, risk_coverage_auc
from nostos.validation.selective_policy_v6 import (
    POLICY_HARD_COMPONENTS,
    hard_components,
    policy_accepts,
    reference_cases,
)


def select_confirmation_cells(
    by_cell: Mapping[str, Sequence[Any]],
    *,
    structure: str,
    count: int,
) -> list[str]:
    """Select a deterministic initial tranche without reading pixels or outcomes."""

    if count < 1:
        raise ValueError("Confirmation field count must be positive.")
    if len(by_cell) < count:
        raise ValueError(
            f"{structure} contains only {len(by_cell)} fields; {count} were frozen."
        )
    return sorted(
        by_cell,
        key=lambda cell: hashlib.sha256(
            f"NOSTOS-v6-initial-confirmation|{structure}|{by_cell[cell][0].reference_group_id}".encode(
                "utf-8"
            )
        ).hexdigest(),
    )[:count]


def _annotate(
    rows: Sequence[Mapping[str, Any]],
    *,
    family_map: Mapping[str, Sequence[str]],
    condition: str,
    thresholds: Mapping[str, float] | None,
) -> list[dict[str, Any]]:
    endpoints = {endpoint for values in family_map.values() for endpoint in values}
    cases = reference_cases(
        [row for row in rows if str(row["endpoint"]) in endpoints]
    )
    annotated: list[dict[str, Any]] = []
    for row in cases:
        family = endpoint_family(str(row["endpoint"]), family_map)
        if condition == "always_emit":
            threshold = 0.0
            accepted = policy_accepts(row, condition=condition, threshold=threshold)
            normalized = 0.0
        else:
            if thresholds is None or family not in thresholds:
                raise ValueError(f"Missing {condition} threshold for family {family}.")
            threshold = float(thresholds[family])
            accepted = policy_accepts(row, condition=condition, threshold=threshold)
            normalized = float(row["scores"][condition]) / max(
                threshold,
                np.finfo(float).eps,
            )
            if bool(hard_components(row) & POLICY_HARD_COMPONENTS[condition]):
                normalized = max(normalized, 1.0) + 1.0
        clone = dict(row)
        clone["endpoint_family"] = family
        clone["policy_condition"] = condition
        clone["policy_threshold"] = threshold
        clone["policy_accepted"] = bool(accepted)
        clone["normalized_policy_score"] = float(normalized)
        annotated.append(clone)
    return annotated


def _policy_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in rows if bool(row["policy_accepted"])]
    invalid = sum(bool(row["invalid"]) for row in accepted)
    combinations = []
    keys = sorted(
        {
            (str(row["structure"]), str(row["endpoint_family"]))
            for row in rows
        }
    )
    for structure, family in keys:
        subset = [
            row
            for row in rows
            if str(row["structure"]) == structure
            and str(row["endpoint_family"]) == family
        ]
        selected = [row for row in subset if bool(row["policy_accepted"])]
        failures = sum(bool(row["invalid"]) for row in selected)
        combinations.append(
            {
                "structure": structure,
                "endpoint_family": family,
                "eligible": len(subset),
                "accepted": len(selected),
                "coverage": len(selected) / len(subset),
                "invalid": int(failures),
                "risk": float(failures / len(selected)) if selected else None,
                "reference_fields": len(
                    {str(row["reference_group_id"]) for row in subset}
                ),
            }
        )
    return {
        "eligible": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows) if rows else 0.0,
        "invalid": int(invalid),
        "risk": float(invalid / len(accepted)) if accepted else None,
        "combinations": combinations,
        "risk_coverage_auc": risk_coverage_auc(
            rows,
            score_key="normalized_policy_score",
        ),
    }


def _decision_cluster_bootstrap_upper(
    rows: Sequence[Mapping[str, Any]],
    *,
    draws: int,
    seed: int,
    quantile: float = 0.95,
) -> float | None:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["structure"]), str(row["reference_group_id"]))].append(row)
    strata: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (structure, _), group_rows in sorted(grouped.items()):
        accepted = [row for row in group_rows if bool(row["policy_accepted"])]
        strata[structure].append(
            (len(accepted), sum(bool(row["invalid"]) for row in accepted))
        )
    if not strata:
        return None
    generator = np.random.default_rng(seed)
    estimates = np.full(draws, np.nan, dtype=float)
    for draw in range(draws):
        accepted_total = 0
        invalid_total = 0
        for counts in strata.values():
            indices = generator.integers(0, len(counts), size=len(counts))
            for index in indices:
                accepted, invalid = counts[int(index)]
                accepted_total += accepted
                invalid_total += invalid
        if accepted_total:
            estimates[draw] = invalid_total / accepted_total
    finite = estimates[np.isfinite(estimates)]
    return float(np.quantile(finite, quantile)) if finite.size else None


def _incremental_comparison(
    full_rows: Sequence[Mapping[str, Any]],
    qc_rows: Sequence[Mapping[str, Any]],
    *,
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    full_by_id = {str(row["case_id"]): row for row in full_rows}
    qc_by_id = {str(row["case_id"]): row for row in qc_rows}
    if set(full_by_id) != set(qc_by_id):
        raise ValueError("Full and QC policies do not cover identical reference cases.")
    full_accepted = [row for row in full_rows if bool(row["policy_accepted"])]
    qc_accepted = [row for row in qc_rows if bool(row["policy_accepted"])]
    qc_only = [
        qc_by_id[identifier]
        for identifier in qc_by_id
        if bool(qc_by_id[identifier]["policy_accepted"])
        and not bool(full_by_id[identifier]["policy_accepted"])
    ]
    full_risk = (
        sum(bool(row["invalid"]) for row in full_accepted) / len(full_accepted)
        if full_accepted
        else None
    )
    qc_risk = (
        sum(bool(row["invalid"]) for row in qc_accepted) / len(qc_accepted)
        if qc_accepted
        else None
    )
    rejected_risk = (
        sum(bool(row["invalid"]) for row in qc_only) / len(qc_only)
        if qc_only
        else None
    )
    enrichment = (
        rejected_risk / qc_risk
        if rejected_risk is not None and qc_risk is not None and qc_risk > 0
        else None
    )
    coverage_loss = len(qc_accepted) / len(qc_rows) - len(full_accepted) / len(full_rows)
    risk_difference = (
        full_risk - qc_risk
        if full_risk is not None and qc_risk is not None
        else None
    )
    if qc_risk is None or qc_risk == 0:
        status = "not_assessable_no_qc_invalid_case"
    else:
        passes = bool(
            risk_difference is not None
            and risk_difference <= float(rules["maximum_full_minus_qc_risk"])
            and coverage_loss <= float(rules["maximum_full_coverage_loss_vs_qc"])
            and enrichment is not None
            and enrichment
            >= float(rules["minimum_invalid_enrichment_among_qc_only_rejections"])
        )
        status = "pass" if passes else "fail"
    return {
        "status": status,
        "full_accepted": len(full_accepted),
        "full_risk": full_risk,
        "qc_accepted": len(qc_accepted),
        "qc_risk": qc_risk,
        "full_minus_qc_risk": risk_difference,
        "full_coverage_loss_vs_qc": coverage_loss,
        "qc_only_cases_rejected_by_full": len(qc_only),
        "qc_only_invalid_rejected_by_full": sum(
            bool(row["invalid"]) for row in qc_only
        ),
        "qc_only_rejection_risk": rejected_risk,
        "invalid_enrichment_among_qc_only_rejections": enrichment,
        "rules": dict(rules),
    }


def evaluate_v6_confirmation(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply every frozen v6 policy and confirmation gate without refitting."""

    family_map = config["endpoint_families"]
    expected_structures = set(config["initial_confirmation"]["structures"])
    observed_structures = {str(row["structure"]) for row in rows}
    if not observed_structures or not observed_structures <= expected_structures:
        raise ValueError(f"Unexpected confirmation structures: {observed_structures}")
    policies: dict[str, dict[str, Any]] = {}
    annotated_by_policy: dict[str, list[dict[str, Any]]] = {}
    for condition, thresholds in config["policy_thresholds"].items():
        annotated = _annotate(
            rows,
            family_map=family_map,
            condition=condition,
            thresholds=thresholds,
        )
        annotated_by_policy[condition] = annotated
        policies[condition] = _policy_summary(annotated)
    always = _annotate(
        rows,
        family_map=family_map,
        condition="always_emit",
        thresholds=None,
    )
    annotated_by_policy["always_emit"] = always
    policies["always_emit"] = _policy_summary(always)

    rules = config["initial_confirmation"]
    full_rows = annotated_by_policy["full_contract"]
    full = policies["full_contract"]
    upper = _decision_cluster_bootstrap_upper(
        full_rows,
        draws=int(rules["bootstrap_replicates"]),
        seed=int(rules["bootstrap_seed"]),
    )
    full["cluster_bootstrap_risk_upper95"] = upper
    combination_results = [
        {
            **item,
            "passes": bool(
                item["coverage"]
                >= float(rules["minimum_structure_family_coverage"])
                and item["risk"] is not None
                and item["risk"] <= float(rules["target_observed_risk"])
            ),
        }
        for item in full["combinations"]
    ]
    full["combinations"] = combination_results
    always_aurc = policies["always_emit"]["risk_coverage_auc"]
    reduction = (
        None
        if always_aurc <= 0
        else 1.0 - full["risk_coverage_auc"] / always_aurc
    )
    field_count = len({str(row["reference_group_id"]) for row in full_rows})
    safety_pass = bool(
        field_count >= int(rules["minimum_total_reference_fields"])
        and full["coverage"] >= float(rules["minimum_overall_coverage"])
        and full["risk"] is not None
        and full["risk"] <= float(rules["target_observed_risk"])
        and upper is not None
        and upper <= float(rules["maximum_cluster_bootstrap_risk_upper95"])
        and all(item["passes"] for item in combination_results)
        and reduction is not None
        and reduction
        >= float(rules["minimum_aurc_reduction_fraction_vs_always_emit"])
    )
    incremental = _incremental_comparison(
        full_rows,
        annotated_by_policy["conventional_acquisition_qc"],
        rules=rules["incremental_comparator_gate"],
    )
    if not safety_pass:
        status = "fail"
    elif incremental["status"] == "pass":
        status = "pass"
    elif incremental["status"].startswith("not_assessable"):
        status = "safety_pass_incremental_not_assessable"
    else:
        status = "safety_pass_incremental_fail"
    return {
        "status": status,
        "reference_fields": field_count,
        "policies": policies,
        "aurc_reduction_fraction_vs_always_emit": reduction,
        "safety_gate_passed": safety_pass,
        "incremental_comparator": incremental,
        "confirmation_thresholds_refit": False,
    }
