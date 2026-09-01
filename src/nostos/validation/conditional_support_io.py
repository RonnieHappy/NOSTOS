"""File-oriented public interface for hierarchical conditional-support profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nostos.validation.conditional_support_profile import (
    audit_conditional_support_profile,
    compile_conditional_support_profile,
)
from nostos.validation.finite_sample_risk import audit_nested_measurement_uncertainty
from nostos.validation.validity_profile_compiler import (
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)


def compile_conditional_support_files(
    development_rows_path: Path,
    config_path: Path,
    base_profile_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    rows = read_jsonl(development_rows_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = json.loads(base_profile_path.read_text(encoding="utf-8"))
    profile, audit, scored = compile_conditional_support_profile(
        rows,
        config=config,
        base_profile=base,
        source_receipt={
            "name": development_rows_path.name,
            "bytes": development_rows_path.stat().st_size,
            "sha256": sha256_file(development_rows_path),
        },
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    profile_path = output_directory / "conditional_support_profile.json"
    audit_path = output_directory / "development_audit.json"
    scored_path = output_directory / "development_scored.jsonl"
    write_json(profile_path, profile)
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    return {
        "status": profile["status"],
        "profile": str(profile_path),
        "profile_file_sha256": sha256_file(profile_path),
        "development_audit": str(audit_path),
        "development_scored": str(scored_path),
        "supported_cells": len(profile["supported_cells"]),
        "unsupported_cells": len(profile["unsupported_cells"]),
    }


def audit_conditional_support_files(
    confirmation_rows_path: Path,
    config_path: Path,
    base_profile_path: Path,
    conditional_profile_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    rows = read_jsonl(confirmation_rows_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = json.loads(base_profile_path.read_text(encoding="utf-8"))
    conditional = json.loads(conditional_profile_path.read_text(encoding="utf-8"))
    audit, scored = audit_conditional_support_profile(
        rows,
        config=config,
        base_profile=base,
        conditional_profile=conditional,
        source_receipt={
            "name": confirmation_rows_path.name,
            "bytes": confirmation_rows_path.stat().st_size,
            "sha256": sha256_file(confirmation_rows_path),
        },
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    audit_path = output_directory / "confirmation_audit.json"
    scored_path = output_directory / "confirmation_scored.jsonl"
    uncertainty_path = output_directory / "finite_sample_uncertainty.json"
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    uncertainty = audit_nested_measurement_uncertainty(
        scored,
        predicted_risk_threshold=float(
            conditional["development_operating_point"]["predicted_risk_threshold"]
        ),
        source_audit_file_sha256=sha256_file(audit_path),
        source_audit_content_sha256=str(audit["content_sha256"]),
        scored_rows_file_sha256=sha256_file(scored_path),
    )
    write_json(uncertainty_path, uncertainty)
    return {
        "status": audit["status"],
        "confirmation_audit": str(audit_path),
        "confirmation_audit_sha256": sha256_file(audit_path),
        "confirmation_scored": str(scored_path),
        "finite_sample_uncertainty": str(uncertainty_path),
        "finite_sample_uncertainty_sha256": sha256_file(uncertainty_path),
        "checks": audit["checks"],
    }
