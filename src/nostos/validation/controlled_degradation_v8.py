"""Outcome-blind controlled degradations and evaluation for the v8 tensor pilot."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import ndimage
from skimage.transform import resize

from nostos.validation.tensor_contract_audit_v7 import (
    eligible_rows,
    incremental_comparator,
    summarize_policy,
)
from nostos.validation.tensor_evidence_v7 import (
    clustered_coherence_aurc_difference,
)


COHERENCE_FAMILY = "tensor_coherence"


def deterministic_condition_seed(
    base_seed: int, *, pair_id: str, condition_id: str
) -> int:
    """Derive the frozen 32-bit condition seed from stable identifiers."""

    payload = f"{int(base_seed)}|{pair_id}|{condition_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % (2**32)


def _robust_bounds(image: np.ndarray) -> tuple[float, float]:
    low, high = np.percentile(np.asarray(image, dtype=np.float64), (1.0, 99.0))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        raise ValueError("Controlled degradation requires nonconstant finite data.")
    return float(low), float(high)


def apply_controlled_degradation(
    image: np.ndarray,
    specification: Mapping[str, Any],
    *,
    seed: int,
) -> np.ndarray:
    """Apply one frozen, coordinate-preserving degradation to a 2-D image."""

    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or not np.isfinite(data).all():
        raise ValueError("Controlled tensor degradation requires a finite 2-D image.")
    operation = str(specification["operation"])
    if operation == "identity":
        result = data.copy()
    elif operation == "gamma":
        gamma = float(specification["gamma"])
        if gamma <= 0:
            raise ValueError("Gamma must be positive.")
        low, high = _robust_bounds(data)
        normalized = np.clip((data - low) / (high - low), 0.0, 1.0)
        result = low + (high - low) * np.power(normalized, gamma)
    elif operation == "gaussian_blur":
        sigma = float(specification["sigma_input_pixels"])
        if sigma <= 0:
            raise ValueError("Blur sigma must be positive.")
        result = ndimage.gaussian_filter(data, sigma=sigma, mode="reflect")
    elif operation == "anisotropic_gaussian_blur":
        sigma = tuple(float(value) for value in specification["sigma_yx_input_pixels"])
        if len(sigma) != 2 or min(sigma) <= 0:
            raise ValueError("Anisotropic blur requires two positive sigmas.")
        result = ndimage.gaussian_filter(data, sigma=sigma, mode="reflect")
    elif operation == "downsample_restore":
        factor = int(specification["factor"])
        if factor < 2:
            raise ValueError("Downsample/restore factor must be at least two.")
        reduced_shape = tuple(max(2, size // factor) for size in data.shape)
        reduced = resize(
            data,
            reduced_shape,
            order=1,
            mode="reflect",
            anti_aliasing=True,
            preserve_range=True,
        )
        result = resize(
            reduced,
            data.shape,
            order=1,
            mode="reflect",
            anti_aliasing=False,
            preserve_range=True,
        )
    elif operation == "gaussian_noise":
        sigma_fraction = float(specification["sigma_fraction_robust_range"])
        if sigma_fraction <= 0:
            raise ValueError("Noise fraction must be positive.")
        low, high = _robust_bounds(data)
        generator = np.random.default_rng(int(seed))
        result = data + generator.normal(
            0.0, sigma_fraction * (high - low), size=data.shape
        )
    else:
        raise KeyError(f"Unknown controlled degradation operation: {operation}")
    result = np.asarray(result, dtype=np.float64)
    if result.shape != data.shape or not np.isfinite(result).all():
        raise RuntimeError("Controlled degradation changed shape or emitted nonfinite data.")
    return result


def _policy_pair(
    rows: Sequence[Mapping[str, Any]], *, draws: int, seed: int
) -> dict[str, Any]:
    return {
        "full_contract": summarize_policy(
            rows,
            condition="full_contract",
            draws=draws,
            seed=seed,
        ),
        "conventional_acquisition_qc": summarize_policy(
            rows,
            condition="conventional_acquisition_qc",
            draws=draws,
            seed=seed + 1,
        ),
    }


def _risk_reduction(full_risk: float | None, qc_risk: float | None) -> float | None:
    if full_risk is None or qc_risk is None or qc_risk <= 0:
        return None
    return float(1.0 - full_risk / qc_risk)


def _structure_risk_direction(
    full: Mapping[str, Any], qc: Mapping[str, Any]
) -> list[dict[str, Any]]:
    full_by = {
        (str(item["structure"]), str(item["endpoint_family"])): item
        for item in full["combinations"]
    }
    qc_by = {
        (str(item["structure"]), str(item["endpoint_family"])): item
        for item in qc["combinations"]
    }
    result = []
    for key in sorted(full_by):
        first = full_by[key]
        second = qc_by[key]
        full_risk = first["risk"]
        qc_risk = second["risk"]
        nonhigher = bool(
            full_risk is not None
            and qc_risk is not None
            and float(full_risk) <= float(qc_risk)
        )
        result.append(
            {
                "structure": key[0],
                "endpoint_family": key[1],
                "full_risk": full_risk,
                "qc_risk": qc_risk,
                "full_risk_nonhigher": nonhigher,
            }
        )
    return result


def _condition_summaries(
    rows: Sequence[Mapping[str, Any]], *, draws: int, seed: int
) -> list[dict[str, Any]]:
    result = []
    condition_ids = sorted(
        {str(row["metadata"]["degradation_id"]) for row in rows}
    )
    for offset, condition_id in enumerate(condition_ids):
        subset = [
            row
            for row in rows
            if str(row["metadata"]["degradation_id"]) == condition_id
        ]
        policies = _policy_pair(subset, draws=draws, seed=seed + 10 * offset)
        first = subset[0]["metadata"]
        result.append(
            {
                "degradation_id": condition_id,
                "degradation_family": first["degradation_family"],
                "severity_rank": first["severity_rank"],
                **policies,
            }
        )
    return result


def evaluate_controlled_degradation_pilot(
    rows: Sequence[Mapping[str, Any]],
    *,
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen engineering pilot without selecting a new threshold."""

    if not rows:
        raise ValueError("Controlled-degradation evaluation requires rows.")
    draws = int(gates["bootstrap_replicates"])
    seed = int(gates["bootstrap_seed"])
    coherence = [
        row for row in rows if str(row["endpoint_family"]) == COHERENCE_FAMILY
    ]
    if len(coherence) * 2 != len(rows):
        raise ValueError("Pilot requires paired coherence and orientation rows.")
    negative = [
        row
        for row in coherence
        if str(row["metadata"]["degradation_family"]) == "negative_control"
    ]
    overall = _policy_pair(coherence, draws=draws, seed=seed)
    negative_policies = _policy_pair(negative, draws=draws, seed=seed + 1000)
    comparator = incremental_comparator(coherence)
    evidence = clustered_coherence_aurc_difference(
        coherence,
        draws=draws,
        seed=seed,
    )
    qc = overall["conventional_acquisition_qc"]
    full = overall["full_contract"]
    invalid_fields = evidence["invalid_reference_fields"]
    relative_risk_reduction = _risk_reduction(full["risk"], qc["risk"])
    directions = _structure_risk_direction(full, qc)
    rejection_invalid_fraction = comparator["comparator_only_rejection_risk"]

    assessability = {
        "comparator_invalid_emissions": int(qc["invalid"]),
        "minimum_comparator_invalid_emissions": int(
            gates["minimum_comparator_invalid_emissions"]
        ),
        "invalid_reference_fields": int(invalid_fields),
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
    checks = {
        "negative_control_coverage": bool(
            negative_policies["full_contract"]["coverage"]
            >= float(gates["minimum_negative_control_coverage"])
        ),
        "negative_control_risk": bool(
            negative_policies["full_contract"]["risk"] is not None
            and negative_policies["full_contract"]["risk"]
            <= float(gates["maximum_negative_control_risk"])
        ),
        "overall_coverage": bool(
            full["coverage"]
            >= float(gates["minimum_overall_full_contract_coverage"])
        ),
        "overall_risk": bool(
            full["risk"] is not None
            and full["risk"] <= float(gates["maximum_overall_full_contract_risk"])
        ),
        "cluster_risk_upper95": bool(
            full["cluster_bootstrap_risk_upper95"] is not None
            and full["cluster_bootstrap_risk_upper95"]
            <= float(gates["maximum_cluster_bootstrap_risk_upper95"])
        ),
        "relative_risk_reduction": bool(
            relative_risk_reduction is not None
            and relative_risk_reduction
            >= float(gates["minimum_relative_risk_reduction_vs_qc"])
        ),
        "rejected_case_invalid_fraction": bool(
            rejection_invalid_fraction is not None
            and rejection_invalid_fraction
            >= float(gates["minimum_invalid_fraction_among_qc_only_rejections"])
        ),
        "positive_aurc_difference": bool(
            evidence["observed"]["comparator_minus_full"] > 0
        ),
        "bootstrap_probability": bool(
            evidence["bootstrap"]["probability_full_better"] is not None
            and evidence["bootstrap"]["probability_full_better"]
            >= float(gates["minimum_bootstrap_probability_full_better"])
        ),
        "structure_risk_direction": bool(
            all(item["full_risk_nonhigher"] for item in directions)
        ),
    }
    if not assessable:
        status = "not_assessable_insufficient_invalid_comparator_emissions"
        passes: bool | None = None
    else:
        passes = bool(all(checks.values()))
        status = "pass" if passes else "fail"

    accepted = [
        row
        for row in eligible_rows(coherence)
        if float(row["scores"]["full_contract"]) <= 1.0
        and not row["hard_abstention_reasons"]
    ]
    accepted_ids = {str(row["case_id"]) for row in accepted}
    rejected = [
        row
        for row in eligible_rows(coherence)
        if str(row["case_id"]) not in accepted_ids
    ]
    reason_counts = Counter(
        reason
        for row in rejected
        for reason in row["hard_abstention_reasons"]
    )
    dominant_components = Counter()
    governing_components = (
        "acquisition_qc",
        "physical_sampling",
        "perturbation_stability",
        "measurement_identifiability",
        "resolution_margin",
    )
    for row in rejected:
        components = {
            name: float(row["support_components"].get(name, 0.0))
            for name in governing_components
        }
        maximum = max(components.values())
        for name, value in components.items():
            if float(value) == maximum:
                dominant_components[name] += 1

    return {
        "status": status,
        "passes": passes,
        "assessable": assessable,
        "assessability": assessability,
        "checks": checks,
        "primary_endpoint_family": COHERENCE_FAMILY,
        "overall": overall,
        "negative_controls": negative_policies,
        "operating_point": {
            **comparator,
            "relative_risk_reduction_vs_qc": relative_risk_reduction,
        },
        "risk_coverage_evidence": evidence,
        "structure_risk_direction": directions,
        "condition_summaries": _condition_summaries(
            coherence, draws=draws, seed=seed + 2000
        ),
        "rejection_diagnostics": {
            "accepted_coherence_rows": len(accepted),
            "rejected_coherence_rows": len(rejected),
            "hard_reason_counts": dict(sorted(reason_counts.items())),
            "dominant_support_component_counts": dict(
                sorted(dominant_components.items())
            ),
        },
        "secondary_orientation_distribution": _policy_pair(
            [
                row
                for row in rows
                if str(row["endpoint_family"])
                == "tensor_orientation_distribution"
            ],
            draws=draws,
            seed=seed + 3000,
        ),
    }
