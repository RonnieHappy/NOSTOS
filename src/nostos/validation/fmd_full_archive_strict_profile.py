"""Compile the conservative post-v1.5 FMD full-archive support profile."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from nostos.validation.conditional_support_profile import (
    CONDITIONAL_COMPILER_VERSION,
    CONDITIONAL_PROFILE_SCHEMA,
    _apply_base_primary,
    apply_conditional_support,
    conditional_cell,
)
from nostos.validation.fmd_widefield_extended_confirmation import (
    clopper_pearson_interval,
)
from nostos.validation.validity_profile_compiler import (
    _operating_summary,
    canonical_sha256,
    read_jsonl,
    sha256_file,
    verify_profile,
    write_json,
    write_jsonl,
)


STRICT_SCHEMA = "nostos-fmd-full-archive-strict-support/1.0"
STRICT_COMPILER_VERSION = "nostos-fmd-full-archive-strict-compiler/1.0"


def _load_inputs(
    project_root: Path, config_path: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != STRICT_SCHEMA:
        raise ValueError("Unsupported FMD full-archive strict profile schema.")
    base_path = project_root / str(config["base_profile"]["path"])
    if sha256_file(base_path) != config["base_profile"]["file_sha256"]:
        raise ValueError("Strict-profile base file hash mismatch.")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    verify_profile(base)
    if base["content_sha256"] != config["base_profile"]["content_sha256"]:
        raise ValueError("Strict-profile base content hash mismatch.")
    if base["primary_score"] != config["base_profile"]["primary_score"]:
        raise ValueError("Strict-profile primary score mismatch.")
    if base["primary_endpoint_family"] != config["base_profile"]["primary_endpoint_family"]:
        raise ValueError("Strict-profile endpoint family mismatch.")
    threshold = float(base["operating_point"]["selected"]["predicted_risk_threshold"])
    if threshold != float(config["base_profile"]["predicted_risk_threshold"]):
        raise ValueError("Strict-profile threshold mismatch.")

    rows: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for source in config["development_sources"]:
        path = project_root / str(source["path"])
        observed = sha256_file(path)
        if observed != str(source["sha256"]):
            raise ValueError(f"Strict-profile development source changed: {source['path']}")
        source_rows = read_jsonl(path)
        rows.extend(source_rows)
        receipts.append(
            {
                "path": str(source["path"]),
                "bytes": path.stat().st_size,
                "sha256": observed,
                "rows": len(source_rows),
                "fields": [int(value) for value in source["fields"]],
            }
        )
    failure_path = project_root / str(config["failure_receipt"]["path"])
    if sha256_file(failure_path) != config["failure_receipt"]["sha256"]:
        raise ValueError("The retained v1.5 failure receipt changed.")
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    if failure.get("status") != config["failure_receipt"]["required_status"]:
        raise ValueError("The v1.5 failure receipt status changed.")
    return config, base, rows, receipts


def compile_strict_profile(
    project_root: Path, config_path: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config, base, rows, receipts = _load_inputs(project_root, config_path)
    primary = _apply_base_primary(rows, base)
    expected_groups = {
        f"{config['source']['acquisition_modality']}_{config['source']['sample']}|fov{field}"
        for field in config["source"]["development_fields"]
    }
    observed_groups = {str(row["reference_group_id"]) for row in primary}
    if observed_groups != expected_groups:
        raise ValueError("Strict-profile groups differ from all nineteen frozen fields.")
    if len(primary) != 1140:
        raise ValueError(f"Strict-profile expected 1140 eligible primary rows, found {len(primary)}.")

    compiler = config["cell_compiler"]
    dimensions = compiler["cell_dimensions"]
    threshold = float(base["operating_point"]["selected"]["predicted_risk_threshold"])
    cells: dict[str, list[dict[str, Any]]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for row in primary:
        payload = conditional_cell(row, dimensions)
        key = str(payload["key"])
        payloads[key] = payload
        cells.setdefault(key, []).append(row)

    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for index, key in enumerate(sorted(cells)):
        summary = _operating_summary(
            cells[key],
            threshold=threshold,
            draws=int(compiler["bootstrap_replicates"]),
            seed=int(compiler["bootstrap_seed"]) + index,
        )
        accepted = [
            row
            for row in cells[key]
            if not bool(row["candidate_hard_abstention"])
            and float(row["calibrated_risk"]) <= threshold
        ]
        failing_groups = sorted(
            {str(row["reference_group_id"]) for row in accepted if bool(row["invalid"])}
        )
        interval = clopper_pearson_interval(
            len(failing_groups),
            len(expected_groups),
            confidence=float(compiler["confidence_level"]),
        )
        checks = {
            "minimum_accepted_cases": summary["accepted"]
            >= int(compiler["minimum_accepted_cases_per_cell"]),
            "required_accepted_independent_groups": summary[
                "accepted_independent_groups"
            ]
            == int(compiler["required_accepted_independent_groups_per_cell"]),
            "maximum_observed_risk": summary["risk"] is not None
            and float(summary["risk"]) <= float(compiler["maximum_observed_risk_per_cell"]),
            "maximum_fields_with_any_accepted_failure": len(failing_groups)
            <= int(compiler["maximum_fields_with_any_accepted_failure_per_cell"]),
            "maximum_two_sided_exact_field_failure_upper95": interval[1]
            <= float(compiler["maximum_two_sided_exact_field_failure_upper95_per_cell"]),
        }
        payload = {
            **payloads[key],
            "development_summary": summary,
            "field_event_summary": {
                "fields": len(expected_groups),
                "fields_with_any_accepted_failure": len(failing_groups),
                "failing_groups": failing_groups,
                "two_sided_exact_ci95": list(interval),
            },
            "checks": checks,
            "supported": bool(all(checks.values())),
        }
        (supported if payload["supported"] else unsupported).append(payload)

    profile: dict[str, Any] = {
        "schema_version": CONDITIONAL_PROFILE_SCHEMA,
        "compiler_version": CONDITIONAL_COMPILER_VERSION,
        "strict_compiler_version": STRICT_COMPILER_VERSION,
        "protocol_id": config["protocol_id"],
        "status": "operating_point_selected" if supported else "no_operating_point",
        "claim_boundary": dict(config["scope"]),
        "base_profile_content_sha256": base["content_sha256"],
        "base_profile_file_sha256": config["base_profile"]["file_sha256"],
        "base_predicted_risk_threshold": threshold,
        "primary_score": base["primary_score"],
        "primary_endpoint_family": base["primary_endpoint_family"],
        "cell_dimensions": deepcopy(dimensions),
        "supported_cells": supported,
        "unsupported_cells": unsupported,
        "development": {
            "independent_groups": sorted(observed_groups),
            "independent_group_count": len(observed_groups),
            "eligible_primary_cases": len(primary),
            "source_receipts": receipts,
        },
        "confirmation_gates": dict(config["confirmation_gates"]),
        "config_sha256": canonical_sha256(config),
    }
    profile["content_sha256"] = canonical_sha256(profile)
    scored = apply_conditional_support(
        rows, base_profile=base, conditional_profile=profile
    )
    overall = _operating_summary(
        scored,
        threshold=threshold,
        draws=int(compiler["bootstrap_replicates"]),
        seed=int(compiler["bootstrap_seed"]) + 1000,
    )
    failing_groups = sorted(
        {
            str(row["reference_group_id"])
            for row in scored
            if not bool(row["candidate_hard_abstention"])
            and float(row["calibrated_risk"]) <= threshold
            and bool(row["invalid"])
        }
    )
    gates = compiler["development_gates"]
    checks = {
        "exactly_three_supported_cells": len(supported) == 3,
        "minimum_coverage": overall["coverage"] >= float(gates["minimum_coverage"]),
        "maximum_observed_risk": overall["risk"] is not None
        and float(overall["risk"]) <= float(gates["maximum_observed_risk"]),
        "maximum_fields_with_any_accepted_failure": len(failing_groups)
        <= int(gates["maximum_fields_with_any_accepted_failure"]),
    }
    if not all(checks.values()):
        profile = deepcopy(profile)
        profile.pop("content_sha256", None)
        profile["status"] = "no_operating_point"
        profile["content_sha256"] = canonical_sha256(profile)
    profile["development_operating_point"] = {
        **overall,
        "fields_with_any_accepted_failure": len(failing_groups),
        "failing_groups": failing_groups,
        "checks": checks,
        "passes": bool(all(checks.values())),
    }
    old_hash = profile.pop("content_sha256", None)
    del old_hash
    profile["content_sha256"] = canonical_sha256(profile)
    audit = {
        "schema_version": "nostos-fmd-full-archive-strict-development-audit/1.0",
        "compiler_version": STRICT_COMPILER_VERSION,
        "status": profile["status"],
        "profile_content_sha256": profile["content_sha256"],
        "base_profile_content_sha256": base["content_sha256"],
        "supported_cell_count": len(supported),
        "unsupported_cell_count": len(unsupported),
        "development_operating_point": profile["development_operating_point"],
        "supported_cells": supported,
        "unsupported_cells": unsupported,
        "checks": checks,
    }
    audit["content_sha256"] = canonical_sha256(audit)
    receipt = {
        "schema_version": "nostos-fmd-full-archive-strict-development-receipt/1.0",
        "status": profile["status"],
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "base_profile_content_sha256": base["content_sha256"],
        "development_sources": receipts,
        "row_count": len(rows),
        "primary_row_count": len(primary),
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    return profile, audit, scored, receipt


def write_strict_profile(
    project_root: Path, config_path: Path, output_directory: Path
) -> dict[str, Any]:
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite strict profile: {output_directory}")
    profile, audit, scored, receipt = compile_strict_profile(project_root, config_path)
    output_directory.mkdir(parents=True)
    profile_path = output_directory / "strict_support_profile.json"
    audit_path = output_directory / "development_audit.json"
    scored_path = output_directory / "development_scored.jsonl"
    receipt_path = output_directory / "development_receipt.json"
    write_json(profile_path, profile)
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    write_json(receipt_path, receipt)
    return {
        "status": profile["status"],
        "profile": str(profile_path),
        "profile_sha256": sha256_file(profile_path),
        "audit": str(audit_path),
        "scored": str(scored_path),
        "receipt": str(receipt_path),
        "supported_cells": [cell["values"] for cell in profile["supported_cells"]],
        "development_operating_point": profile["development_operating_point"],
    }
