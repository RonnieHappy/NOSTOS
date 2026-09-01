"""Endpoint-family selective policies with component-correct ablations.

Version 6 distinguishes a score component from the hard precondition governed
by that component. A comparator cannot inherit a NOSTOS hard abstention while
claiming that the corresponding validity component was removed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


POLICY_HARD_COMPONENTS: dict[str, frozenset[str]] = {
    "full_contract": frozenset({"acquisition_qc", "physical_sampling", "identifiability"}),
    "always_emit": frozenset(),
    "conventional_acquisition_qc": frozenset({"acquisition_qc"}),
    "physical_sampling_only": frozenset({"physical_sampling"}),
    "perturbation_stability_only": frozenset(),
    "full_contract_without_qc": frozenset({"physical_sampling", "identifiability"}),
    "full_contract_without_sampling": frozenset({"acquisition_qc", "identifiability"}),
    "full_contract_without_perturbation": frozenset(
        {"acquisition_qc", "physical_sampling", "identifiability"}
    ),
    "full_contract_without_identifiability": frozenset(
        {"acquisition_qc", "physical_sampling"}
    ),
}

HARD_REASON_COMPONENT = {
    "acquisition_qc_abstain": "acquisition_qc",
    "fewer_than_four_effective_samples_per_requested_scale": "physical_sampling",
    "input_orientation_resultant_below_minimum": "identifiability",
    "input_spectral_orientation_anisotropy_below_minimum": "identifiability",
    "input_orientation_estimators_disagree": "identifiability",
    "input_scale_peak_at_search_boundary": "identifiability",
}


def reference_cases(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
    ]


def hard_components(row: Mapping[str, Any]) -> frozenset[str]:
    components: set[str] = set()
    for reason in row.get("hard_abstention_reasons", []):
        if reason not in HARD_REASON_COMPONENT:
            raise ValueError(f"Unknown hard-abstention reason: {reason}")
        components.add(HARD_REASON_COMPONENT[reason])
    return frozenset(components)


def policy_accepts(
    row: Mapping[str, Any],
    *,
    condition: str,
    threshold: float,
) -> bool:
    if condition not in POLICY_HARD_COMPONENTS:
        raise ValueError(f"No hard-precondition semantics are defined for {condition!r}.")
    if float(row["scores"][condition]) > threshold:
        return False
    governed = POLICY_HARD_COMPONENTS[condition]
    return not bool(hard_components(row) & governed)


def _summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    threshold: float,
) -> dict[str, Any]:
    cases = reference_cases(rows)
    accepted = [
        row
        for row in cases
        if policy_accepts(row, condition=condition, threshold=threshold)
    ]
    combinations = []
    for structure in sorted({str(row["structure"]) for row in cases}):
        subset = [row for row in cases if str(row["structure"]) == structure]
        selected = [
            row
            for row in subset
            if policy_accepts(row, condition=condition, threshold=threshold)
        ]
        invalid = sum(bool(row["invalid"]) for row in selected)
        combinations.append(
            {
                "structure": structure,
                "eligible": len(subset),
                "accepted": len(selected),
                "coverage": len(selected) / len(subset),
                "invalid": int(invalid),
                "risk": float(invalid / len(selected)) if selected else None,
                "reference_fields": len(
                    {str(row["reference_group_id"]) for row in subset}
                ),
            }
        )
    invalid = sum(bool(row["invalid"]) for row in accepted)
    return {
        "condition": condition,
        "threshold": float(threshold),
        "eligible": len(cases),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(cases) if cases else 0.0,
        "invalid": int(invalid),
        "risk": float(invalid / len(accepted)) if accepted else None,
        "structures": combinations,
    }


def cluster_bootstrap_upper(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    threshold: float,
    draws: int,
    seed: int,
    quantile: float = 0.95,
) -> float | None:
    if draws < 1 or not 0.0 < quantile < 1.0:
        raise ValueError("Bootstrap arguments are invalid.")
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in reference_cases(rows):
        groups[(str(row["structure"]), str(row["reference_group_id"]))].append(row)
    strata: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (structure, _), grouped_rows in sorted(groups.items()):
        accepted = [
            row
            for row in grouped_rows
            if policy_accepts(row, condition=condition, threshold=threshold)
        ]
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


def select_family_threshold(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    target_risk: float,
    maximum_risk_upper95: float,
    minimum_family_coverage: float,
    minimum_structure_coverage: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Select the most permissive structure-independent threshold for one family."""

    cases = reference_cases(rows)
    candidates = sorted(
        {
            float(row["scores"][condition])
            for row in cases
            if not bool(hard_components(row) & POLICY_HARD_COMPONENTS[condition])
        },
        reverse=True,
    )
    bootstrap_evaluated = 0
    for threshold in candidates:
        summary = _summary(rows, condition=condition, threshold=threshold)
        if summary["coverage"] < minimum_family_coverage:
            break
        deterministic = (
            summary["risk"] is not None
            and summary["risk"] <= target_risk
            and all(
                item["coverage"] >= minimum_structure_coverage
                and item["risk"] is not None
                and item["risk"] <= target_risk
                for item in summary["structures"]
            )
        )
        if not deterministic:
            continue
        bootstrap_evaluated += 1
        upper = cluster_bootstrap_upper(
            rows,
            condition=condition,
            threshold=threshold,
            draws=draws,
            seed=seed,
        )
        if upper is None or upper > maximum_risk_upper95:
            continue
        return {
            "status": "threshold_selected",
            **summary,
            "cluster_bootstrap_risk_upper95": upper,
            "candidate_thresholds": len(candidates),
            "bootstrap_candidates_evaluated": bootstrap_evaluated,
        }
    return {
        "status": "no_threshold",
        "condition": condition,
        "threshold": None,
        "eligible": len(cases),
        "accepted": 0,
        "coverage": 0.0,
        "invalid": 0,
        "risk": None,
        "structures": [],
        "cluster_bootstrap_risk_upper95": None,
        "candidate_thresholds": len(candidates),
        "bootstrap_candidates_evaluated": bootstrap_evaluated,
    }


def select_family_policy(
    rows: Sequence[Mapping[str, Any]],
    *,
    family_map: Mapping[str, Sequence[str]],
    condition: str,
    target_risk: float,
    maximum_risk_upper95: float,
    minimum_overall_coverage: float,
    minimum_family_coverage: float,
    minimum_structure_coverage: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Select one raw-score cutoff per computational endpoint family."""

    family_results: dict[str, dict[str, Any]] = {}
    family_rows: dict[str, list[Mapping[str, Any]]] = {}
    for offset, (family, endpoints) in enumerate(sorted(family_map.items())):
        endpoint_set = set(endpoints)
        selected_rows = [row for row in rows if str(row["endpoint"]) in endpoint_set]
        family_rows[family] = selected_rows
        family_results[family] = select_family_threshold(
            selected_rows,
            condition=condition,
            target_risk=target_risk,
            maximum_risk_upper95=maximum_risk_upper95,
            minimum_family_coverage=minimum_family_coverage,
            minimum_structure_coverage=minimum_structure_coverage,
            draws=draws,
            seed=seed + offset,
        )
    if any(item["status"] != "threshold_selected" for item in family_results.values()):
        return {
            "status": "fail",
            "condition": condition,
            "families": family_results,
            "overall": None,
        }

    claim_cases: list[Mapping[str, Any]] = []
    accepted: list[Mapping[str, Any]] = []
    for family, selected_rows in family_rows.items():
        cases = reference_cases(selected_rows)
        claim_cases.extend(cases)
        threshold = float(family_results[family]["threshold"])
        accepted.extend(
            row
            for row in cases
            if policy_accepts(row, condition=condition, threshold=threshold)
        )
    invalid = sum(bool(row["invalid"]) for row in accepted)
    overall = {
        "eligible": len(claim_cases),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(claim_cases),
        "invalid": int(invalid),
        "risk": float(invalid / len(accepted)) if accepted else None,
    }

    # Bootstrap the policy as a whole by encoding each family decision in a
    # temporary zero/one score and reusing the same component-correct policy.
    encoded: list[dict[str, Any]] = []
    for family, selected_rows in family_rows.items():
        threshold = float(family_results[family]["threshold"])
        for row in selected_rows:
            clone = dict(row)
            clone["scores"] = dict(row["scores"])
            clone["scores"]["always_emit"] = (
                0.0
                if policy_accepts(row, condition=condition, threshold=threshold)
                else 1.0
            )
            clone["hard_abstention_reasons"] = []
            encoded.append(clone)
    upper = cluster_bootstrap_upper(
        encoded,
        condition="always_emit",
        threshold=0.0,
        draws=draws,
        seed=seed + 1000,
    )
    overall["cluster_bootstrap_risk_upper95"] = upper
    passes = bool(
        overall["coverage"] >= minimum_overall_coverage
        and overall["risk"] is not None
        and overall["risk"] <= target_risk
        and upper is not None
        and upper <= maximum_risk_upper95
    )
    return {
        "status": "pass" if passes else "fail",
        "condition": condition,
        "families": family_results,
        "overall": overall,
    }
