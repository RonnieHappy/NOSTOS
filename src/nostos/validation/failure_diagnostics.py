"""Read-only diagnostics for a failed selective-risk calibration gate.

These helpers explain why a frozen gate failed. They do not select an operating
threshold for subsequent confirmation and must not be used to relabel a failed
protocol as passing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


def best_combination_point(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    minimum_coverage: float,
) -> dict[str, Any]:
    """Return the lowest observed risk attainable at the coverage floor.

    Coverage uses every reference-eligible case as its denominator, including
    hard abstentions. Tied minimum-risk candidates are resolved in favour of
    higher coverage and then the more permissive threshold. This is a
    diagnostic optimum for one structure-endpoint combination, not a threshold
    authorized for confirmation.
    """

    if not 0.0 <= minimum_coverage <= 1.0:
        raise ValueError("minimum_coverage must lie in [0, 1].")
    cases = [
        row
        for row in rows
        if bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
    ]
    if not cases:
        return {
            "status": "not_assessable",
            "eligible": 0,
            "reference_fields": 0,
            "hard_abstentions": 0,
            "minimum_coverage": float(minimum_coverage),
            "best": None,
        }

    candidates = sorted(
        {
            float(row["scores"][condition])
            for row in cases
            if not bool(row["hard_abstention"])
        }
    )
    summaries: list[dict[str, Any]] = []
    for threshold in candidates:
        accepted = [
            row
            for row in cases
            if not bool(row["hard_abstention"])
            and float(row["scores"][condition]) <= threshold
        ]
        coverage = len(accepted) / len(cases)
        if coverage < minimum_coverage:
            continue
        invalid = sum(bool(row["invalid"]) for row in accepted)
        summaries.append(
            {
                "threshold": float(threshold),
                "accepted": len(accepted),
                "coverage": float(coverage),
                "invalid": int(invalid),
                "risk": float(invalid / len(accepted)),
            }
        )

    baseline_accepted = [row for row in cases if not bool(row["hard_abstention"])]
    baseline_invalid = sum(bool(row["invalid"]) for row in baseline_accepted)
    baseline = {
        "accepted": len(baseline_accepted),
        "coverage": len(baseline_accepted) / len(cases),
        "invalid": int(baseline_invalid),
        "risk": (
            float(baseline_invalid / len(baseline_accepted))
            if baseline_accepted
            else None
        ),
    }
    if not summaries:
        return {
            "status": "coverage_floor_unattainable",
            "eligible": len(cases),
            "reference_fields": len(
                {str(row["reference_group_id"]) for row in cases}
            ),
            "hard_abstentions": sum(bool(row["hard_abstention"]) for row in cases),
            "minimum_coverage": float(minimum_coverage),
            "always_accept_nonhard": baseline,
            "best": None,
        }

    best = min(
        summaries,
        key=lambda item: (
            item["risk"],
            -item["coverage"],
            -item["threshold"],
        ),
    )
    return {
        "status": "assessable",
        "eligible": len(cases),
        "reference_fields": len(
            {str(row["reference_group_id"]) for row in cases}
        ),
        "hard_abstentions": sum(bool(row["hard_abstention"]) for row in cases),
        "minimum_coverage": float(minimum_coverage),
        "always_accept_nonhard": baseline,
        "best": best,
        "candidate_thresholds_at_or_above_coverage_floor": len(summaries),
    }


def diagnose_combinations(
    rows: Sequence[Mapping[str, Any]],
    *,
    endpoints: set[str],
    condition: str,
    minimum_coverage: float,
    target_risk: float,
) -> list[dict[str, Any]]:
    """Diagnose each observed structure-endpoint combination independently."""

    claim_rows = [row for row in rows if str(row["endpoint"]) in endpoints]
    keys = sorted(
        {(str(row["structure"]), str(row["endpoint"])) for row in claim_rows}
    )
    diagnostics: list[dict[str, Any]] = []
    for structure, endpoint in keys:
        subset = [
            row
            for row in claim_rows
            if str(row["structure"]) == structure
            and str(row["endpoint"]) == endpoint
        ]
        result = best_combination_point(
            subset,
            condition=condition,
            minimum_coverage=minimum_coverage,
        )
        best = result.get("best")
        result.update(
            {
                "structure": structure,
                "endpoint": endpoint,
                "condition": condition,
                "passes_independent_diagnostic": bool(
                    best is not None and float(best["risk"]) <= target_risk
                ),
                "target_risk": float(target_risk),
            }
        )
        diagnostics.append(result)
    return diagnostics


def threshold_scale_conflicts(
    diagnostics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """List within-structure endpoint pairs with strongly separated optima."""

    conflicts: list[dict[str, Any]] = []
    structures = sorted({str(item["structure"]) for item in diagnostics})
    for structure in structures:
        points = [
            item
            for item in diagnostics
            if str(item["structure"]) == structure and item.get("best") is not None
        ]
        for left_index, left in enumerate(points):
            for right in points[left_index + 1 :]:
                left_threshold = float(left["best"]["threshold"])
                right_threshold = float(right["best"]["threshold"])
                separation = abs(left_threshold - right_threshold)
                if separation < 0.5:
                    continue
                conflicts.append(
                    {
                        "structure": structure,
                        "endpoint_a": str(left["endpoint"]),
                        "threshold_a": left_threshold,
                        "endpoint_b": str(right["endpoint"]),
                        "threshold_b": right_threshold,
                        "absolute_separation": float(separation),
                    }
                )
    return sorted(
        conflicts,
        key=lambda item: (-item["absolute_separation"], item["structure"]),
    )


def summarize_score_distributions(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
) -> dict[str, float | int | None]:
    """Summarize valid and invalid score distributions for audit context."""

    eligible = [
        row
        for row in rows
        if bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
        and not bool(row["hard_abstention"])
    ]
    output: dict[str, float | int | None] = {"eligible_nonhard": len(eligible)}
    for label, state in (("valid", False), ("invalid", True)):
        values = np.asarray(
            [
                float(row["scores"][condition])
                for row in eligible
                if bool(row["invalid"]) is state
            ],
            dtype=float,
        )
        output[f"{label}_n"] = int(values.size)
        output[f"{label}_median"] = (
            float(np.median(values)) if values.size else None
        )
        output[f"{label}_q10"] = (
            float(np.quantile(values, 0.10)) if values.size else None
        )
        output[f"{label}_q90"] = (
            float(np.quantile(values, 0.90)) if values.size else None
        )
    return output
