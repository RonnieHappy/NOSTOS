"""Prospective operating-threshold calibration for paired-acquisition evidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from nostos.validation.paired_acquisition_support import aurc


def reference_cases(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return cases for which registration and reference eligibility both passed."""

    return [
        row
        for row in rows
        if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])
    ]


def _accepted(
    row: Mapping[str, Any],
    *,
    threshold: float,
    condition: str,
) -> bool:
    return (
        not bool(row["hard_abstention"])
        and float(row["scores"][condition]) <= threshold
    )


def operating_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    condition: str,
) -> dict[str, Any]:
    """Summarize overall and structure–endpoint behavior at one tied-score cutoff."""

    cases = reference_cases(rows)
    accepted = [
        row for row in cases if _accepted(row, threshold=threshold, condition=condition)
    ]
    combinations: list[dict[str, Any]] = []
    keys = sorted({(str(row["structure"]), str(row["endpoint"])) for row in cases})
    for structure, endpoint in keys:
        subset = [
            row
            for row in cases
            if str(row["structure"]) == structure and str(row["endpoint"]) == endpoint
        ]
        subset_accepted = [
            row
            for row in subset
            if _accepted(row, threshold=threshold, condition=condition)
        ]
        combinations.append(
            {
                "structure": structure,
                "endpoint": endpoint,
                "eligible": len(subset),
                "accepted": len(subset_accepted),
                "coverage": len(subset_accepted) / len(subset),
                "invalid": sum(bool(row["invalid"]) for row in subset_accepted),
                "risk": (
                    float(np.mean([bool(row["invalid"]) for row in subset_accepted]))
                    if subset_accepted
                    else None
                ),
                "reference_fields": len(
                    {str(row["reference_group_id"]) for row in subset}
                ),
            }
        )
    return {
        "threshold": float(threshold),
        "condition": condition,
        "eligible": len(cases),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(cases) if cases else 0.0,
        "invalid": sum(bool(row["invalid"]) for row in accepted),
        "risk": (
            float(np.mean([bool(row["invalid"]) for row in accepted]))
            if accepted
            else None
        ),
        "combinations": combinations,
    }


def stratified_cluster_bootstrap_risk_upper(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    condition: str,
    draws: int,
    seed: int,
    quantile: float = 0.95,
) -> float | None:
    """Upper risk quantile after field resampling within each structure."""

    if draws < 1 or not 0 < quantile < 1:
        raise ValueError("Bootstrap draws and quantile must be valid.")
    grouped: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    by_group: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in reference_cases(rows):
        by_group[(str(row["structure"]), str(row["reference_group_id"]))].append(row)
    for (structure, identifier), group_rows in by_group.items():
        accepted = [
            row
            for row in group_rows
            if _accepted(row, threshold=threshold, condition=condition)
        ]
        grouped[structure][identifier] = (
            len(accepted),
            sum(bool(row["invalid"]) for row in accepted),
        )
    if not grouped:
        return None
    rng = np.random.default_rng(seed)
    estimates = np.full(draws, np.nan, dtype=float)
    strata = {
        structure: [counts for _, counts in sorted(groups.items())]
        for structure, groups in sorted(grouped.items())
    }
    for draw in range(draws):
        accepted_total = 0
        invalid_total = 0
        for counts in strata.values():
            indices = rng.integers(0, len(counts), size=len(counts))
            for index in indices:
                accepted, invalid = counts[int(index)]
                accepted_total += accepted
                invalid_total += invalid
        if accepted_total:
            estimates[draw] = invalid_total / accepted_total
    finite = estimates[np.isfinite(estimates)]
    return float(np.quantile(finite, quantile)) if finite.size else None


def select_operating_threshold_stratified(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    target_risk: float,
    maximum_risk_upper95: float,
    minimum_overall_coverage: float,
    minimum_combination_coverage: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Select the highest-coverage cutoff satisfying every frozen constraint."""

    cases = reference_cases(rows)
    candidates = sorted(
        {
            float(row["scores"][condition])
            for row in cases
            if not bool(row["hard_abstention"])
        },
        reverse=True,
    )
    bootstrap_candidates = 0
    for threshold in candidates:
        summary = operating_summary(rows, threshold=threshold, condition=condition)
        if summary["coverage"] < minimum_overall_coverage:
            break
        combinations_pass = all(
            item["coverage"] >= minimum_combination_coverage
            and item["risk"] is not None
            and item["risk"] <= target_risk
            for item in summary["combinations"]
        )
        if (
            not combinations_pass
            or summary["risk"] is None
            or summary["risk"] > target_risk
        ):
            continue
        bootstrap_candidates += 1
        upper = stratified_cluster_bootstrap_risk_upper(
            rows,
            threshold=threshold,
            condition=condition,
            draws=draws,
            seed=seed,
        )
        if upper is None or upper > maximum_risk_upper95:
            continue
        return {
            "status": "operating_point_selected",
            **summary,
            "cluster_bootstrap_risk_upper95": upper,
            "candidate_thresholds": len(candidates),
            "bootstrap_candidates_evaluated": bootstrap_candidates,
            "constraints": {
                "target_overall_and_combination_risk": target_risk,
                "maximum_overall_cluster_bootstrap_risk_upper95": maximum_risk_upper95,
                "minimum_overall_coverage": minimum_overall_coverage,
                "minimum_structure_endpoint_coverage": minimum_combination_coverage,
            },
        }
    return {
        "status": "no_operating_point",
        "threshold": None,
        "condition": condition,
        "eligible": len(cases),
        "accepted": 0,
        "coverage": 0.0,
        "invalid": 0,
        "risk": None,
        "cluster_bootstrap_risk_upper95": None,
        "combinations": [],
        "candidate_thresholds": len(candidates),
        "bootstrap_candidates_evaluated": bootstrap_candidates,
        "constraints": {
            "target_overall_and_combination_risk": target_risk,
            "maximum_overall_cluster_bootstrap_risk_upper95": maximum_risk_upper95,
            "minimum_overall_coverage": minimum_overall_coverage,
            "minimum_structure_endpoint_coverage": minimum_combination_coverage,
        },
    }


def evaluate_threshold_calibration(
    rows: Sequence[Mapping[str, Any]],
    *,
    eligible_endpoints: set[str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the prospective gate to an untouched threshold-calibration partition."""

    claim_rows = [row for row in rows if str(row["endpoint"]) in eligible_endpoints]
    if not claim_rows:
        raise ValueError("No profile-eligible endpoint rows were supplied.")
    if {str(row["development_partition"]) for row in claim_rows} != {
        "threshold_calibration"
    }:
        raise ValueError("Every calibration row must come from threshold_calibration.")
    parameters = {
        "target_risk": float(config["target_selective_risk"]),
        "maximum_risk_upper95": float(config["maximum_cluster_bootstrap_risk_upper95"]),
        "minimum_overall_coverage": float(config["minimum_overall_confirmation_coverage"]),
        "minimum_combination_coverage": float(
            config["minimum_per_structure_endpoint_coverage"]
        ),
        "draws": int(config["bootstrap_replicates"]),
        "seed": int(config["bootstrap_seed"]),
    }
    full = select_operating_threshold_stratified(
        claim_rows,
        condition="full_contract",
        **parameters,
    )
    conventional_qc = select_operating_threshold_stratified(
        claim_rows,
        condition="conventional_acquisition_qc",
        **parameters,
    )
    full_aurc = aurc(claim_rows, "full_contract")
    always_aurc = aurc(claim_rows, "always_emit")
    qc_aurc = aurc(claim_rows, "conventional_acquisition_qc")
    reduction = None if always_aurc <= 0 else 1.0 - full_aurc / always_aurc
    aurc_gate = (
        reduction is not None
        and reduction >= float(config["minimum_aurc_reduction_fraction"])
    )
    operating_gate = full["status"] == "operating_point_selected"
    return {
        "status": "pass" if operating_gate and aurc_gate else "fail",
        "claim_endpoints": sorted(eligible_endpoints),
        "reference_fields": len(
            {str(row["reference_group_id"]) for row in claim_rows}
        ),
        "paired_acquisitions": len({str(row["pair_id"]) for row in claim_rows}),
        "endpoint_cases": len(claim_rows),
        "reference_eligible_cases": len(reference_cases(claim_rows)),
        "operating_point": full,
        "conventional_qc_operating_point": conventional_qc,
        "aurc": {
            "full_contract": full_aurc,
            "always_emit": always_aurc,
            "conventional_acquisition_qc": qc_aurc,
            "reduction_fraction_vs_always_emit": reduction,
        },
        "gates": {
            "operating_point_selected": operating_gate,
            "minimum_aurc_reduction_fraction": aurc_gate,
            "required_aurc_reduction_fraction": float(
                config["minimum_aurc_reduction_fraction"]
            ),
        },
    }
