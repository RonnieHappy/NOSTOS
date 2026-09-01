"""Execute one prospective BioSR development or confirmation archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    PROTOCOL_VERSION,
    audit_pair_registration,
    aurc,
    development_partition,
    eligible_rows,
    evaluate_precomputed_pair,
    index_biosr_archive,
    image_sha256,
    measure_with_mild_probes,
    read_mrc_bytes,
    shared_spectral_band_cycles_per_mm,
    sha256_file,
    write_rows_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_FILES = (
    Path(__file__).resolve(),
    PROJECT_ROOT / "src" / "nostos" / "validation" / "paired_acquisition_support.py",
    PROJECT_ROOT / "src" / "nostos" / "features" / "spatial_fft.py",
    PROJECT_ROOT / "src" / "nostos" / "features" / "response_modules.py",
    PROJECT_ROOT / "src" / "nostos" / "core" / "qc.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "metrics.py",
    PROJECT_ROOT / "pyproject.toml",
    PROJECT_ROOT / "uv.lock",
)
LOCK_RECEIPT = PROJECT_ROOT / "manifests" / "paired_acquisition_support_v1_protocol_lock.json"
AMENDMENT_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_preprocessing_amendment_lock.json"
ER_LAYOUT_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_er_layout_amendment_lock.json"
CALIBRATION_CORRECTION_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_calibration_correction_lock.json"
SUPPORT_SCORE_CODE_AUDIT_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_code_audit_corrections_lock.json"
PILOT_REPAIR_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_pilot_repair_v5_lock.json"
PROFILE_LINEAGE_AMENDMENT_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_profile_lineage_amendment_lock.json"
SCORE_FORMULA_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_score_formula_lock_v2.json"
THRESHOLD_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_threshold_lock.json"


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_lock(receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    items = receipt.get("files") or [receipt["file"]]
    failures = []
    for item in items:
        path = PROJECT_ROOT / item["path"]
        observed = sha256_file(path) if path.is_file() else None
        if observed != item["sha256"] or (path.is_file() and path.stat().st_size != item["bytes"]):
            failures.append({"path": item["path"], "expected": item, "observed_sha256": observed})
    if failures:
        raise RuntimeError(f"Prospective protocol lock failed: {failures}")
    return receipt


def _verify_pilot_repair_lineage() -> tuple[dict[str, Any], dict[str, Any]]:
    """Preserve the historical pilot lock while verifying its audited profile amendment."""

    historical = json.loads(PILOT_REPAIR_LOCK.read_text(encoding="utf-8"))
    amendment = _verify_lock(PROFILE_LINEAGE_AMENDMENT_LOCK)
    if amendment.get("historical_pilot_repair_lock_sha256") != sha256_file(PILOT_REPAIR_LOCK):
        raise RuntimeError("Profile-lineage amendment does not identify the historical pilot lock.")
    historical_profile = next(
        item
        for item in historical["files"]
        if item["path"] == "configs/biosr_widefield_measurement_profile_v1.locked.json"
    )
    historical_runner = next(
        item
        for item in historical["files"]
        if item["path"] == "scripts/run_biosr_paired_support.py"
    )
    if amendment.get("historical_profile") != historical_profile:
        raise RuntimeError("Profile-lineage amendment does not preserve the historical profile receipt.")
    if amendment.get("historical_runner") != historical_runner:
        raise RuntimeError("Profile-lineage amendment does not preserve the historical runner receipt.")
    amended_paths = {historical_profile["path"], historical_runner["path"]}
    failures = []
    for item in historical["files"]:
        if item["path"] in amended_paths:
            continue
        path = PROJECT_ROOT / item["path"]
        observed = sha256_file(path) if path.is_file() else None
        if observed != item["sha256"] or (path.is_file() and path.stat().st_size != item["bytes"]):
            failures.append({"path": item["path"], "expected": item, "observed_sha256": observed})
    if failures:
        raise RuntimeError(f"Historical pilot-repair lineage failed: {failures}")
    current_profile = amendment["current_profile"]
    profile_path = PROJECT_ROOT / current_profile["path"]
    if (
        not profile_path.is_file()
        or profile_path.stat().st_size != current_profile["bytes"]
        or sha256_file(profile_path) != current_profile["sha256"]
    ):
        raise RuntimeError("Audited current acquisition profile does not match its lineage amendment.")
    return historical, amendment


def _implementation_receipt() -> dict[str, Any]:
    files = [
        {
            "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in IMPLEMENTATION_FILES
    ]
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "files": files}


def _read_checkpoint(
    path: Path,
    *,
    archive_sha256: str,
    config_sha256: str,
    implementation_sha256: str,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("archive_sha256") != archive_sha256
        or payload.get("config_sha256") != config_sha256
        or payload.get("implementation_sha256") != implementation_sha256
    ):
        return None
    return payload


def _process_cell(
    archive: str,
    records_payload: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    records = [BioSRPairRecord(**item) for item in records_payload]
    first = records[0]
    scales = tuple(float(value) for value in config["physical_scales_um"])
    spectral_band = shared_spectral_band_cycles_per_mm(config, first.effective_input_spacing_um)
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as opened:
        reference_payload = opened.read(first.reference_member)
        reference_image = read_mrc_bytes(reference_payload)
        reference_sha = image_sha256(reference_image)
        reference_base, reference_probes = measure_with_mild_probes(
            reference_image,
            grid_spacing_um=first.reference_spacing_um,
            effective_spacing_um=first.reference_spacing_um,
            scales_um=scales,
            spectral_band_cycles_per_mm=spectral_band,
        )
        for record in records:
            raw_payload = opened.read(record.input_member)
            raw = read_mrc_bytes(raw_payload)
            if raw.shape != (record.input_frames, *record.input_shape_yx):
                raise ValueError(f"Unexpected raw shape {raw.shape} for {record.pair_id}.")
            input_image = np.mean(raw.astype(np.float64), axis=0)
            registration = audit_pair_registration(
                input_image,
                reference_image,
                reference_spacing_um=record.reference_spacing_um,
                effective_input_spacing_um=record.effective_input_spacing_um,
            )
            input_base, input_probes = measure_with_mild_probes(
                input_image,
                grid_spacing_um=record.input_grid_spacing_um,
                effective_spacing_um=record.effective_input_spacing_um,
                scales_um=scales,
                spectral_band_cycles_per_mm=spectral_band,
            )
            metadata = {
                "cell_id": record.cell_id,
                "signal_level_ordinal": record.signal_level,
                "input_member": record.input_member,
                "reference_member": record.reference_member,
                "raw_stack_sha256": hashlib.sha256(raw_payload).hexdigest(),
                "input_mean_pixel_sha256": image_sha256(input_image),
                "reference_mrc_sha256": hashlib.sha256(reference_payload).hexdigest(),
                "reference_pixel_sha256": reference_sha,
                "input_construction": "float64 arithmetic mean of nine raw SIM frames",
            }
            rows.extend(
                evaluate_precomputed_pair(
                    pair_id=record.pair_id,
                    reference_group_id=record.reference_group_id,
                    structure=record.structure,
                    effective_input_spacing_um=record.effective_input_spacing_um,
                    registration=registration,
                    input_base=input_base,
                    input_probes=input_probes,
                    reference_base=reference_base,
                    reference_probes=reference_probes,
                    config=config,
                    metadata=metadata,
                )
            )
    return {
        "cell_id": first.cell_id,
        "reference_group_id": first.reference_group_id,
        "records": len(records),
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _summarize(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    eligible = eligible_rows(rows)
    conditions = ["full_contract", *config["comparators"]]
    conditions = list(dict.fromkeys(conditions))
    summaries: dict[str, Any] = {}
    for condition in conditions:
        if condition not in rows[0]["scores"]:
            continue
        summaries[condition] = {
            "aurc": aurc(rows, condition),
            "eligible_cases": len(eligible),
            "nonselective_risk": float(np.mean([row["invalid"] for row in eligible])) if eligible else None,
        }
    endpoints: dict[str, Any] = {}
    for endpoint in sorted({str(row["endpoint"]) for row in rows}):
        subset = [row for row in rows if row["endpoint"] == endpoint]
        selected = eligible_rows(subset)
        endpoints[endpoint] = {
            "rows": len(subset),
            "eligible": len(selected),
            "reference_eligibility_fraction": len(selected) / len(subset),
            "invalid_fraction": float(np.mean([row["invalid"] for row in selected])) if selected else None,
            "full_contract_aurc": aurc(subset, "full_contract") if selected else None,
        }
    partitions = {
        name: len({row["reference_group_id"] for row in rows if row["development_partition"] == name})
        for name in ("score_design", "threshold_calibration")
    }
    return {
        "rows": len(rows),
        "eligible_rows": len(eligible),
        "reference_fields": len({row["reference_group_id"] for row in rows}),
        "pairs": len({row["pair_id"] for row in rows}),
        "registration_eligible_pairs": len({row["pair_id"] for row in rows if row["pair_registration_eligible"]}),
        "hard_abstention_rows": sum(bool(row["hard_abstention"]) for row in eligible),
        "development_partition_fields": partitions,
        "conditions": summaries,
        "endpoints": endpoints,
    }


def run(
    *,
    archive: Path,
    structure: str,
    upscaling_factor: int,
    expected_md5: str,
    config_path: Path,
    output: Path,
    workers: int,
    max_cells: int | None,
    stage: str,
    expected_level_count: int,
) -> dict[str, Any]:
    lock = _verify_lock(LOCK_RECEIPT)
    amendment = _verify_lock(AMENDMENT_LOCK)
    er_layout_lock = _verify_lock(ER_LAYOUT_LOCK) if structure == "ER" else None
    calibration_correction = _verify_lock(CALIBRATION_CORRECTION_LOCK)
    code_audit_correction = _verify_lock(SUPPORT_SCORE_CODE_AUDIT_LOCK)
    pilot_repair, profile_lineage_amendment = _verify_pilot_repair_lineage()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("Config and implementation protocol versions disagree.")
    config_sha = sha256_file(config_path)
    implementation = _implementation_receipt()
    observed_md5 = _md5(archive)
    if observed_md5.lower() != expected_md5.lower():
        raise RuntimeError(f"Archive MD5 mismatch: expected {expected_md5}, observed {observed_md5}.")
    archive_sha = sha256_file(archive)
    records = index_biosr_archive(
        archive,
        structure=structure,
        expected_raw_spacing_um=float(config["raw_sim_sampling_um"]),
        upscaling_factor=upscaling_factor,
        expected_level_count=expected_level_count,
        spacing_absolute_tolerance_um=float(config["mrc_header_spacing_absolute_tolerance_um"]),
        field_of_view_relative_tolerance=float(config["field_of_view_relative_tolerance"]),
    )
    by_cell: dict[str, list[BioSRPairRecord]] = {}
    for record in records:
        by_cell.setdefault(record.cell_id, []).append(record)
    cells = sorted(by_cell)
    if stage in {"score_design", "threshold_calibration"}:
        cells = [
            cell
            for cell in cells
            if development_partition(structure, by_cell[cell][0].reference_group_id) == stage
        ]
    elif stage != "confirmation":
        raise ValueError(f"Unknown stage: {stage}.")
    if stage == "threshold_calibration":
        _verify_lock(SCORE_FORMULA_LOCK)
    if stage == "confirmation":
        _verify_lock(THRESHOLD_LOCK)
    if max_cells is not None:
        if max_cells < 1:
            raise ValueError("max_cells must be positive.")
        if stage != "score_design":
            raise ValueError("Smoke-test limits are permitted only during score_design.")
        cells = cells[:max_cells]
    output.mkdir(parents=True, exist_ok=True)
    checkpoints = output / "cell_checkpoints"
    checkpoints.mkdir(exist_ok=True)
    index_payload = {
        "schema_version": "nostos-biosr-pair-index/1.0",
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_md5": observed_md5,
        "archive_sha256": archive_sha,
        "structure": structure,
        "upscaling_factor": upscaling_factor,
        "expected_level_count": expected_level_count,
        "implementation_sha256": implementation["sha256"],
        "records": [asdict(record) for record in records if record.cell_id in cells],
    }
    (output / "pair_index.json").write_text(json.dumps(index_payload, indent=2) + "\n", encoding="utf-8")
    all_rows: list[dict[str, Any]] = []
    pending: list[str] = []
    checkpoint_receipts: list[dict[str, Any]] = []
    for cell in cells:
        checkpoint = checkpoints / f"{cell}.json"
        payload = _read_checkpoint(
            checkpoint,
            archive_sha256=archive_sha,
            config_sha256=config_sha,
            implementation_sha256=implementation["sha256"],
        )
        if payload is None:
            pending.append(cell)
        else:
            all_rows.extend(payload["rows"])
            checkpoint_receipts.append({key: payload[key] for key in ("cell_id", "rows_count", "elapsed_seconds")})
    if pending:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_cell,
                    str(archive),
                    [asdict(record) for record in by_cell[cell]],
                    config,
                ): cell
                for cell in pending
            }
            for future in as_completed(futures):
                result = future.result()
                cell = str(result["cell_id"])
                payload = {
                    "protocol_version": PROTOCOL_VERSION,
                    "archive_sha256": archive_sha,
                    "config_sha256": config_sha,
                    "implementation_sha256": implementation["sha256"],
                    "cell_id": cell,
                    "reference_group_id": result["reference_group_id"],
                    "records": result["records"],
                    "rows_count": len(result["rows"]),
                    "elapsed_seconds": result["elapsed_seconds"],
                    "rows": result["rows"],
                }
                checkpoint = checkpoints / f"{cell}.json"
                checkpoint.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                all_rows.extend(result["rows"])
                checkpoint_receipts.append({key: payload[key] for key in ("cell_id", "rows_count", "elapsed_seconds")})
                print(f"completed {cell}: {payload['rows_count']} rows in {payload['elapsed_seconds']:.1f} s", flush=True)
    all_rows.sort(key=lambda row: str(row["case_id"]))
    write_rows_jsonl(all_rows, output / "endpoint_cases.jsonl")
    summary = _summarize(all_rows, config)
    receipt = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "smoke_test" if max_cells is not None else f"complete_{stage}",
        "stage": stage,
        "structure": structure,
        "archive": index_payload | {"records": len(index_payload["records"])},
        "config_path": str(config_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "config_sha256": config_sha,
        "implementation": implementation,
        "protocol_lock_sha256": sha256_file(LOCK_RECEIPT),
        "preprocessing_amendment_lock_sha256": sha256_file(AMENDMENT_LOCK),
        "er_layout_amendment_lock_sha256": sha256_file(ER_LAYOUT_LOCK) if er_layout_lock else None,
        "calibration_correction_lock_sha256": sha256_file(CALIBRATION_CORRECTION_LOCK),
        "code_audit_correction_lock_sha256": sha256_file(SUPPORT_SCORE_CODE_AUDIT_LOCK),
        "pilot_repair_lock_sha256": sha256_file(PILOT_REPAIR_LOCK),
        "profile_lineage_amendment_lock_sha256": sha256_file(
            PROFILE_LINEAGE_AMENDMENT_LOCK
        ),
        "protocol_lock": lock["locked_at_utc"],
        "preprocessing_amendment_lock": amendment["locked_at_utc"],
        "calibration_correction_lock": calibration_correction["locked_at_utc"],
        "code_audit_correction_lock": code_audit_correction["locked_at_utc"],
        "pilot_repair_lock": pilot_repair["locked_at_utc"],
        "profile_lineage_amendment_lock": profile_lineage_amendment["locked_at_utc"],
        "workers": workers,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
        },
        "checkpoints": sorted(checkpoint_receipts, key=lambda item: item["cell_id"]),
        "summary": summary,
        "claim_boundary": config["claim_boundary"],
    }
    receipt_path = output / "archive_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt["artifacts"] = {
        "pair_index_sha256": sha256_file(output / "pair_index.json"),
        "endpoint_cases_sha256": sha256_file(output / "endpoint_cases.jsonl"),
        "receipt_sha256_before_artifact_index": sha256_file(receipt_path),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--structure", required=True)
    parser.add_argument("--upscaling-factor", type=int, choices=(2, 3), required=True)
    parser.add_argument("--expected-md5", required=True)
    parser.add_argument("--expected-level-count", type=int, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "paired_acquisition_support_v5.locked.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--max-cells", type=int, help="Explicit smoke-test limit; never a confirmatory run.")
    parser.add_argument(
        "--stage",
        choices=("score_design", "threshold_calibration", "confirmation"),
        required=True,
        help="Enforces prospective access: calibration requires a score lock; confirmation requires a threshold lock.",
    )
    args = parser.parse_args()
    payload = run(
        archive=args.archive,
        structure=args.structure,
        upscaling_factor=args.upscaling_factor,
        expected_md5=args.expected_md5,
        config_path=args.config,
        output=args.output,
        workers=args.workers,
        max_cells=args.max_cells,
        stage=args.stage,
        expected_level_count=args.expected_level_count,
    )
    print(json.dumps({"status": payload["status"], "summary": payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
