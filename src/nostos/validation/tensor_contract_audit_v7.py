"""Field-clustered audit utilities for the NOSTOS v7 tensor contract."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from nostos.validation.tensor_support_v7 import policy_accepts


def eligible_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
    ]


def clustered_risk_upper95(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    draws: int = 10_000,
    seed: int = 26_082_917,
) -> float | None:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in eligible_rows(rows):
        grouped[(str(row["structure"]), str(row["reference_group_id"]))].append(row)
    if not grouped:
        return None
    strata: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (structure, _), group in sorted(grouped.items()):
        accepted = [row for row in group if policy_accepts(row, condition)]
        strata[structure].append(
            (len(accepted), sum(bool(row["invalid"]) for row in accepted))
        )
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
    return float(np.quantile(finite, 0.95)) if finite.size else None


def summarize_policy(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    draws: int = 10_000,
    seed: int = 26_082_917,
) -> dict[str, Any]:
    eligible = eligible_rows(rows)
    accepted = [row for row in eligible if policy_accepts(row, condition)]
    combinations = []
    keys = sorted(
        {
            (str(row["structure"]), str(row["endpoint_family"]))
            for row in eligible
        }
    )
    for offset, (structure, family) in enumerate(keys):
        subset = [
            row
            for row in eligible
            if str(row["structure"]) == structure
            and str(row["endpoint_family"]) == family
        ]
        selected = [row for row in subset if policy_accepts(row, condition)]
        invalid = sum(bool(row["invalid"]) for row in selected)
        by_field = []
        for field in sorted({str(row["reference_group_id"]) for row in subset}):
            field_rows = [
                row for row in subset if str(row["reference_group_id"]) == field
            ]
            field_selected = [
                row for row in field_rows if policy_accepts(row, condition)
            ]
            failures = sum(bool(row["invalid"]) for row in field_selected)
            by_field.append(
                {
                    "reference_group_id": field,
                    "eligible": len(field_rows),
                    "accepted": len(field_selected),
                    "invalid": failures,
                    "risk": (
                        failures / len(field_selected) if field_selected else None
                    ),
                }
            )
        combinations.append(
            {
                "structure": structure,
                "endpoint_family": family,
                "eligible": len(subset),
                "accepted": len(selected),
                "coverage": len(selected) / len(subset),
                "invalid": invalid,
                "risk": invalid / len(selected) if selected else None,
                "reference_fields": len(by_field),
                "cluster_bootstrap_risk_upper95": clustered_risk_upper95(
                    subset,
                    condition=condition,
                    draws=draws,
                    seed=seed + offset,
                ),
                "worst_field_risk": max(
                    (
                        item["risk"]
                        for item in by_field
                        if item["risk"] is not None
                    ),
                    default=None,
                ),
                "by_field": by_field,
            }
        )
    invalid = sum(bool(row["invalid"]) for row in accepted)
    return {
        "eligible": len(eligible),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(eligible) if eligible else 0.0,
        "invalid": invalid,
        "risk": invalid / len(accepted) if accepted else None,
        "cluster_bootstrap_risk_upper95": clustered_risk_upper95(
            eligible,
            condition=condition,
            draws=draws,
            seed=seed + 100,
        ),
        "combinations": combinations,
    }


def incremental_comparator(
    rows: Sequence[Mapping[str, Any]],
    *,
    full_condition: str = "full_contract",
    comparator_condition: str = "conventional_acquisition_qc",
) -> dict[str, Any]:
    eligible = eligible_rows(rows)
    full = [row for row in eligible if policy_accepts(row, full_condition)]
    comparator = [
        row for row in eligible if policy_accepts(row, comparator_condition)
    ]
    full_ids = {str(row["case_id"]) for row in full}
    comparator_only = [
        row for row in comparator if str(row["case_id"]) not in full_ids
    ]
    full_risk = sum(bool(row["invalid"]) for row in full) / len(full)
    comparator_risk = (
        sum(bool(row["invalid"]) for row in comparator) / len(comparator)
    )
    rejected_risk = (
        sum(bool(row["invalid"]) for row in comparator_only)
        / len(comparator_only)
        if comparator_only
        else None
    )
    enrichment = (
        rejected_risk / comparator_risk
        if rejected_risk is not None and comparator_risk > 0
        else None
    )
    return {
        "full_accepted": len(full),
        "full_risk": full_risk,
        "comparator_accepted": len(comparator),
        "comparator_risk": comparator_risk,
        "full_minus_comparator_risk": full_risk - comparator_risk,
        "coverage_loss_vs_comparator": (
            len(comparator) - len(full)
        )
        / len(eligible),
        "comparator_only_rejections": len(comparator_only),
        "invalid_comparator_only_rejections": sum(
            bool(row["invalid"]) for row in comparator_only
        ),
        "comparator_only_rejection_risk": rejected_risk,
        "invalid_enrichment_among_comparator_only_rejections": enrichment,
    }
