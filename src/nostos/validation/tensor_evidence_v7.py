"""Evidence utilities for the family-specific NOSTOS v7 tensor contract.

The v7 contract deliberately treats tensor coherence and the axial orientation
distribution as different estimands.  A strong resolution-margin probe is
allowed to govern coherence only; it is retained as a diagnostic for the
orientation distribution because development data showed no useful risk
ranking for that family.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


COHERENCE_FAMILY = "tensor_coherence"
ORIENTATION_DISTRIBUTION_FAMILY = "tensor_orientation_distribution"


def attach_family_specific_resolution_margin(
    rows: Sequence[Mapping[str, Any]],
    drift_rows: Sequence[Mapping[str, Any]],
    *,
    coherence_threshold_fraction: float,
    sigma_effective_input_pixels: float = 2.0,
) -> list[dict[str, Any]]:
    """Attach the frozen strong-blur score without governing orientation.

    ``normalized_resolution_margin_drift`` is the absolute response change
    divided by the endpoint's invalidity tolerance.  The coherence component
    reaches the policy boundary at ``coherence_threshold_fraction``.  For the
    orientation distribution the same drift is recorded but cannot change the
    score or acceptance decision.
    """

    if not np.isfinite(coherence_threshold_fraction) or coherence_threshold_fraction <= 0:
        raise ValueError("coherence_threshold_fraction must be finite and positive.")
    if not np.isfinite(sigma_effective_input_pixels) or sigma_effective_input_pixels <= 0:
        raise ValueError("sigma_effective_input_pixels must be finite and positive.")
    drift_by_id: dict[str, Mapping[str, Any]] = {}
    for item in drift_rows:
        case_id = str(item["case_id"])
        if case_id in drift_by_id:
            raise ValueError(f"Duplicate resolution-margin case_id: {case_id}")
        drift_by_id[case_id] = item
    row_ids = {str(row["case_id"]) for row in rows}
    if row_ids != set(drift_by_id):
        missing = sorted(row_ids - set(drift_by_id))
        unexpected = sorted(set(drift_by_id) - row_ids)
        raise ValueError(
            "Resolution-margin rows must cover every tensor row exactly once; "
            f"missing={missing[:3]}, unexpected={unexpected[:3]}."
        )

    result: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        row["scores"] = dict(source["scores"])
        case_id = str(row["case_id"])
        item = drift_by_id[case_id]
        normalized = float(item["normalized_resolution_margin_drift"])
        drift = float(item["resolution_margin_drift"])
        if not np.isfinite(normalized) or normalized < 0 or not np.isfinite(drift) or drift < 0:
            raise ValueError(f"Invalid resolution-margin drift for {case_id}.")
        family = str(row["endpoint_family"])
        governs = family == COHERENCE_FAMILY
        if family not in {COHERENCE_FAMILY, ORIENTATION_DISTRIBUTION_FAMILY}:
            raise ValueError(f"Unsupported v7 tensor endpoint family: {family}")
        component_score = normalized / coherence_threshold_fraction
        if governs:
            row["scores"]["full_contract"] = max(
                float(row["scores"]["full_contract"]),
                component_score,
            )
        row["resolution_margin"] = {
            "operation": "Gaussian blur on normalized input before measurement",
            "sigma_effective_input_pixels": float(sigma_effective_input_pixels),
            "drift": drift,
            "normalized_to_endpoint_tolerance": normalized,
            "coherence_threshold_fraction": float(coherence_threshold_fraction),
            "component_score": float(component_score),
            "governs_acceptance": governs,
            "family_rule": (
                "maximum-score contract component"
                if governs
                else "diagnostic_only_no_acceptance_effect"
            ),
        }
        result.append(row)
    return result


def tied_score_aurc(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
) -> float:
    """Return the rectangular AURC with every tied-score block kept intact."""

    if not rows:
        raise ValueError("At least one row is required.")
    ordered = sorted(
        rows,
        key=lambda row: (float(row["scores"][condition]), str(row["case_id"])),
    )
    invalid = 0
    area = 0.0
    previous_coverage = 0.0
    index = 0
    while index < len(ordered):
        score = float(ordered[index]["scores"][condition])
        end = index
        while end < len(ordered) and float(ordered[end]["scores"][condition]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage = end / len(ordered)
        risk = invalid / end
        area += (coverage - previous_coverage) * risk
        previous_coverage = coverage
        index = end
    return float(area)


def _weighted_tied_score_aurc(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str,
    field_index: Mapping[tuple[str, str], int],
    field_counts: np.ndarray,
) -> np.ndarray:
    ordered = sorted(
        rows,
        key=lambda row: (float(row["scores"][condition]), str(row["case_id"])),
    )
    group_indices = np.asarray(
        [
            field_index[(str(row["structure"]), str(row["reference_group_id"]))]
            for row in ordered
        ],
        dtype=int,
    )
    invalid = np.asarray([bool(row["invalid"]) for row in ordered], dtype=bool)
    scores = np.asarray([float(row["scores"][condition]) for row in ordered], dtype=float)
    total = np.sum(field_counts[:, group_indices], axis=1, dtype=float)
    area = np.zeros(field_counts.shape[0], dtype=float)
    accepted = np.zeros_like(area)
    failures = np.zeros_like(area)
    previous_coverage = np.zeros_like(area)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and scores[end] == scores[index]:
            end += 1
        block_indices = group_indices[index:end]
        accepted += np.sum(field_counts[:, block_indices], axis=1, dtype=float)
        invalid_indices = block_indices[invalid[index:end]]
        if len(invalid_indices):
            failures += np.sum(field_counts[:, invalid_indices], axis=1, dtype=float)
        coverage = np.divide(
            accepted,
            total,
            out=np.full_like(area, np.nan),
            where=total > 0,
        )
        risk = np.divide(
            failures,
            accepted,
            out=np.zeros_like(area),
            where=accepted > 0,
        )
        area += np.where(
            np.isfinite(coverage),
            (coverage - previous_coverage) * risk,
            0.0,
        )
        previous_coverage = np.where(
            np.isfinite(coverage), coverage, previous_coverage
        )
        index = end
    area[total <= 0] = np.nan
    return area


def clustered_coherence_aurc_difference(
    rows: Sequence[Mapping[str, Any]],
    *,
    full_condition: str = "full_contract",
    comparator_condition: str = "conventional_acquisition_qc",
    draws: int = 10_000,
    seed: int = 26_082_929,
) -> dict[str, Any]:
    """Bootstrap paired coherence AURC differences at the reference-field unit.

    Fields are sampled independently within each structure.  Positive
    comparator-minus-full differences favor the complete contract.  The
    function reports zero-difference draws, including samples containing no
    invalid cases, rather than discarding them.
    """

    if draws < 1:
        raise ValueError("draws must be positive.")
    eligible = [
        row
        for row in rows
        if bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
        and str(row["endpoint_family"]) == COHERENCE_FAMILY
    ]
    if not eligible:
        raise ValueError("No eligible tensor-coherence rows were supplied.")

    structures = sorted({str(row["structure"]) for row in eligible})
    field_keys: list[tuple[str, str]] = []
    fields_by_structure: dict[str, list[tuple[str, str]]] = {}
    for structure in structures:
        keys = sorted(
            {
                (structure, str(row["reference_group_id"]))
                for row in eligible
                if str(row["structure"]) == structure
            }
        )
        fields_by_structure[structure] = keys
        field_keys.extend(keys)
    field_index = {key: index for index, key in enumerate(field_keys)}
    generator = np.random.default_rng(seed)
    counts = np.zeros((draws, len(field_keys)), dtype=np.int32)
    for structure in structures:
        keys = fields_by_structure[structure]
        sampled = generator.multinomial(
            len(keys), np.full(len(keys), 1.0 / len(keys)), size=draws
        )
        indices = [field_index[key] for key in keys]
        counts[:, indices] = sampled

    full_draws = _weighted_tied_score_aurc(
        eligible,
        condition=full_condition,
        field_index=field_index,
        field_counts=counts,
    )
    comparator_draws = _weighted_tied_score_aurc(
        eligible,
        condition=comparator_condition,
        field_index=field_index,
        field_counts=counts,
    )
    difference = comparator_draws - full_draws
    finite = difference[np.isfinite(difference)]

    structure_results: dict[str, Any] = {}
    for structure in structures:
        subset = [row for row in eligible if str(row["structure"]) == structure]
        keys = fields_by_structure[structure]
        subset_counts = counts.copy()
        keep = {field_index[key] for key in keys}
        remove = [index for index in range(len(field_keys)) if index not in keep]
        if remove:
            subset_counts[:, remove] = 0
        full = _weighted_tied_score_aurc(
            subset,
            condition=full_condition,
            field_index=field_index,
            field_counts=subset_counts,
        )
        comparator = _weighted_tied_score_aurc(
            subset,
            condition=comparator_condition,
            field_index=field_index,
            field_counts=subset_counts,
        )
        values = comparator - full
        values = values[np.isfinite(values)]
        structure_results[structure] = _difference_summary(values)

    observed_full = tied_score_aurc(eligible, condition=full_condition)
    observed_comparator = tied_score_aurc(
        eligible, condition=comparator_condition
    )
    return {
        "endpoint_family": COHERENCE_FAMILY,
        "eligible_rows": len(eligible),
        "reference_fields": len(field_keys),
        "invalid_rows": sum(bool(row["invalid"]) for row in eligible),
        "invalid_reference_fields": len(
            {
                (str(row["structure"]), str(row["reference_group_id"]))
                for row in eligible
                if bool(row["invalid"])
            }
        ),
        "observed": {
            "full_contract_aurc": observed_full,
            "conventional_acquisition_qc_aurc": observed_comparator,
            "comparator_minus_full": observed_comparator - observed_full,
            "relative_reduction": (
                1.0 - observed_full / observed_comparator
                if observed_comparator > 0
                else None
            ),
        },
        "bootstrap": {
            "draws": draws,
            "seed": seed,
            "resampling_unit": "reference_group_id stratified by structure",
            "difference_direction": "positive comparator-minus-full values favor the complete contract",
            **_difference_summary(finite),
            "structure_specific": structure_results,
        },
    }


def _difference_summary(values: np.ndarray) -> dict[str, Any]:
    if not len(values):
        return {
            "finite_draws": 0,
            "median": None,
            "ci95": [None, None],
            "probability_full_better": None,
            "probability_full_noninferior": None,
        }
    return {
        "finite_draws": int(len(values)),
        "median": float(np.median(values)),
        "ci95": [float(value) for value in np.quantile(values, [0.025, 0.975])],
        "probability_full_better": float(np.mean(values > 0)),
        "probability_full_noninferior": float(np.mean(values >= 0)),
    }

