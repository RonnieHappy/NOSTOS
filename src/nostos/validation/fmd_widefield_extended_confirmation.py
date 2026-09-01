"""Prospective no-refit extension of the FMD widefield v1.4 confirmation."""

from __future__ import annotations

import hashlib
import json
import tarfile
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.stats import beta

from nostos.validation.conditional_support_profile import (
    audit_conditional_support_profile,
    verify_conditional_profile,
)
from nostos.validation.fmd_validity_profile import (
    _convert_dimensionless_rows,
    _internal_measurement_config,
    measure_selected_with_mild_probes,
)
from nostos.validation.fmd_widefield_conditional_run import (
    _adapter_confirmation_config,
    _load_locked_inputs,
)
from nostos.validation.fmd_widefield_profile import (
    FMD_WIDEFIELD_ADAPTER_VERSION,
    _read_grayscale_member,
    index_widefield_split,
)
from nostos.validation.paired_acquisition_support import (
    audit_pair_registration,
    evaluate_precomputed_pair,
    shared_spectral_band_cycles_per_mm,
)
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)


EXTENDED_SCHEMA = "nostos-fmd-widefield-extended-confirmation/1.0"
EXTENDED_LOCK_SCHEMA = "nostos-fmd-widefield-extended-confirmation-lock/1.0"
EXTENDED_RUNNER_VERSION = "nostos-fmd-widefield-extended-confirmation-runner/1.0"
EXTENDED_AUDITOR_VERSION = "nostos-fmd-widefield-extended-confirmation-auditor/1.0"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def derive_field_order(*, seed: int, excluded_field: int) -> list[int]:
    """Return the original deterministic FMD field order without reading pixels."""

    fields = [field for field in range(1, 21) if field != int(excluded_field)]
    return sorted(
        fields,
        key=lambda field: _hash_text(f"{int(seed)}|WideField_BPAE_R|fov{field}"),
    )


def derive_realization_indices(*, seed: int, field: int) -> list[int]:
    """Return the four original deterministic realization indices for a field."""

    ranked = sorted(
        range(50),
        key=lambda index: _hash_text(
            f"{int(seed)}|fov{int(field)}|realization{index}"
        ),
    )
    return sorted(ranked[:4])


def clopper_pearson_interval(
    events: int, total: int, *, confidence: float = 0.95
) -> tuple[float, float]:
    """Return a two-sided exact binomial confidence interval."""

    events = int(events)
    total = int(total)
    if total <= 0 or events < 0 or events > total:
        raise ValueError("Exact binomial interval requires 0 <= events <= total and total > 0.")
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError("Confidence level must lie strictly between zero and one.")
    alpha = 1.0 - float(confidence)
    lower = 0.0 if events == 0 else float(beta.ppf(alpha / 2.0, events, total - events + 1))
    upper = 1.0 if events == total else float(
        beta.ppf(1.0 - alpha / 2.0, events + 1, total - events)
    )
    return lower, upper


def verify_extension_selection(config: Mapping[str, Any]) -> None:
    if config.get("schema_version") != EXTENDED_SCHEMA:
        raise ValueError("Unsupported FMD extended-confirmation schema.")
    selection = config["selection"]
    order = derive_field_order(
        seed=int(selection["seed"]),
        excluded_field=int(selection["excluded_prior_field"]),
    )
    opened = [int(value) for value in selection["previously_opened_fields"]]
    extension = [int(value) for value in selection["confirmation_fields"]]
    if opened != order[: len(opened)]:
        raise ValueError("Previously opened FMD fields differ from the frozen hash order.")
    if extension != order[len(opened) :]:
        raise ValueError("Extension fields are not every remaining field in frozen hash order.")
    if set(opened) & set(extension):
        raise ValueError("Previously opened and extension field sets overlap.")
    if len(extension) != int(selection["expected_confirmation_fields"]):
        raise ValueError("Extension field count differs from the frozen protocol.")
    if len(opened) + len(extension) != 19:
        raise ValueError("Frozen selection does not account for all non-excluded FMD fields.")
    for field in extension:
        observed = [
            int(value) for value in selection["realization_indices"][str(field)]
        ]
        expected = derive_realization_indices(seed=int(selection["seed"]), field=field)
        if observed != expected:
            raise ValueError(f"FOV {field} realization indices differ from the hash rule.")


def _verify_ref(project_root: Path, spec: Mapping[str, Any]) -> Path:
    path = project_root / str(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Frozen v1.4 input is missing: {path}")
    if sha256_file(path) != str(spec["file_sha256"]):
        raise ValueError(f"Frozen v1.4 file hash mismatch: {spec['path']}")
    if spec.get("content_sha256"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("content_sha256") != str(spec["content_sha256"]):
            raise ValueError(f"Frozen v1.4 content hash mismatch: {spec['path']}")
    return path


def load_extension_inputs(
    project_root: Path, config_path: Path
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Path],
]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    verify_extension_selection(config)
    refs = {
        name: _verify_ref(project_root, spec)
        for name, spec in config["frozen_v1_4"].items()
    }
    base_config, base_profile, conditional_profile, measurement = _load_locked_inputs(
        project_root,
        refs["config"],
        refs["base_profile"],
        refs["conditional_profile"],
    )
    verify_conditional_profile(conditional_profile)
    for key in (
        "archive_name",
        "archive_bytes",
        "archive_md5",
        "archive_sha256",
        "acquisition_modality",
        "sample",
        "acquisition_levels",
        "image_shape_yx_px",
    ):
        if config["source"][key] != base_config["source"][key]:
            raise ValueError(f"Extended source field {key!r} differs from v1.4.")
    prior_lock = json.loads(refs["confirmation_lock"].read_text(encoding="utf-8"))
    if prior_lock.get("content_sha256") != config["frozen_v1_4"][
        "confirmation_lock"
    ]["content_sha256"]:
        raise ValueError("V1.4 confirmation lock content mismatch.")
    prior_audit = json.loads(refs["confirmation_audit"].read_text(encoding="utf-8"))
    if prior_audit.get("status") != "pass":
        raise ValueError("The frozen v1.4 confirmation audit is not a pass.")
    return (
        config,
        base_config,
        base_profile,
        conditional_profile,
        measurement,
        refs,
    )


def verify_extension_lock(
    lock_path: Path,
    *,
    project_root: Path,
    config_path: Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != EXTENDED_LOCK_SCHEMA:
        raise ValueError("Unsupported FMD v1.5 extension-lock schema.")
    if lock.get("confirmation_status_at_lock") != "pixels_not_decoded_for_measurement_analysis":
        raise ValueError("V1.5 lock does not attest unopened extension pixels.")
    expected = str(lock.get("content_sha256", ""))
    payload = dict(lock)
    payload.pop("content_sha256", None)
    if not expected or canonical_sha256(payload) != expected:
        raise ValueError("FMD v1.5 extension-lock content hash mismatch.")
    checks = {
        "protocol_id": lock.get("protocol_id") == config["protocol_id"],
        "config_file": lock.get("config_file_sha256") == sha256_file(config_path),
        "config_content": lock.get("config_content_sha256") == canonical_sha256(config),
        "archive": lock.get("archive_sha256") == config["source"]["archive_sha256"],
        "extension_fields": [int(value) for value in lock["extension_fields"]]
        == [int(value) for value in config["selection"]["confirmation_fields"]],
    }
    if not all(checks.values()):
        raise ValueError(f"FMD v1.5 extension lock failed identity checks: {checks}")
    for artifact in lock["artifacts"]:
        path = project_root / str(artifact["path"])
        if not path.is_file() or sha256_file(path) != str(artifact["sha256"]):
            raise ValueError(f"FMD v1.5 locked artifact mismatch: {artifact['path']}")
    return lock


def build_extended_confirmation_rows(
    data_root: Path,
    config_path: Path,
    extension_lock_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    (
        config,
        _base_config,
        base_profile,
        conditional_profile,
        measurement,
        refs,
    ) = load_extension_inputs(project_root, config_path)
    extension_lock = verify_extension_lock(
        extension_lock_path,
        project_root=project_root,
        config_path=config_path,
        config=config,
    )
    adapted = _adapter_confirmation_config(config, measurement)
    records, archive_identity = index_widefield_split(
        data_root, adapted, split="confirmation"
    )
    output_directory.mkdir(parents=True, exist_ok=False)
    index_path = output_directory / "extension_pair_index.json"
    index_payload: dict[str, Any] = {
        "schema_version": "nostos-fmd-widefield-extended-pair-index/1.0",
        "adapter_version": FMD_WIDEFIELD_ADAPTER_VERSION,
        "runner_version": EXTENDED_RUNNER_VERSION,
        "protocol_id": config["protocol_id"],
        "split": "extended_confirmation",
        "archive_identity": archive_identity,
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "index_created_before_image_decode": True,
        "selected_member_payloads_read_for_checksum_only_before_index": True,
        "records": [asdict(record) for record in records],
    }
    index_payload["content_sha256"] = canonical_sha256(index_payload)
    write_json(index_path, index_payload)

    internal_config = _internal_measurement_config(measurement)
    scales = tuple(float(value) for value in measurement["measurement"]["analysis_scales_px"])
    spectral_band = shared_spectral_band_cycles_per_mm(internal_config, 1.0)
    expected_shape = config["source"]["image_shape_yx_px"]
    reference_cache: dict[
        str, tuple[np.ndarray, dict[str, Any], list[tuple[str, float, dict[str, Any]]]]
    ] = {}
    rows: list[dict[str, Any]] = []
    archive_path = data_root / str(config["source"]["archive_name"])
    started = time.perf_counter()
    with tarfile.open(archive_path, mode="r:") as opened:
        for record in records:
            if record.reference_sha256 not in reference_cache:
                reference_image = _read_grayscale_member(
                    opened,
                    record.reference_member,
                    expected_sha256=record.reference_sha256,
                    expected_shape=expected_shape,
                )
                reference_base, reference_probes = measure_selected_with_mild_probes(
                    reference_image,
                    scales_px=scales,
                    spectral_band_cycles_per_mm=spectral_band,
                )
                reference_cache[record.reference_sha256] = (
                    reference_image,
                    reference_base,
                    reference_probes,
                )
            reference_image, reference_base, reference_probes = reference_cache[
                record.reference_sha256
            ]
            input_image = _read_grayscale_member(
                opened,
                record.input_member,
                expected_sha256=record.input_sha256,
                expected_shape=expected_shape,
            )
            registration = audit_pair_registration(
                input_image,
                reference_image,
                reference_spacing_um=1.0,
                effective_input_spacing_um=1.0,
            )
            input_base, input_probes = measure_selected_with_mild_probes(
                input_image,
                scales_px=scales,
                spectral_band_cycles_per_mm=spectral_band,
            )
            pair_rows = evaluate_precomputed_pair(
                pair_id=record.pair_id,
                reference_group_id=record.reference_group_id,
                structure=record.sample,
                effective_input_spacing_um=1.0,
                registration=registration,
                input_base=input_base,
                input_probes=input_probes,
                reference_base=reference_base,
                reference_probes=reference_probes,
                config=internal_config,
                metadata={
                    "dataset": "FMD",
                    "acquisition_modality": record.acquisition_modality,
                    "sample": record.sample,
                    "field_of_view": record.field_of_view,
                    "noise_realization": record.noise_realization,
                    "acquisition_level": record.acquisition_level,
                    "averaged_captures": record.averaged_captures,
                    "input_member": record.input_member,
                    "reference_member": record.reference_member,
                    "input_sha256": record.input_sha256,
                    "reference_sha256": record.reference_sha256,
                },
            )
            converted = _convert_dimensionless_rows(
                pair_rows, config=measurement, split="extended_confirmation"
            )
            for row in converted:
                row["metadata"]["calibration_contract"] = (
                    "No pixel spacing is supplied by the FMD widefield archive; only "
                    "dimensionless endpoints are eligible."
                )
                row["metadata"]["extended_confirmation_protocol_id"] = config[
                    "protocol_id"
                ]
            rows.extend(converted)

    rows.sort(key=lambda row: str(row["case_id"]))
    elapsed = time.perf_counter() - started
    rows_path = output_directory / "extension_rows.jsonl"
    write_jsonl(rows_path, rows)
    eligible = [
        row
        for row in rows
        if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])
    ]
    eligible_by_family = Counter(str(row["endpoint_family"]) for row in eligible)
    invalid_by_family = Counter(
        str(row["endpoint_family"]) for row in eligible if bool(row["invalid"])
    )
    receipt = {
        "schema_version": "nostos-fmd-widefield-extended-evidence-build/1.0",
        "runner_version": EXTENDED_RUNNER_VERSION,
        "status": "evidence_rows_complete",
        "protocol_id": config["protocol_id"],
        "claim_boundary": config["scope"],
        "independent_groups": sorted({record.reference_group_id for record in records}),
        "independent_group_count": len({record.reference_group_id for record in records}),
        "paired_acquisitions": len(records),
        "unique_reference_images_decoded": len(reference_cache),
        "endpoint_rows": len(rows),
        "eligible_endpoint_rows": len(eligible),
        "eligible_by_family": dict(sorted(eligible_by_family.items())),
        "invalid_by_family": dict(sorted(invalid_by_family.items())),
        "elapsed_seconds": float(elapsed),
        "source": {
            "archive_identity": archive_identity,
            "config_file_sha256": sha256_file(config_path),
            "pair_index_sha256": sha256_file(index_path),
            "rows_sha256": sha256_file(rows_path),
        },
        "frozen_v1_4": {
            "base_profile_file_sha256": sha256_file(refs["base_profile"]),
            "base_profile_content_sha256": base_profile["content_sha256"],
            "conditional_profile_file_sha256": sha256_file(refs["conditional_profile"]),
            "conditional_profile_content_sha256": conditional_profile["content_sha256"],
        },
        "extension_lock": {
            "file_sha256": sha256_file(extension_lock_path),
            "content_sha256": extension_lock["content_sha256"],
        },
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    receipt_path = output_directory / "extension_evidence_receipt.json"
    write_json(receipt_path, receipt)
    return {
        "status": receipt["status"],
        "rows": str(rows_path),
        "rows_sha256": receipt["source"]["rows_sha256"],
        "pair_index": str(index_path),
        "receipt": str(receipt_path),
        "independent_groups": receipt["independent_group_count"],
        "paired_acquisitions": len(records),
        "endpoint_rows": len(rows),
        "eligible_endpoint_rows": len(eligible),
        "elapsed_seconds": elapsed,
    }


def _field_event_summary(
    scored: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    expected_groups: Sequence[str],
    confidence: float,
) -> dict[str, Any]:
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
    row_ci = clopper_pearson_interval(
        total_invalid, total_accepted, confidence=confidence
    )
    return {
        "independent_groups": len(fields),
        "fields_with_any_accepted_failure": events,
        "field_event_rate": events / len(fields),
        "field_event_exact_ci": list(field_ci),
        "accepted_emissions": total_accepted,
        "invalid_accepted_emissions": total_invalid,
        "accepted_emission_risk": total_invalid / total_accepted,
        "accepted_emission_exact_ci_descriptive": list(row_ci),
        "fields": fields,
    }


def _all_supported_cells_per_field(
    scored: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    expected_groups: Sequence[str],
    supported_keys: Sequence[str],
) -> tuple[bool, dict[str, list[str]]]:
    missing: dict[str, list[str]] = {}
    required = {str(value) for value in supported_keys}
    for group in expected_groups:
        observed = {
            str(row["conditional_cell"]["key"])
            for row in scored
            if str(row["reference_group_id"]) == str(group)
            and not bool(row["candidate_hard_abstention"])
            and float(row["calibrated_risk"]) <= float(threshold)
        }
        absent = sorted(required - observed)
        if absent:
            missing[str(group)] = absent
    return not missing, missing


def audit_extended_confirmation(
    extension_rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    base_config: Mapping[str, Any],
    base_profile: Mapping[str, Any],
    conditional_profile: Mapping[str, Any],
    prior_rows: Sequence[Mapping[str, Any]],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    verify_extension_selection(config)
    expected_extension = [
        f"{config['source']['acquisition_modality']}_{config['source']['sample']}|fov{field}"
        for field in config["selection"]["confirmation_fields"]
    ]
    expected_prior = [
        f"{config['source']['acquisition_modality']}_{config['source']['sample']}|fov{field}"
        for field in config["selection"]["prior_confirmation_fields"]
    ]
    observed_extension = sorted(
        {
            str(row["reference_group_id"])
            for row in extension_rows
            if str(row["endpoint_family"])
            == str(conditional_profile["primary_endpoint_family"])
        }
    )
    observed_prior = sorted(
        {
            str(row["reference_group_id"])
            for row in prior_rows
            if str(row["endpoint_family"])
            == str(conditional_profile["primary_endpoint_family"])
        }
    )
    if observed_extension != sorted(expected_extension):
        raise ValueError("Extension rows differ from the seven-field frozen split.")
    if observed_prior != sorted(expected_prior):
        raise ValueError("Prior confirmation rows differ from the frozen four-field split.")
    extension_audit, extension_scored = audit_conditional_support_profile(
        extension_rows,
        config=base_config,
        base_profile=base_profile,
        conditional_profile=conditional_profile,
        source_receipt=source_receipt,
    )
    cumulative_rows = [dict(row) for row in prior_rows] + [
        dict(row) for row in extension_rows
    ]
    cumulative_audit, cumulative_scored = audit_conditional_support_profile(
        cumulative_rows,
        config=base_config,
        base_profile=base_profile,
        conditional_profile=conditional_profile,
        source_receipt=source_receipt,
    )
    threshold = float(conditional_profile["base_predicted_risk_threshold"])
    confidence = float(config["uncertainty"]["confidence_level"])
    extension_field = _field_event_summary(
        extension_scored,
        threshold=threshold,
        expected_groups=expected_extension,
        confidence=confidence,
    )
    cumulative_groups = expected_prior + expected_extension
    cumulative_field = _field_event_summary(
        cumulative_scored,
        threshold=threshold,
        expected_groups=cumulative_groups,
        confidence=confidence,
    )
    cell_ok, missing_cells = _all_supported_cells_per_field(
        extension_scored,
        threshold=threshold,
        expected_groups=expected_extension,
        supported_keys=[cell["key"] for cell in conditional_profile["supported_cells"]],
    )
    extension_gates = config["extension_gates"]
    cumulative_gates = config["cumulative_gates"]
    checks = {
        "extension_inherited_v1_4_audit_pass": (
            not bool(extension_gates["require_inherited_v1_4_audit_pass"])
            or extension_audit["status"] == "pass"
        ),
        "extension_required_independent_groups": extension_field["independent_groups"]
        == int(extension_gates["required_independent_groups"]),
        "extension_zero_invalid_accepted_emissions": (
            not bool(extension_gates["require_zero_invalid_accepted_emissions"])
            or extension_field["invalid_accepted_emissions"] == 0
        ),
        "extension_zero_fields_with_any_accepted_failure": (
            not bool(extension_gates["require_zero_fields_with_any_accepted_failure"])
            or extension_field["fields_with_any_accepted_failure"] == 0
        ),
        "extension_all_supported_cells_in_every_field": (
            not bool(extension_gates["require_all_supported_cells_in_every_field"])
            or cell_ok
        ),
        "cumulative_inherited_v1_4_audit_pass": (
            not bool(cumulative_gates["require_inherited_v1_4_audit_pass"])
            or cumulative_audit["status"] == "pass"
        ),
        "cumulative_required_independent_groups": cumulative_field[
            "independent_groups"
        ]
        == int(cumulative_gates["required_independent_groups"]),
        "cumulative_zero_invalid_accepted_emissions": (
            not bool(cumulative_gates["require_zero_invalid_accepted_emissions"])
            or cumulative_field["invalid_accepted_emissions"] == 0
        ),
        "cumulative_zero_fields_with_any_accepted_failure": (
            not bool(cumulative_gates["require_zero_fields_with_any_accepted_failure"])
            or cumulative_field["fields_with_any_accepted_failure"] == 0
        ),
        "cumulative_exact_field_failure_upper95": float(
            cumulative_field["field_event_exact_ci"][1]
        )
        <= float(cumulative_gates["maximum_two_sided_exact_field_failure_upper95"]),
    }
    audit = {
        "schema_version": "nostos-fmd-widefield-extended-confirmation-audit/1.0",
        "auditor_version": EXTENDED_AUDITOR_VERSION,
        "status": "pass" if all(checks.values()) else "fail",
        "protocol_id": config["protocol_id"],
        "claim_boundary": config["scope"],
        "frozen_profile": {
            "base_profile_content_sha256": base_profile["content_sha256"],
            "conditional_profile_content_sha256": conditional_profile["content_sha256"],
            "predicted_risk_threshold": threshold,
            "supported_cells": [
                {"key": cell["key"], "values": cell["values"]}
                for cell in conditional_profile["supported_cells"]
            ],
        },
        "extension": {
            "field_event_summary": extension_field,
            "inherited_v1_4_audit": extension_audit,
            "missing_supported_cells_by_field": missing_cells,
        },
        "cumulative": {
            "field_event_summary": cumulative_field,
            "inherited_v1_4_audit": cumulative_audit,
        },
        "checks": checks,
        "source_receipt": dict(source_receipt or {}),
    }
    audit["content_sha256"] = canonical_sha256(audit)
    return audit, extension_scored, cumulative_scored


def run_extended_audit(
    extension_rows_path: Path,
    config_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    (
        config,
        base_config,
        base_profile,
        conditional_profile,
        _measurement,
        refs,
    ) = load_extension_inputs(project_root, config_path)
    if output_directory.exists():
        raise FileExistsError(
            f"Refusing to overwrite v1.5 extension audit: {output_directory}"
        )
    extension_rows = read_jsonl(extension_rows_path)
    prior_rows = read_jsonl(refs["confirmation_rows"])
    audit, extension_scored, cumulative_scored = audit_extended_confirmation(
        extension_rows,
        config=config,
        base_config=base_config,
        base_profile=base_profile,
        conditional_profile=conditional_profile,
        prior_rows=prior_rows,
        source_receipt={
            "extension_rows": {
                "path": extension_rows_path.name,
                "bytes": extension_rows_path.stat().st_size,
                "sha256": sha256_file(extension_rows_path),
            },
            "prior_confirmation_rows": {
                "path": refs["confirmation_rows"].relative_to(project_root).as_posix(),
                "bytes": refs["confirmation_rows"].stat().st_size,
                "sha256": sha256_file(refs["confirmation_rows"]),
            },
        },
    )
    output_directory.mkdir(parents=True)
    audit_path = output_directory / "extended_confirmation_audit.json"
    extension_scored_path = output_directory / "extension_scored.jsonl"
    cumulative_scored_path = output_directory / "cumulative_scored.jsonl"
    write_json(audit_path, audit)
    write_jsonl(extension_scored_path, extension_scored)
    write_jsonl(cumulative_scored_path, cumulative_scored)
    return {
        "status": audit["status"],
        "audit": str(audit_path),
        "audit_sha256": sha256_file(audit_path),
        "extension_scored": str(extension_scored_path),
        "cumulative_scored": str(cumulative_scored_path),
        "checks": audit["checks"],
        "extension_field_event_summary": audit["extension"]["field_event_summary"],
        "cumulative_field_event_summary": audit["cumulative"]["field_event_summary"],
    }
