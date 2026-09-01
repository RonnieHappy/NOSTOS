"""Finite-sample risk intervals that keep nested rows and independent units distinct."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from scipy.stats import beta

from nostos.validation.validity_profile_compiler import canonical_sha256


def clopper_pearson_interval(
    events: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> tuple[float, float]:
    if trials <= 0 or events < 0 or events > trials:
        raise ValueError("Clopper-Pearson counts must satisfy 0 <= events <= trials.")
    if not 0.0 < confidence < 1.0:
        raise ValueError("Confidence must be between zero and one.")
    alpha = 1.0 - confidence
    lower = 0.0 if events == 0 else float(beta.ppf(alpha / 2.0, events, trials - events + 1))
    upper = (
        1.0
        if events == trials
        else float(beta.ppf(1.0 - alpha / 2.0, events + 1, trials - events))
    )
    return lower, upper


def _summary(events: int, trials: int) -> dict[str, Any]:
    lower, upper = clopper_pearson_interval(events, trials)
    return {
        "events": int(events),
        "trials": int(trials),
        "observed_proportion": float(events / trials),
        "clopper_pearson_95": [lower, upper],
    }


def audit_nested_measurement_uncertainty(
    scored_rows: Sequence[Mapping[str, Any]],
    *,
    predicted_risk_threshold: float,
    source_audit_file_sha256: str,
    source_audit_content_sha256: str,
    scored_rows_file_sha256: str,
) -> dict[str, Any]:
    accepted = [
        row
        for row in scored_rows
        if not bool(row["candidate_hard_abstention"])
        and float(row["calibrated_risk"]) <= predicted_risk_threshold
    ]
    if not accepted:
        raise ValueError("Finite-sample audit has no accepted measurements.")
    row_events = sum(bool(row["invalid"]) for row in accepted)
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    cells: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in accepted:
        groups[str(row["reference_group_id"])].append(row)
        cells[str(row["conditional_cell"]["key"])].append(row)
    failing_groups = sum(any(bool(row["invalid"]) for row in values) for values in groups.values())
    cell_summaries = []
    for key, values in sorted(cells.items()):
        events = sum(bool(row["invalid"]) for row in values)
        cell_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in values:
            cell_groups[str(row["reference_group_id"])].append(row)
        failing_cell_groups = sum(
            any(bool(row["invalid"]) for row in group_rows)
            for group_rows in cell_groups.values()
        )
        cell_summaries.append(
            {
                "key": key,
                "values": values[0]["conditional_cell"]["values"],
                "nested_measurement_interval": _summary(events, len(values)),
                "independent_group_any_failure_interval": _summary(
                    failing_cell_groups, len(cell_groups)
                ),
            }
        )
    output = {
        "schema_version": "nostos-finite-sample-risk-audit/1.0",
        "status": "supplemental_uncertainty_complete",
        "source": {
            "confirmation_audit_file_sha256": source_audit_file_sha256,
            "confirmation_audit_content_sha256": source_audit_content_sha256,
            "confirmation_scored_rows_sha256": scored_rows_file_sha256,
        },
        "predicted_risk_threshold": float(predicted_risk_threshold),
        "accepted_measurements": len(accepted),
        "independent_groups": len(groups),
        "nested_measurement_interval": _summary(row_events, len(accepted)),
        "independent_group_any_failure_interval": _summary(
            failing_groups, len(groups)
        ),
        "supported_cell_intervals": cell_summaries,
        "interpretation": {
            "nested_measurement_interval": (
                "Describes emitted measurements in this benchmark; repeated measurements "
                "within a field are not independent biological samples."
            ),
            "independent_group_any_failure_interval": (
                "Exact interval for the proportion of comparable fields with at least one "
                "invalid accepted measurement. This interval is intentionally reported at "
                "the independent-group level and can be wide when few groups are available."
            ),
            "cluster_bootstrap_zero_event_warning": (
                "A percentile cluster bootstrap is identically zero when every observed field "
                "has zero events; it is an empirical resampling bound, not a population upper "
                "confidence limit."
            ),
        },
        "frozen_gate_decisions_changed": False,
        "profile_refit": False,
    }
    output["content_sha256"] = canonical_sha256(output)
    return output


# Backward-compatible name retained for the frozen FMD v1.4 audit script.
audit_nested_zero_event_uncertainty = audit_nested_measurement_uncertainty
