"""No-refit external transfer for the conservative FMD strict profile."""

from __future__ import annotations

import hashlib
import json
import tarfile
import time
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from nostos.validation.conditional_support_profile import (
    audit_conditional_support_profile,
    verify_conditional_profile,
)
from nostos.validation.fmd_validity_profile import (
    _convert_dimensionless_rows,
    _internal_measurement_config,
    measure_selected_with_mild_probes,
)
from nostos.validation.fmd_widefield_extended_confirmation import (
    _all_supported_cells_per_field,
    _field_event_summary,
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
    verify_profile,
    write_json,
    write_jsonl,
)


TRANSFER_SCHEMA = "nostos-fmd-strict-external-transfer/1.0"
TRANSFER_LOCK_SCHEMA = "nostos-fmd-strict-external-transfer-lock/1.0"
TRANSFER_RUNNER_VERSION = "nostos-fmd-strict-external-transfer-runner/1.0"
TRANSFER_AUDITOR_VERSION = "nostos-fmd-strict-external-transfer-auditor/1.0"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def derive_transfer_field_order(*, seed: int, dataset_key: str) -> list[int]:
    return sorted(
        range(1, 21),
        key=lambda field: _hash_text(f"{int(seed)}|{dataset_key}|fov{field}"),
    )


def derive_transfer_realizations(
    *, seed: int, dataset_key: str, field: int
) -> list[int]:
    ranked = sorted(
        range(50),
        key=lambda index: _hash_text(
            f"{int(seed)}|{dataset_key}|fov{int(field)}|realization{index}"
        ),
    )
    return sorted(ranked[:4])


def verify_transfer_selection(config: Mapping[str, Any]) -> None:
    if config.get("schema_version") != TRANSFER_SCHEMA:
        raise ValueError("Unsupported FMD strict external-transfer schema.")
    selection = config["selection"]
    seed = int(selection["seed"])
    expected_fields = int(selection["fields_per_source"])
    if len(config["sources"]) != int(selection["expected_source_count"]):
        raise ValueError("External-transfer source count differs from the lock.")
    keys: set[str] = set()
    for item in config["sources"]:
        key = str(item["dataset_key"])
        if key in keys:
            raise ValueError(f"Duplicate external-transfer dataset key: {key}")
        keys.add(key)
        fields = [int(value) for value in item["confirmation_fields"]]
        expected = derive_transfer_field_order(seed=seed, dataset_key=key)[:expected_fields]
        if fields != expected:
            raise ValueError(f"External-transfer fields differ from the hash rule: {key}")
        for field in fields:
            observed = [
                int(value) for value in item["realization_indices"][str(field)]
            ]
            expected_realizations = derive_transfer_realizations(
                seed=seed, dataset_key=key, field=field
            )
            if observed != expected_realizations:
                raise ValueError(
                    f"External-transfer realizations differ from the hash rule: {key} FOV {field}"
                )


def _verify_file(project_root: Path, spec: Mapping[str, Any]) -> Path:
    path = project_root / str(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Frozen transfer input is missing: {path}")
    if sha256_file(path) != str(spec["file_sha256"]):
        raise ValueError(f"Frozen transfer input hash mismatch: {spec['path']}")
    if spec.get("content_sha256"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("content_sha256") != str(spec["content_sha256"]):
            raise ValueError(f"Frozen transfer content mismatch: {spec['path']}")
    return path


def load_transfer_inputs(
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
    verify_transfer_selection(config)
    refs = {
        name: _verify_file(project_root, spec)
        for name, spec in config["frozen_profile"].items()
    }
    development_config = json.loads(refs["development_config"].read_text(encoding="utf-8"))
    base_profile = json.loads(refs["base_profile"].read_text(encoding="utf-8"))
    strict_profile = json.loads(refs["strict_profile"].read_text(encoding="utf-8"))
    measurement = json.loads(refs["measurement_protocol"].read_text(encoding="utf-8"))
    verify_profile(base_profile)
    verify_conditional_profile(strict_profile)
    if strict_profile["config_sha256"] != canonical_sha256(development_config):
        raise ValueError("Strict profile was compiled from a different development config.")
    if strict_profile["base_profile_content_sha256"] != base_profile["content_sha256"]:
        raise ValueError("Strict profile and base profile are incompatible.")
    supported = [cell["values"] for cell in strict_profile["supported_cells"]]
    if supported != [["avg16", 16.0], ["avg16", 4.0], ["avg16", 8.0]]:
        raise ValueError("External transfer requires the frozen three-cell strict profile.")
    return config, development_config, base_profile, strict_profile, measurement, refs


def verify_transfer_lock(
    lock_path: Path,
    *,
    project_root: Path,
    config_path: Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != TRANSFER_LOCK_SCHEMA:
        raise ValueError("Unsupported FMD strict external-transfer lock schema.")
    if lock.get("confirmation_status_at_lock") != "pixels_not_decoded_for_measurement_analysis":
        raise ValueError("External-transfer lock does not attest unopened pixels.")
    expected = str(lock.get("content_sha256", ""))
    payload = dict(lock)
    payload.pop("content_sha256", None)
    if not expected or canonical_sha256(payload) != expected:
        raise ValueError("External-transfer lock content hash mismatch.")
    checks = {
        "protocol_id": lock.get("protocol_id") == config["protocol_id"],
        "config_file": lock.get("config_file_sha256") == sha256_file(config_path),
        "config_content": lock.get("config_content_sha256") == canonical_sha256(config),
        "sources": [source["dataset_key"] for source in lock["sources"]]
        == [source["dataset_key"] for source in config["sources"]],
    }
    if not all(checks.values()):
        raise ValueError(f"External-transfer lock identity checks failed: {checks}")
    for artifact in lock["artifacts"]:
        path = project_root / str(artifact["path"])
        if not path.is_file() or sha256_file(path) != str(artifact["sha256"]):
            raise ValueError(f"External-transfer locked artifact mismatch: {artifact['path']}")
    return lock


def _adapter_config(
    protocol: Mapping[str, Any], measurement: Mapping[str, Any], source: Mapping[str, Any]
) -> dict[str, Any]:
    adapted = deepcopy(dict(measurement))
    adapted["protocol_id"] = str(protocol["protocol_id"])
    adapted["scope"] = deepcopy(protocol["scope"])
    adapted["source"] = deepcopy(source["source"])
    adapted["selection"]["development_fields"] = []
    adapted["selection"]["confirmation_fields"] = [
        int(value) for value in source["confirmation_fields"]
    ]
    adapted["selection"]["realization_indices"] = deepcopy(
        source["realization_indices"]
    )
    adapted["selection"]["expected_fields_per_split"] = len(
        source["confirmation_fields"]
    )
    adapted["selection"]["expected_realizations_per_field_level"] = int(
        protocol["selection"]["realizations_per_field_level"]
    )
    adapted["selection"]["expected_pairs_per_split"] = int(
        protocol["selection"]["pairs_per_source"]
    )
    return adapted


def _measure_source(
    *,
    data_root: Path,
    protocol: Mapping[str, Any],
    measurement: Mapping[str, Any],
    source: Mapping[str, Any],
    records: Sequence[Any],
) -> tuple[list[dict[str, Any]], int]:
    internal_config = _internal_measurement_config(measurement)
    scales = tuple(float(value) for value in measurement["measurement"]["analysis_scales_px"])
    spectral_band = shared_spectral_band_cycles_per_mm(internal_config, 1.0)
    expected_shape = source["source"]["image_shape_yx_px"]
    reference_cache: dict[
        str, tuple[np.ndarray, dict[str, Any], list[tuple[str, float, dict[str, Any]]]]
    ] = {}
    rows: list[dict[str, Any]] = []
    archive_path = data_root / str(source["source"]["archive_name"])
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
                    "transfer_source_key": source["dataset_key"],
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
                pair_rows, config=measurement, split="external_transfer_confirmation"
            )
            for row in converted:
                row["metadata"]["calibration_contract"] = (
                    "No pixel spacing is supplied by the FMD archive; only dimensionless "
                    "endpoints are eligible."
                )
                row["metadata"]["external_transfer_protocol_id"] = protocol[
                    "protocol_id"
                ]
            rows.extend(converted)
    return rows, len(reference_cache)


def build_transfer_rows(
    data_root: Path,
    config_path: Path,
    transfer_lock_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    config, _development, base, strict, measurement, _refs = load_transfer_inputs(
        project_root, config_path
    )
    lock = verify_transfer_lock(
        transfer_lock_path,
        project_root=project_root,
        config_path=config_path,
        config=config,
    )
    output_directory.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    all_rows: list[dict[str, Any]] = []
    index_sources = []
    source_jobs: list[tuple[Mapping[str, Any], list[Any], dict[str, Any]]] = []
    for source in config["sources"]:
        adapted = _adapter_config(config, measurement, source)
        records, archive_identity = index_widefield_split(
            data_root, adapted, split="confirmation"
        )
        index_sources.append(
            {
                "dataset_key": source["dataset_key"],
                "archive_identity": archive_identity,
                "records": [asdict(record) for record in records],
            }
        )
        source_jobs.append((source, records, archive_identity))
    index_payload = {
        "schema_version": "nostos-fmd-strict-external-transfer-index/1.0",
        "adapter_version": FMD_WIDEFIELD_ADAPTER_VERSION,
        "runner_version": TRANSFER_RUNNER_VERSION,
        "protocol_id": config["protocol_id"],
        "index_created_before_image_decode": True,
        "selected_member_payloads_read_for_checksum_only_before_index": True,
        "sources": index_sources,
    }
    index_payload["content_sha256"] = canonical_sha256(index_payload)
    index_path = output_directory / "external_transfer_pair_index.json"
    write_json(index_path, index_payload)

    receipt_sources = []
    for source, records, archive_identity in source_jobs:
        rows, reference_count = _measure_source(
            data_root=data_root,
            protocol=config,
            measurement=measurement,
            source=source,
            records=records,
        )
        all_rows.extend(rows)
        receipt_sources.append(
            {
                "dataset_key": source["dataset_key"],
                "independent_groups": sorted(
                    {record.reference_group_id for record in records}
                ),
                "paired_acquisitions": len(records),
                "unique_reference_images_decoded": reference_count,
                "archive_identity": archive_identity,
            }
        )
    all_rows.sort(key=lambda row: str(row["case_id"]))
    rows_path = output_directory / "external_transfer_rows.jsonl"
    write_jsonl(rows_path, all_rows)
    eligible = [
        row
        for row in all_rows
        if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])
    ]
    receipt = {
        "schema_version": "nostos-fmd-strict-external-transfer-evidence/1.0",
        "runner_version": TRANSFER_RUNNER_VERSION,
        "status": "evidence_rows_complete",
        "protocol_id": config["protocol_id"],
        "claim_boundary": config["scope"],
        "sources": receipt_sources,
        "independent_group_count": len(
            {str(row["reference_group_id"]) for row in eligible}
        ),
        "paired_acquisitions": sum(item["paired_acquisitions"] for item in receipt_sources),
        "endpoint_rows": len(all_rows),
        "eligible_endpoint_rows": len(eligible),
        "eligible_by_family": dict(
            sorted(Counter(str(row["endpoint_family"]) for row in eligible).items())
        ),
        "invalid_by_family": dict(
            sorted(
                Counter(
                    str(row["endpoint_family"])
                    for row in eligible
                    if bool(row["invalid"])
                ).items()
            )
        ),
        "elapsed_seconds": float(time.perf_counter() - started),
        "source": {
            "config_file_sha256": sha256_file(config_path),
            "pair_index_sha256": sha256_file(index_path),
            "rows_sha256": sha256_file(rows_path),
        },
        "frozen_profile": {
            "base_profile_content_sha256": base["content_sha256"],
            "strict_profile_content_sha256": strict["content_sha256"],
        },
        "transfer_lock": {
            "file_sha256": sha256_file(transfer_lock_path),
            "content_sha256": lock["content_sha256"],
        },
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    receipt_path = output_directory / "external_transfer_evidence_receipt.json"
    write_json(receipt_path, receipt)
    return {
        "status": receipt["status"],
        "rows": str(rows_path),
        "rows_sha256": receipt["source"]["rows_sha256"],
        "pair_index": str(index_path),
        "receipt": str(receipt_path),
        "independent_groups": receipt["independent_group_count"],
        "paired_acquisitions": receipt["paired_acquisitions"],
        "endpoint_rows": len(all_rows),
        "eligible_endpoint_rows": len(eligible),
        "elapsed_seconds": receipt["elapsed_seconds"],
    }


def audit_transfer_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    development_config: Mapping[str, Any],
    base_profile: Mapping[str, Any],
    strict_profile: Mapping[str, Any],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verify_transfer_selection(config)
    threshold = float(strict_profile["base_predicted_risk_threshold"])
    confidence = float(config["uncertainty"]["confidence_level"])
    supported_keys = [cell["key"] for cell in strict_profile["supported_cells"]]
    per_source = []
    all_scored: list[dict[str, Any]] = []
    checks: dict[str, bool] = {}
    all_expected_groups: list[str] = []
    for source in config["sources"]:
        key = str(source["dataset_key"])
        subset = [row for row in rows if row["metadata"]["transfer_source_key"] == key]
        audit, scored = audit_conditional_support_profile(
            subset,
            config=development_config,
            base_profile=base_profile,
            conditional_profile=strict_profile,
            source_receipt=source_receipt,
        )
        all_scored.extend(scored)
        expected_groups = [
            f"{source['source']['acquisition_modality']}_{source['source']['sample']}|fov{field}"
            for field in source["confirmation_fields"]
        ]
        all_expected_groups.extend(expected_groups)
        field = _field_event_summary(
            scored,
            threshold=threshold,
            expected_groups=expected_groups,
            confidence=confidence,
        )
        cells_ok, missing = _all_supported_cells_per_field(
            scored,
            threshold=threshold,
            expected_groups=expected_groups,
            supported_keys=supported_keys,
        )
        gate = config["source_gates"]
        source_checks = {
            "inherited_profile_audit_pass": audit["status"] == "pass",
            "required_independent_groups": field["independent_groups"]
            == int(gate["required_independent_groups"]),
            "zero_invalid_accepted_emissions": (
                not bool(gate["require_zero_invalid_accepted_emissions"])
                or field["invalid_accepted_emissions"] == 0
            ),
            "zero_fields_with_any_accepted_failure": (
                not bool(gate["require_zero_fields_with_any_accepted_failure"])
                or field["fields_with_any_accepted_failure"] == 0
            ),
            "all_supported_cells_in_every_field": (
                not bool(gate["require_all_supported_cells_in_every_field"])
                or cells_ok
            ),
        }
        for name, value in source_checks.items():
            checks[f"{key}:{name}"] = bool(value)
        per_source.append(
            {
                "dataset_key": key,
                "field_event_summary": field,
                "inherited_profile_audit": audit,
                "missing_supported_cells_by_field": missing,
                "checks": source_checks,
                "passes": bool(all(source_checks.values())),
            }
        )

    combined_audit, combined_scored = audit_conditional_support_profile(
        rows,
        config=development_config,
        base_profile=base_profile,
        conditional_profile=strict_profile,
        source_receipt=source_receipt,
    )
    combined_field = _field_event_summary(
        combined_scored,
        threshold=threshold,
        expected_groups=all_expected_groups,
        confidence=confidence,
    )
    combined_gate = config["combined_gates"]
    combined_checks = {
        "inherited_profile_audit_pass": combined_audit["status"] == "pass",
        "required_independent_groups": combined_field["independent_groups"]
        == int(combined_gate["required_independent_groups"]),
        "zero_invalid_accepted_emissions": (
            not bool(combined_gate["require_zero_invalid_accepted_emissions"])
            or combined_field["invalid_accepted_emissions"] == 0
        ),
        "zero_fields_with_any_accepted_failure": (
            not bool(combined_gate["require_zero_fields_with_any_accepted_failure"])
            or combined_field["fields_with_any_accepted_failure"] == 0
        ),
        "maximum_two_sided_exact_field_failure_upper95": float(
            combined_field["field_event_exact_ci"][1]
        )
        <= float(combined_gate["maximum_two_sided_exact_field_failure_upper95"]),
    }
    for name, value in combined_checks.items():
        checks[f"combined:{name}"] = bool(value)
    audit = {
        "schema_version": "nostos-fmd-strict-external-transfer-audit/1.0",
        "auditor_version": TRANSFER_AUDITOR_VERSION,
        "status": "pass" if all(checks.values()) else "fail",
        "protocol_id": config["protocol_id"],
        "claim_boundary": config["scope"],
        "frozen_profile": {
            "base_profile_content_sha256": base_profile["content_sha256"],
            "strict_profile_content_sha256": strict_profile["content_sha256"],
            "predicted_risk_threshold": threshold,
            "supported_cells": [
                {"key": cell["key"], "values": cell["values"]}
                for cell in strict_profile["supported_cells"]
            ],
        },
        "per_source": per_source,
        "combined": {
            "field_event_summary": combined_field,
            "inherited_profile_audit": combined_audit,
            "checks": combined_checks,
            "passes": bool(all(combined_checks.values())),
        },
        "checks": checks,
        "source_receipt": dict(source_receipt or {}),
    }
    audit["content_sha256"] = canonical_sha256(audit)
    return audit, combined_scored


def run_transfer_audit(
    rows_path: Path, config_path: Path, output_directory: Path
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    config, development, base, strict, _measurement, _refs = load_transfer_inputs(
        project_root, config_path
    )
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite transfer audit: {output_directory}")
    rows = read_jsonl(rows_path)
    audit, scored = audit_transfer_rows(
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
