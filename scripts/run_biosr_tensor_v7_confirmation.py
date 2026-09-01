"""Run one locked BioSR F-actin confirmation archive for tensor v7."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from nostos.validation.biosr_tensor_confirmation_v7 import (
    archive_layout_from_central_directory,
    evaluate_v7_confirmation,
    index_biosr_tensor_archive_v7,
    select_confirmation_cells_v7,
)
from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    audit_pair_registration,
    image_sha256,
    read_mrc_bytes,
    sha256_file,
    shared_spectral_band_cycles_per_mm,
)
from nostos.validation.tensor_support_v7 import (
    evaluate_tensor_pair,
    measure_resolution_margin_probe,
    measure_tensor_support,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "nostos-paired-acquisition-tensor/7.0"
DEFAULT_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
CONFIRMATION_LOCK = (
    ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
)
IMPLEMENTATION_FILES = (
    Path(__file__).resolve(),
    ROOT / "src/nostos/validation/biosr_tensor_confirmation_v7.py",
    ROOT / "src/nostos/validation/tensor_support_v7.py",
    ROOT / "src/nostos/validation/tensor_contract_audit_v7.py",
    ROOT / "src/nostos/validation/tensor_evidence_v7.py",
    ROOT / "src/nostos/features/physical_tensor.py",
    ROOT / "src/nostos/features/spatial_fft.py",
    ROOT / "src/nostos/core/qc.py",
    ROOT / "src/nostos/validation/paired_acquisition_support.py",
    ROOT / "src/nostos/validation/metrics.py",
    ROOT / "pyproject.toml",
    ROOT / "uv.lock",
)


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _implementation_receipt() -> dict[str, Any]:
    files = [
        {
            "path": str(path.resolve().relative_to(ROOT.resolve())).replace(
                "\\", "/"
            ),
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


def _verify_lock() -> dict[str, Any]:
    payload = json.loads(CONFIRMATION_LOCK.read_text(encoding="utf-8"))
    failures = []
    for item in payload["files"]:
        target = ROOT / item["path"]
        observed = sha256_file(target) if target.is_file() else None
        if (
            not target.is_file()
            or target.stat().st_size != int(item["bytes"])
            or observed != item["sha256"]
        ):
            failures.append(
                {
                    "path": item["path"],
                    "expected": item["sha256"],
                    "observed": observed,
                }
            )
    if failures:
        raise RuntimeError(f"v7 confirmation lock verification failed: {failures}")
    implementation = _implementation_receipt()
    if implementation["sha256"] != payload["implementation_sha256"]:
        raise RuntimeError("Runner implementation differs from the v7 lock.")
    return payload


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
    tensor = config["physical_tensor"]
    scales = tuple(float(value) for value in tensor["physical_scales_um"])
    spectral_band = shared_spectral_band_cycles_per_mm(
        config, first.effective_input_spacing_um
    )
    derivative = float(tensor["derivative_scale_fraction"])
    integration = float(tensor["integration_scale_factor"])
    margin = config["support_contract"]["coherence_only_resolution_margin"]
    sigma = float(margin["sigma_effective_input_pixels"])
    threshold = float(margin["threshold_fraction_of_endpoint_tolerance"])
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as opened:
        reference_payload = opened.read(first.reference_member)
        reference_image = read_mrc_bytes(reference_payload)
        reference_sha = image_sha256(reference_image)
        reference = measure_tensor_support(
            reference_image,
            grid_spacing_um=first.reference_spacing_um,
            effective_spacing_um=first.reference_spacing_um,
            scales_um=scales,
            spectral_band_cycles_per_mm=spectral_band,
            derivative_scale_fraction=derivative,
            integration_scale_factor=integration,
        )
        for record in records:
            raw_payload = opened.read(record.input_member)
            raw = read_mrc_bytes(raw_payload)
            if raw.shape != (record.input_frames, *record.input_shape_yx):
                raise ValueError(
                    f"Unexpected raw shape {raw.shape} for {record.pair_id}."
                )
            input_image = np.mean(raw.astype(np.float64), axis=0)
            registration = audit_pair_registration(
                input_image,
                reference_image,
                reference_spacing_um=record.reference_spacing_um,
                effective_input_spacing_um=record.effective_input_spacing_um,
            )
            measured = measure_tensor_support(
                input_image,
                grid_spacing_um=record.input_grid_spacing_um,
                effective_spacing_um=record.effective_input_spacing_um,
                scales_um=scales,
                spectral_band_cycles_per_mm=spectral_band,
                derivative_scale_fraction=derivative,
                integration_scale_factor=integration,
            )
            strong_probe = measure_resolution_margin_probe(
                input_image,
                grid_spacing_um=record.input_grid_spacing_um,
                effective_spacing_um=record.effective_input_spacing_um,
                scales_um=scales,
                sigma_effective_input_pixels=sigma,
                derivative_scale_fraction=derivative,
                integration_scale_factor=integration,
            )
            rows.extend(
                evaluate_tensor_pair(
                    pair_id=record.pair_id,
                    reference_group_id=record.reference_group_id,
                    structure=record.structure,
                    effective_input_spacing_um=record.effective_input_spacing_um,
                    registration=registration,
                    input_measurement=measured,
                    reference_measurement=reference,
                    scales_um=scales,
                    input_resolution_margin_response=strong_probe,
                    coherence_resolution_margin_threshold_fraction=threshold,
                    resolution_margin_sigma_effective_input_pixels=sigma,
                    metadata={
                        "cell_id": record.cell_id,
                        "signal_level_ordinal": record.signal_level,
                        "input_member": record.input_member,
                        "reference_member": record.reference_member,
                        "raw_stack_sha256": hashlib.sha256(raw_payload).hexdigest(),
                        "input_mean_pixel_sha256": image_sha256(input_image),
                        "reference_mrc_sha256": hashlib.sha256(
                            reference_payload
                        ).hexdigest(),
                        "reference_pixel_sha256": reference_sha,
                        "input_construction": (
                            f"float64 arithmetic mean of {record.input_frames} raw SIM frames"
                        ),
                        "confirmation_selection": "hash_only_in_v7_lock_before_image_member_access",
                        "reference_policy": "frozen_primary_reference_only",
                    },
                )
            )
    return {
        "cell_id": first.cell_id,
        "reference_group_id": first.reference_group_id,
        "records": len(records),
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def run(
    *,
    archive: Path,
    structure: str,
    config_path: Path,
    output: Path,
    workers: int,
) -> dict[str, Any]:
    lock = _verify_lock()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("Config and v7 runner protocol versions disagree.")
    if structure not in config["confirmation"]["structures"]:
        raise ValueError(f"{structure} is not a frozen v7 confirmation structure.")
    specification = config["structures"][structure]
    if archive.name != specification["archive_name"]:
        raise ValueError("Archive basename differs from the frozen configuration.")
    config_sha = sha256_file(config_path)
    if config_sha != lock["config"]["sha256"]:
        raise RuntimeError("Configuration differs from the v7 lock.")
    if archive.stat().st_size != int(specification["archive_bytes"]):
        raise RuntimeError("Archive byte count differs from frozen Figshare metadata.")
    observed_md5 = _md5(archive)
    if observed_md5.lower() != str(specification["archive_md5"]).lower():
        raise RuntimeError("Archive MD5 differs from frozen Figshare metadata.")
    archive_sha = sha256_file(archive)
    implementation = _implementation_receipt()

    layout = archive_layout_from_central_directory(
        archive,
        structure=structure,
        expected_level_count=int(specification["expected_level_count"]),
        reference_basename=str(specification["primary_reference_basename"]),
        excluded_reference_basenames=tuple(
            specification["excluded_reference_basenames"]
        ),
    )
    selected = select_confirmation_cells_v7(
        layout["cells"],
        structure=structure,
        count=int(config["confirmation"]["fields_per_structure"]),
        salt=str(config["confirmation"]["selection_salt"]),
    )
    locked_selected = lock["confirmation"]["selected_cells"][structure]
    if selected != locked_selected:
        raise RuntimeError("Central-directory selection differs from the v7 lock.")

    records = index_biosr_tensor_archive_v7(
        archive,
        structure=structure,
        expected_raw_spacing_um=float(config["raw_sim_sampling_um"]),
        upscaling_factor=int(specification["upscaling_factor"]),
        expected_level_count=int(specification["expected_level_count"]),
        expected_input_frames=int(specification["expected_input_frames"]),
        reference_basename=str(specification["primary_reference_basename"]),
        spacing_absolute_tolerance_um=float(
            config["mrc_header_spacing_absolute_tolerance_um"]
        ),
        field_of_view_relative_tolerance=float(
            config["field_of_view_relative_tolerance"]
        ),
    )
    by_cell: dict[str, list[BioSRPairRecord]] = defaultdict(list)
    for record in records:
        by_cell[record.cell_id].append(record)
    if sorted(by_cell) != layout["cells"]:
        raise RuntimeError("Header index and central-directory cell sets differ.")

    output.mkdir(parents=True, exist_ok=True)
    checkpoints = output / "cell_checkpoints"
    checkpoints.mkdir(exist_ok=True)
    pair_index = {
        "schema_version": "nostos-biosr-tensor-v7-confirmation-pair-index/1.0",
        "selection_status": "selected_and_frozen_before_any_v7_f_actin_image_member_access",
        "selection_rule": config["confirmation"]["field_selection_rule"],
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_md5": observed_md5,
        "archive_sha256": archive_sha,
        "structure": structure,
        "upscaling_factor": int(specification["upscaling_factor"]),
        "expected_level_count": int(specification["expected_level_count"]),
        "expected_input_frames": int(specification["expected_input_frames"]),
        "primary_reference_basename": specification["primary_reference_basename"],
        "excluded_reference_basenames": specification[
            "excluded_reference_basenames"
        ],
        "selected_cells": selected,
        "available_cells": layout["cells"],
        "records": [
            asdict(record) for record in records if record.cell_id in selected
        ],
    }
    pair_index_path = output / "pair_index.json"
    pair_index_path.write_text(
        json.dumps(pair_index, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    all_rows: list[dict[str, Any]] = []
    pending: list[str] = []
    checkpoint_receipts = []
    for cell in selected:
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
            checkpoint_receipts.append(
                {
                    key: payload[key]
                    for key in ("cell_id", "rows_count", "elapsed_seconds")
                }
            )
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
                checkpoint.write_text(
                    json.dumps(payload, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                all_rows.extend(result["rows"])
                checkpoint_receipts.append(
                    {
                        key: payload[key]
                        for key in ("cell_id", "rows_count", "elapsed_seconds")
                    }
                )
                print(
                    f"completed {structure} {cell}: {payload['rows_count']} rows "
                    f"in {payload['elapsed_seconds']:.1f} s",
                    flush=True,
                )
    all_rows.sort(key=lambda row: str(row["case_id"]))
    rows_path = output / "tensor_cases.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    rules = {
        **config["confirmation"]["primary_safety_rules"],
        **config["confirmation"][
            "separate_incremental_coherence_utility_rules"
        ],
    }
    provisional = evaluate_v7_confirmation(all_rows, rules=rules)
    receipt = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "complete_v7_confirmation_archive",
        "analysis_role": "one_of_two_locked_untouched_f_actin_confirmation_archives",
        "structure": structure,
        "selection": {
            "selected_cells": selected,
            "available_cells": len(by_cell),
            "selected_reference_fields": len(selected),
            "outcome_or_pixel_dependent": False,
        },
        "reference_policy": {
            "primary_reference_basename": specification[
                "primary_reference_basename"
            ],
            "excluded_reference_basenames": specification[
                "excluded_reference_basenames"
            ],
        },
        "archive": {
            "path": str(archive.resolve()),
            "bytes": archive.stat().st_size,
            "md5": observed_md5,
            "sha256": archive_sha,
            "figshare_file_id": specification["archive_file_id"],
        },
        "config": {
            "path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": config_sha,
        },
        "implementation": implementation,
        "confirmation_lock_sha256": sha256_file(CONFIRMATION_LOCK),
        "workers": workers,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
        },
        "checkpoints": sorted(
            checkpoint_receipts, key=lambda item: item["cell_id"]
        ),
        "rows": len(all_rows),
        "pairs": len({str(row["pair_id"]) for row in all_rows}),
        "provisional_single_archive_evaluation": provisional,
        "combined_gate_required": True,
        "artifacts": {
            "pair_index": {
                "path": str(pair_index_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": pair_index_path.stat().st_size,
                "sha256": sha256_file(pair_index_path),
            },
            "tensor_cases": {
                "path": str(rows_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": rows_path.stat().st_size,
                "sha256": sha256_file(rows_path),
            },
        },
        "claim_boundary": config["claim_boundary"],
    }
    receipt_path = output / "archive_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--structure",
        choices=("F-actin_linear", "F-actin_nonlinear"),
        required=True,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(2, os.cpu_count() or 1)),
    )
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive.")
    result = run(
        archive=args.archive,
        structure=args.structure,
        config_path=args.config,
        output=args.output,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "structure": result["structure"],
                "selection": result["selection"],
                "rows": result["rows"],
                "pairs": result["pairs"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
