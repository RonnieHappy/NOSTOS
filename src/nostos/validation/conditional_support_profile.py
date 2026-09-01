"""Hierarchical support overlays for an immutable calibrated-risk profile.

The overlay addresses pooled-risk masking: a base profile may pass overall while
one declared acquisition-by-measurement cell fails consistently.  Cells are
learned from grouped development evidence only and become hard abstentions when
unsupported, unsafe, missing or unseen at application time.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any, Mapping, Sequence

from nostos.validation.validity_profile_compiler import (
    _cluster_bootstrap_aurc_difference,
    _matched_count_summary,
    _operating_summary,
    _prediction_metrics,
    _stratified_operating_summaries,
    apply_score_profile,
    canonical_sha256,
    validate_contract_rows,
    verify_profile,
)


CONDITIONAL_PROFILE_SCHEMA = "nostos-conditional-support-profile/1.0"
CONDITIONAL_COMPILER_VERSION = "nostos-conditional-support-compiler/1.0"


def _eligible(row: Mapping[str, Any]) -> bool:
    return bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])


def _dimension_value(row: Mapping[str, Any], dimension: Mapping[str, Any]) -> Any:
    source = str(dimension["source"])
    key = str(dimension["key"])
    if source == "row":
        if key not in row:
            raise ValueError(f"Conditional-support row lacks {key!r}.")
        value = row[key]
    elif source == "metadata":
        metadata = row.get("metadata", {})
        if not isinstance(metadata, Mapping) or key not in metadata:
            raise ValueError(f"Conditional-support metadata lacks {key!r}.")
        value = metadata[key]
    else:
        raise ValueError(f"Unsupported conditional-support dimension source: {source!r}")
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"Conditional-support dimension {key!r} is empty.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Conditional-support dimension {key!r} is non-finite.")
    return value


def conditional_cell(
    row: Mapping[str, Any], dimensions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    values = [_dimension_value(row, dimension) for dimension in dimensions]
    payload = {
        "dimensions": [
            {"source": str(item["source"]), "key": str(item["key"])}
            for item in dimensions
        ],
        "values": values,
    }
    payload["key"] = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return payload


def _apply_base_primary(
    rows: Sequence[Mapping[str, Any]], base_profile: Mapping[str, Any]
) -> list[dict[str, Any]]:
    primary_family = str(base_profile["primary_endpoint_family"])
    primary_score = str(base_profile["primary_score"])
    selected = [
        row
        for row in rows
        if _eligible(row) and str(row["endpoint_family"]) == primary_family
    ]
    return apply_score_profile(
        selected,
        score_key=primary_score,
        risk_maps=base_profile["calibration"]["candidates"][primary_score]["risk_maps"],
        stratum_support=base_profile.get("acquisition_stratum_support"),
    )


def _apply_base_comparator(
    rows: Sequence[Mapping[str, Any]], base_profile: Mapping[str, Any]
) -> list[dict[str, Any]]:
    primary_family = str(base_profile["primary_endpoint_family"])
    score = "conventional_acquisition_qc"
    selected = [
        row
        for row in rows
        if _eligible(row) and str(row["endpoint_family"]) == primary_family
    ]
    return apply_score_profile(
        selected,
        score_key=score,
        risk_maps=base_profile["calibration"]["candidates"][score]["risk_maps"],
        stratum_support=base_profile.get("acquisition_stratum_support"),
    )


def apply_conditional_support(
    rows: Sequence[Mapping[str, Any]],
    *,
    base_profile: Mapping[str, Any],
    conditional_profile: Mapping[str, Any],
) -> list[dict[str, Any]]:
    verify_profile(base_profile)
    verify_conditional_profile(conditional_profile)
    if conditional_profile["base_profile_content_sha256"] != base_profile["content_sha256"]:
        raise ValueError("Conditional-support overlay belongs to a different base profile.")
    dimensions = conditional_profile["cell_dimensions"]
    supported = {str(item["key"]) for item in conditional_profile["supported_cells"]}
    output: list[dict[str, Any]] = []
    for source in _apply_base_primary(rows, base_profile):
        row = deepcopy(source)
        cell = conditional_cell(row, dimensions)
        base_hard = bool(row["candidate_hard_abstention"])
        cell_supported = str(cell["key"]) in supported
        row["base_candidate_hard_abstention"] = base_hard
        row["base_calibrated_risk"] = float(row["calibrated_risk"])
        row["conditional_cell"] = cell
        row["conditional_cell_supported"] = cell_supported
        if not cell_supported:
            row["candidate_hard_abstention"] = True
            row["calibrated_risk"] = 1.0
            row["conditional_hard_abstention_reason"] = (
                "unsupported_or_unsafe_acquisition_measurement_cell"
            )
        else:
            row["candidate_hard_abstention"] = base_hard
            row["conditional_hard_abstention_reason"] = None
        output.append(row)
    output.sort(key=lambda row: str(row["case_id"]))
    return output


def compile_conditional_support_profile(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    base_profile: Mapping[str, Any],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    verify_profile(base_profile)
    validate_contract_rows(rows, score_keys=base_profile["score_candidates"])
    base_spec = config["base_profile"]
    if base_spec["content_sha256"] != base_profile["content_sha256"]:
        raise ValueError("Base profile content differs from the v1.4 protocol lock.")
    if str(base_spec["primary_score"]) != str(base_profile["primary_score"]):
        raise ValueError("Base-profile primary score differs from the protocol lock.")
    threshold = float(base_profile["operating_point"]["selected"]["predicted_risk_threshold"])
    if threshold != float(base_spec["predicted_risk_threshold"]):
        raise ValueError("Base-profile operating threshold differs from the protocol lock.")

    compiler = config["conditional_compiler"]
    dimensions = compiler["cell_dimensions"]
    base_rows = _apply_base_primary(rows, base_profile)
    expected_groups = {
        f"{config['source']['acquisition_modality']}_{config['source']['sample']}|fov{int(field)}"
        for field in config["selection"]["development_fields"]
    }
    observed_groups = {str(row["reference_group_id"]) for row in base_rows}
    if observed_groups != expected_groups:
        raise ValueError("Conditional development groups differ from the frozen split.")

    cells: dict[str, list[dict[str, Any]]] = {}
    cell_payloads: dict[str, dict[str, Any]] = {}
    for row in base_rows:
        cell = conditional_cell(row, dimensions)
        key = str(cell["key"])
        cell_payloads[key] = cell
        cells.setdefault(key, []).append(row)

    supported_cells: list[dict[str, Any]] = []
    unsupported_cells: list[dict[str, Any]] = []
    for index, key in enumerate(sorted(cells)):
        summary = _operating_summary(
            cells[key],
            threshold=threshold,
            draws=int(compiler["bootstrap_replicates"]),
            seed=int(compiler["bootstrap_seed"]) + index,
        )
        checks = {
            "minimum_accepted_cases": summary["accepted"]
            >= int(compiler["minimum_accepted_cases_per_cell"]),
            "minimum_accepted_independent_groups": summary["accepted_independent_groups"]
            >= int(compiler["minimum_accepted_independent_groups_per_cell"]),
            "maximum_observed_risk": summary["risk"] is not None
            and float(summary["risk"]) <= float(compiler["maximum_observed_risk_per_cell"]),
            "maximum_cluster_bootstrap_risk_upper95": summary[
                "cluster_bootstrap_risk_upper95"
            ]
            is not None
            and float(summary["cluster_bootstrap_risk_upper95"])
            <= float(compiler["maximum_cluster_bootstrap_risk_upper95_per_cell"]),
        }
        payload = {
            **cell_payloads[key],
            "development_summary": summary,
            "checks": checks,
            "supported": bool(all(checks.values())),
        }
        (supported_cells if payload["supported"] else unsupported_cells).append(payload)

    draft_profile: dict[str, Any] = {
        "schema_version": CONDITIONAL_PROFILE_SCHEMA,
        "compiler_version": CONDITIONAL_COMPILER_VERSION,
        "protocol_id": config["protocol_id"],
        "status": "pending_development_gate",
        "claim_boundary": dict(config["scope"]),
        "base_profile_content_sha256": base_profile["content_sha256"],
        "base_profile_file_sha256": str(base_spec["file_sha256"]),
        "base_predicted_risk_threshold": threshold,
        "primary_score": base_profile["primary_score"],
        "primary_endpoint_family": base_profile["primary_endpoint_family"],
        "cell_dimensions": deepcopy(dimensions),
        "supported_cells": supported_cells,
        "unsupported_cells": unsupported_cells,
        "development": {
            "independent_groups": sorted(observed_groups),
            "independent_group_count": len(observed_groups),
            "eligible_primary_cases": len(base_rows),
            "source_receipt": dict(source_receipt or {}),
        },
        "confirmation_gates": dict(config["confirmation_gates"]),
        "config_sha256": canonical_sha256(config),
    }
    draft_profile["content_sha256"] = canonical_sha256(draft_profile)
    temporary_profile = deepcopy(draft_profile)
    temporary_profile.pop("content_sha256")
    temporary_profile["status"] = "operating_point_selected"
    temporary_profile["content_sha256"] = canonical_sha256(temporary_profile)
    final_rows = apply_conditional_support(
        rows,
        base_profile=base_profile,
        conditional_profile=temporary_profile,
    )
    development_summary = _operating_summary(
        final_rows,
        threshold=threshold,
        draws=int(compiler["bootstrap_replicates"]),
        seed=int(compiler["bootstrap_seed"]) + 1000,
    )
    gates = compiler["development_gates"]
    checks = {
        "at_least_one_supported_cell": bool(supported_cells),
        "minimum_coverage": development_summary["coverage"]
        >= float(gates["minimum_coverage"]),
        "maximum_observed_risk": development_summary["risk"] is not None
        and float(development_summary["risk"]) <= float(gates["maximum_observed_risk"]),
        "maximum_cluster_bootstrap_risk_upper95": development_summary[
            "cluster_bootstrap_risk_upper95"
        ]
        is not None
        and float(development_summary["cluster_bootstrap_risk_upper95"])
        <= float(gates["maximum_cluster_bootstrap_risk_upper95"]),
    }
    status = "operating_point_selected" if all(checks.values()) else "no_operating_point"
    profile = deepcopy(draft_profile)
    profile.pop("content_sha256")
    profile["status"] = status
    profile["development_operating_point"] = {
        **development_summary,
        "checks": checks,
        "passes": bool(all(checks.values())),
    }
    profile["content_sha256"] = canonical_sha256(profile)
    if status == "operating_point_selected":
        final_rows = apply_conditional_support(
            rows, base_profile=base_profile, conditional_profile=profile
        )
    audit = {
        "schema_version": "nostos-conditional-support-development-audit/1.0",
        "status": status,
        "profile_content_sha256": profile["content_sha256"],
        "base_profile_content_sha256": base_profile["content_sha256"],
        "supported_cell_count": len(supported_cells),
        "unsupported_cell_count": len(unsupported_cells),
        "development_operating_point": profile["development_operating_point"],
        "supported_cells": supported_cells,
        "unsupported_cells": unsupported_cells,
        "checks": checks,
    }
    audit["content_sha256"] = canonical_sha256(audit)
    return profile, audit, final_rows


def verify_conditional_profile(profile: Mapping[str, Any]) -> None:
    if profile.get("schema_version") != CONDITIONAL_PROFILE_SCHEMA:
        raise ValueError("Unsupported conditional-support profile schema.")
    expected = str(profile.get("content_sha256", ""))
    content = dict(profile)
    content.pop("content_sha256", None)
    if not expected or canonical_sha256(content) != expected:
        raise ValueError("Conditional-support profile content hash mismatch.")
    if profile.get("status") != "operating_point_selected":
        raise ValueError("Conditional-support profile has no deployable operating point.")


def audit_conditional_support_profile(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    base_profile: Mapping[str, Any],
    conditional_profile: Mapping[str, Any],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verify_profile(base_profile)
    verify_conditional_profile(conditional_profile)
    validate_contract_rows(rows, score_keys=base_profile["score_candidates"])
    if conditional_profile["config_sha256"] != canonical_sha256(config):
        raise ValueError("Conditional profile and confirmation protocol differ.")
    eligible_groups = {
        str(row["reference_group_id"])
        for row in rows
        if _eligible(row)
        and str(row["endpoint_family"])
        == str(conditional_profile["primary_endpoint_family"])
    }
    overlap = sorted(
        eligible_groups & set(conditional_profile["development"]["independent_groups"])
    )
    if overlap:
        raise ValueError(f"Conditional development-confirmation group leakage: {overlap}")

    primary = apply_conditional_support(
        rows, base_profile=base_profile, conditional_profile=conditional_profile
    )
    comparator = _apply_base_comparator(rows, base_profile)
    threshold = float(conditional_profile["base_predicted_risk_threshold"])
    gates = config["confirmation_gates"]
    primary_summary = _operating_summary(
        primary,
        threshold=threshold,
        draws=int(gates["bootstrap_replicates"]),
        seed=int(gates["bootstrap_seed"]),
    )
    comparator_summary = _matched_count_summary(
        comparator, accepted_count=int(primary_summary["accepted"])
    )
    tie_bounds = comparator_summary["tie_robust_risk_bounds"]
    conservative_reduction = None
    deterministic_reduction = None
    if primary_summary["risk"] is not None and comparator_summary["risk"]:
        deterministic_reduction = 1.0 - float(primary_summary["risk"]) / float(
            comparator_summary["risk"]
        )
    if primary_summary["risk"] is not None and tie_bounds is not None:
        best = float(tie_bounds["best_case_risk"])
        if best > 0:
            conservative_reduction = 1.0 - float(primary_summary["risk"]) / best
    aurc = _cluster_bootstrap_aurc_difference(
        primary,
        comparator,
        draws=int(gates["bootstrap_replicates"]),
        seed=int(gates["bootstrap_seed"]) + 1,
    )
    aurc["definition"] = (
        "acquisition_qc_AURC_minus_conditional_primary_AURC; positive favors NOSTOS"
    )

    supported_keys = {str(cell["key"]) for cell in conditional_profile["supported_cells"]}
    cell_summaries: list[dict[str, Any]] = []
    for index, cell in enumerate(conditional_profile["supported_cells"]):
        cell_rows = [
            row for row in primary if str(row["conditional_cell"]["key"]) == str(cell["key"])
        ]
        summary = _operating_summary(
            cell_rows,
            threshold=threshold,
            draws=int(gates["bootstrap_replicates"]),
            seed=int(gates["bootstrap_seed"]) + 100 + index,
        )
        checks = {
            "minimum_accepted_cases": summary["accepted"]
            >= int(gates["minimum_accepted_cases_per_supported_cell"]),
            "minimum_accepted_independent_groups": summary["accepted_independent_groups"]
            >= int(gates["minimum_accepted_independent_groups_per_supported_cell"]),
            "maximum_observed_risk": summary["risk"] is not None
            and float(summary["risk"])
            <= float(gates["maximum_observed_risk_per_supported_cell"]),
            "maximum_cluster_bootstrap_risk_upper95": summary[
                "cluster_bootstrap_risk_upper95"
            ]
            is not None
            and float(summary["cluster_bootstrap_risk_upper95"])
            <= float(gates["maximum_cluster_bootstrap_risk_upper95_per_supported_cell"]),
        }
        cell_summaries.append(
            {
                "key": cell["key"],
                "values": cell["values"],
                "summary": summary,
                "checks": checks,
                "passes": bool(all(checks.values())),
            }
        )

    checks = {
        "minimum_independent_groups": len(eligible_groups)
        >= int(gates["minimum_independent_groups"]),
        "minimum_coverage": primary_summary["coverage"] >= float(gates["minimum_coverage"]),
        "maximum_observed_risk": primary_summary["risk"] is not None
        and float(primary_summary["risk"]) <= float(gates["maximum_observed_risk"]),
        "maximum_cluster_bootstrap_risk_upper95": primary_summary[
            "cluster_bootstrap_risk_upper95"
        ]
        is not None
        and float(primary_summary["cluster_bootstrap_risk_upper95"])
        <= float(gates["maximum_cluster_bootstrap_risk_upper95"]),
        "minimum_relative_risk_reduction_vs_acquisition_qc": conservative_reduction
        is not None
        and conservative_reduction
        >= float(gates["minimum_relative_risk_reduction_vs_acquisition_qc"]),
        "minimum_invalid_acquisition_qc_emissions": comparator_summary["invalid"]
        >= int(gates["minimum_invalid_acquisition_qc_emissions"]),
        "positive_aurc_difference": (
            not bool(gates["require_positive_aurc_difference"])
            or float(aurc["observed"]) > 0.0
        ),
        "aurc_bootstrap_ci_lower_above_zero": (
            not bool(gates["require_aurc_bootstrap_ci_lower_above_zero"])
            or float(aurc["bootstrap_ci95"][0]) > 0.0
        ),
        "every_supported_cell_passes": bool(cell_summaries)
        and all(bool(cell["passes"]) for cell in cell_summaries),
        "no_unregistered_supported_cell": all(
            str(row["conditional_cell"]["key"]) in supported_keys
            for row in primary
            if not bool(row["candidate_hard_abstention"])
            and float(row["calibrated_risk"]) <= threshold
        ),
    }
    status = "pass" if all(checks.values()) else "fail"
    comparator_by_id = {str(row["case_id"]): row for row in comparator}
    scored = []
    for row in primary:
        clone = deepcopy(row)
        comparison = comparator_by_id[str(row["case_id"])]
        clone["acquisition_qc_calibrated_risk"] = float(comparison["calibrated_risk"])
        clone["acquisition_qc_candidate_hard_abstention"] = bool(
            comparison["candidate_hard_abstention"]
        )
        scored.append(clone)
    audit = {
        "schema_version": "nostos-conditional-support-confirmation-audit/1.0",
        "status": status,
        "protocol_id": config["protocol_id"],
        "claim_boundary": config["scope"],
        "base_profile_content_sha256": base_profile["content_sha256"],
        "conditional_profile_content_sha256": conditional_profile["content_sha256"],
        "confirmation": {
            "independent_groups": sorted(eligible_groups),
            "independent_group_count": len(eligible_groups),
            "development_group_overlap": overlap,
            "eligible_primary_cases": len(primary),
            "source_receipt": dict(source_receipt or {}),
        },
        "primary_operating_point": primary_summary,
        "supported_cell_audit": cell_summaries,
        "acquisition_qc_matched_count": comparator_summary,
        "relative_risk_reduction_vs_acquisition_qc": {
            "deterministic_tie_break_estimate": deterministic_reduction,
            "conservative_lower_bound_over_boundary_tie": conservative_reduction,
        },
        "risk_coverage": {
            "primary_metrics": _prediction_metrics(primary),
            "acquisition_qc_metrics": _prediction_metrics(comparator),
            "cluster_bootstrap_aurc_difference": aurc,
        },
        "descriptive_strata": _stratified_operating_summaries(
            primary, threshold=threshold
        ),
        "checks": checks,
    }
    audit["content_sha256"] = canonical_sha256(audit)
    return audit, scored
