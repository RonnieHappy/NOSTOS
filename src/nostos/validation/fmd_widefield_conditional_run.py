"""One-shot FMD widefield confirmation runner for conditional support v1.4."""

from __future__ import annotations

import json
import tarfile
import time
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from nostos.validation.conditional_support_profile import (
    verify_conditional_profile,
)
from nostos.validation.fmd_validity_profile import (
    _convert_dimensionless_rows,
    _internal_measurement_config,
    measure_selected_with_mild_probes,
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
    sha256_file,
    verify_profile,
    write_json,
    write_jsonl,
)


CONDITIONAL_RUNNER_VERSION = "nostos-fmd-widefield-conditional-runner/1.0"


def _load_locked_inputs(
    project_root: Path,
    config_path: Path,
    base_profile_path: Path,
    conditional_profile_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "nostos-fmd-widefield-conditional-support/1.0":
        raise ValueError("Unsupported FMD conditional-support protocol schema.")
    base_profile = json.loads(base_profile_path.read_text(encoding="utf-8"))
    conditional_profile = json.loads(
        conditional_profile_path.read_text(encoding="utf-8")
    )
    verify_profile(base_profile)
    verify_conditional_profile(conditional_profile)
    if sha256_file(base_profile_path) != config["base_profile"]["file_sha256"]:
        raise ValueError("Base-profile file hash differs from the v1.4 lock.")
    if base_profile["content_sha256"] != config["base_profile"]["content_sha256"]:
        raise ValueError("Base-profile content hash differs from the v1.4 lock.")
    if conditional_profile["config_sha256"] != canonical_sha256(config):
        raise ValueError("Conditional profile was compiled from a different v1.4 lock.")
    if conditional_profile["base_profile_content_sha256"] != base_profile["content_sha256"]:
        raise ValueError("Conditional profile and base profile are incompatible.")

    measurement_path = project_root / str(config["base_measurement_protocol"]["path"])
    if sha256_file(measurement_path) != config["base_measurement_protocol"]["file_sha256"]:
        raise ValueError("Base measurement-protocol file hash mismatch.")
    measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
    if canonical_sha256(measurement) != config["base_measurement_protocol"][
        "content_sha256"
    ]:
        raise ValueError("Base measurement-protocol content hash mismatch.")
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
        if measurement["source"][key] != config["source"][key]:
            raise ValueError(f"V1.4 source field {key!r} differs from the base measurement lock.")
    return config, base_profile, conditional_profile, measurement


def _adapter_confirmation_config(
    config: Mapping[str, Any], measurement: Mapping[str, Any]
) -> dict[str, Any]:
    adapted = deepcopy(dict(measurement))
    adapted["protocol_id"] = str(config["protocol_id"])
    adapted["scope"] = deepcopy(config["scope"])
    adapted["source"] = deepcopy(config["source"])
    adapted["selection"]["development_fields"] = list(
        config["selection"]["development_fields"]
    )
    adapted["selection"]["confirmation_fields"] = list(
        config["selection"]["confirmation_fields"]
    )
    adapted["selection"]["realization_indices"] = deepcopy(
        config["selection"]["realization_indices"]
    )
    adapted["selection"]["expected_fields_per_split"] = int(
        config["selection"]["expected_confirmation_fields"]
    )
    adapted["selection"]["expected_realizations_per_field_level"] = int(
        config["selection"]["expected_realizations_per_field_level"]
    )
    adapted["selection"]["expected_pairs_per_split"] = int(
        config["selection"]["expected_confirmation_pairs"]
    )
    return adapted


def _verify_confirmation_lock(
    lock_path: Path,
    *,
    project_root: Path,
    config: Mapping[str, Any],
    base_profile_path: Path,
    base_profile: Mapping[str, Any],
    conditional_profile_path: Path,
    conditional_profile: Mapping[str, Any],
) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "nostos-fmd-widefield-conditional-confirmation-lock/1.0":
        raise ValueError("Unsupported FMD v1.4 confirmation-lock schema.")
    if lock.get("confirmation_status_at_lock") != "pixels_not_decoded_for_measurement_analysis":
        raise ValueError("V1.4 lock does not attest unopened confirmation pixels.")
    expected = str(lock.get("content_sha256", ""))
    payload = dict(lock)
    payload.pop("content_sha256", None)
    if not expected or canonical_sha256(payload) != expected:
        raise ValueError("FMD v1.4 confirmation-lock content hash mismatch.")
    checks = {
        "protocol_id": lock.get("protocol_id") == config["protocol_id"],
        "config_content": lock.get("config_content_sha256") == canonical_sha256(config),
        "base_profile_file": lock.get("base_profile_file_sha256")
        == sha256_file(base_profile_path),
        "base_profile_content": lock.get("base_profile_content_sha256")
        == base_profile["content_sha256"],
        "conditional_profile_file": lock.get("conditional_profile_file_sha256")
        == sha256_file(conditional_profile_path),
        "conditional_profile_content": lock.get("conditional_profile_content_sha256")
        == conditional_profile["content_sha256"],
        "archive": lock.get("archive_sha256") == config["source"]["archive_sha256"],
        "confirmation_fields": [int(value) for value in lock["confirmation_fields"]]
        == [int(value) for value in config["selection"]["confirmation_fields"]],
    }
    if not all(checks.values()):
        raise ValueError(f"FMD v1.4 confirmation lock failed identity checks: {checks}")
    for artifact in lock["artifacts"]:
        path = project_root / str(artifact["path"])
        if not path.is_file() or sha256_file(path) != str(artifact["sha256"]):
            raise ValueError(f"FMD v1.4 locked artifact mismatch: {artifact['path']}")
    return lock


def build_conditional_confirmation_rows(
    data_root: Path,
    config_path: Path,
    base_profile_path: Path,
    conditional_profile_path: Path,
    confirmation_lock_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    config, base_profile, conditional_profile, measurement = _load_locked_inputs(
        project_root,
        config_path,
        base_profile_path,
        conditional_profile_path,
    )
    confirmation_lock = _verify_confirmation_lock(
        confirmation_lock_path,
        project_root=project_root,
        config=config,
        base_profile_path=base_profile_path,
        base_profile=base_profile,
        conditional_profile_path=conditional_profile_path,
        conditional_profile=conditional_profile,
    )
    adapted = _adapter_confirmation_config(config, measurement)
    records, archive_identity = index_widefield_split(
        data_root, adapted, split="confirmation"
    )
    output_directory.mkdir(parents=True, exist_ok=False)
    index_path = output_directory / "confirmation_pair_index.json"
    index_payload: dict[str, Any] = {
        "schema_version": "nostos-fmd-widefield-conditional-pair-index/1.0",
        "adapter_version": FMD_WIDEFIELD_ADAPTER_VERSION,
        "runner_version": CONDITIONAL_RUNNER_VERSION,
        "protocol_id": config["protocol_id"],
        "split": "confirmation",
        "archive_identity": archive_identity,
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "base_measurement_protocol_content_sha256": canonical_sha256(measurement),
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
                pair_rows, config=measurement, split="confirmation"
            )
            for row in converted:
                row["metadata"]["calibration_contract"] = (
                    "No pixel spacing is supplied by the FMD widefield archive; only "
                    "dimensionless endpoints are eligible."
                )
                row["metadata"]["conditional_support_protocol_id"] = config[
                    "protocol_id"
                ]
            rows.extend(converted)

    rows.sort(key=lambda row: str(row["case_id"]))
    elapsed = time.perf_counter() - started
    rows_path = output_directory / "confirmation_rows.jsonl"
    write_jsonl(rows_path, rows)
    eligible = [row for row in rows if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])]
    eligible_by_family = Counter(str(row["endpoint_family"]) for row in eligible)
    invalid_by_family = Counter(
        str(row["endpoint_family"]) for row in eligible if bool(row["invalid"])
    )
    receipt = {
        "schema_version": "nostos-fmd-widefield-conditional-evidence-build/1.0",
        "runner_version": CONDITIONAL_RUNNER_VERSION,
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
        "base_profile": {
            "file_sha256": sha256_file(base_profile_path),
            "content_sha256": base_profile["content_sha256"],
        },
        "conditional_profile": {
            "file_sha256": sha256_file(conditional_profile_path),
            "content_sha256": conditional_profile["content_sha256"],
        },
        "confirmation_lock": {
            "file_sha256": sha256_file(confirmation_lock_path),
            "content_sha256": confirmation_lock["content_sha256"],
        },
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    receipt_path = output_directory / "confirmation_evidence_receipt.json"
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
