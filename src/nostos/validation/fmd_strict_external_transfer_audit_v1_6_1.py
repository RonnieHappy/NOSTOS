"""Audit-only repair for zero-coverage FMD strict external transfer branches.

The locked v1.6 measurement runner completed successfully. Its first audit
invocation failed before writing output because the field-event helper tried to
construct an exact row-level binomial interval when a source emitted zero
measurements. This module changes only that undefined reporting branch: risk
and its descriptive row interval become ``None`` when accepted count is zero.
All evidence rows, profiles, thresholds, support cells and gates remain frozen.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import nostos.validation.fmd_strict_external_transfer as locked_auditor
from nostos.validation.fmd_strict_external_transfer import load_transfer_inputs
from nostos.validation.fmd_widefield_extended_confirmation import (
    clopper_pearson_interval,
)
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)


PATCHED_AUDITOR_VERSION = "nostos-fmd-strict-external-transfer-auditor/1.1"


def field_event_summary_zero_safe(
    scored: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    expected_groups: Sequence[str],
    confidence: float,
) -> dict[str, Any]:
    """Summarize independent-field events without inventing zero-coverage risk."""

    by_group: dict[str, list[Mapping[str, Any]]] = {
        str(group): [] for group in expected_groups
    }
    for row in scored:
        group = str(row["reference_group_id"])
        if group in by_group:
            by_group[group].append(row)
    fields = []
    total_accepted = 0
    total_invalid = 0
    events = 0
    for group in sorted(by_group):
        accepted = [
            row
            for row in by_group[group]
            if not bool(row["candidate_hard_abstention"])
            and float(row["calibrated_risk"]) <= float(threshold)
        ]
        invalid = sum(bool(row["invalid"]) for row in accepted)
        event = invalid > 0
        total_accepted += len(accepted)
        total_invalid += invalid
        events += int(event)
        fields.append(
            {
                "reference_group_id": group,
                "accepted": len(accepted),
                "invalid": invalid,
                "any_accepted_failure": event,
            }
        )
    field_ci = clopper_pearson_interval(events, len(fields), confidence=confidence)
    if total_accepted:
        row_ci: list[float] | None = list(
            clopper_pearson_interval(
                total_invalid, total_accepted, confidence=confidence
            )
        )
        risk: float | None = total_invalid / total_accepted
    else:
        row_ci = None
        risk = None
    return {
        "independent_groups": len(fields),
        "fields_with_any_accepted_failure": events,
        "field_event_rate": events / len(fields),
        "field_event_exact_ci": list(field_ci),
        "accepted_emissions": total_accepted,
        "invalid_accepted_emissions": total_invalid,
        "accepted_emission_risk": risk,
        "accepted_emission_exact_ci_descriptive": row_ci,
        "zero_coverage": total_accepted == 0,
        "fields": fields,
    }


def audit_transfer_rows_v1_6_1(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    development_config: Mapping[str, Any],
    base_profile: Mapping[str, Any],
    strict_profile: Mapping[str, Any],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run the locked audit with the zero-coverage reporting branch repaired."""

    original = locked_auditor._field_event_summary
    locked_auditor._field_event_summary = field_event_summary_zero_safe
    try:
        audit, scored = locked_auditor.audit_transfer_rows(
            rows,
            config=config,
            development_config=development_config,
            base_profile=base_profile,
            strict_profile=strict_profile,
            source_receipt=source_receipt,
        )
    finally:
        locked_auditor._field_event_summary = original
    repaired = deepcopy(audit)
    repaired.pop("content_sha256", None)
    repaired["auditor_version"] = PATCHED_AUDITOR_VERSION
    repaired["audit_only_repair"] = {
        "status": "post_measurement_reporting_defect_repaired",
        "original_exception": "ValueError: Exact binomial interval requires 0 <= events <= total and total > 0.",
        "trigger": "A source-specific branch emitted zero accepted measurements.",
        "change": "When accepted count is zero, accepted-emission risk and its descriptive exact interval are serialized as null and zero_coverage is true.",
        "unchanged": [
            "evidence rows",
            "source selection",
            "measurements",
            "invalidity labels",
            "profiles",
            "support cells",
            "thresholds",
            "comparators",
            "gates"
        ]
    }
    repaired["content_sha256"] = canonical_sha256(repaired)
    return repaired, scored


def run_transfer_audit_v1_6_1(
    rows_path: Path, config_path: Path, output_directory: Path
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    config, development, base, strict, _measurement, _refs = load_transfer_inputs(
        project_root, config_path
    )
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite transfer audit: {output_directory}")
    rows = read_jsonl(rows_path)
    audit, scored = audit_transfer_rows_v1_6_1(
        rows,
        config=config,
        development_config=development,
        base_profile=base,
        strict_profile=strict,
        source_receipt={
            "rows": {
                "path": rows_path.name,
                "bytes": rows_path.stat().st_size,
                "sha256": sha256_file(rows_path),
            }
        },
    )
    output_directory.mkdir(parents=True)
    audit_path = output_directory / "external_transfer_audit.json"
    scored_path = output_directory / "external_transfer_scored.jsonl"
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    return {
        "status": audit["status"],
        "auditor_version": audit["auditor_version"],
        "audit": str(audit_path),
        "audit_sha256": sha256_file(audit_path),
        "scored": str(scored_path),
        "checks": audit["checks"],
        "per_source": [
            {
                "dataset_key": item["dataset_key"],
                "passes": item["passes"],
                "field_event_summary": item["field_event_summary"],
            }
            for item in audit["per_source"]
        ],
        "combined_field_event_summary": audit["combined"]["field_event_summary"],
    }

