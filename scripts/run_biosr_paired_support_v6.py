"""Run one locked BioSR v6 initial-confirmation archive."""

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

from nostos.validation.confirmation_v6 import (
    evaluate_v6_confirmation,
    select_confirmation_cells,
)
from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    audit_pair_registration,
    evaluate_precomputed_pair,
    image_sha256,
    index_biosr_archive,
    measure_with_mild_probes,
    read_mrc_bytes,
    shared_spectral_band_cycles_per_mm,
    sha256_file,
    write_rows_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "nostos-paired-acquisition-support/6.0"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "paired_acquisition_support_v6.locked.json"
CONFIRMATION_LOCK = (
    PROJECT_ROOT / "manifests" / "paired_acquisition_support_v6_confirmation_lock.json"
)
IMPLEMENTATION_FILES = (
    Path(__file__).resolve(),
    PROJECT_ROOT / "src" / "nostos" / "validation" / "paired_acquisition_support.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "selective_policy_v6.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "confirmation_v6.py",
    PROJECT_ROOT / "src" / "nostos" / "features" / "spatial_fft.py",
    PROJECT_ROOT / "src" / "nostos" / "features" / "response_modules.py",
    PROJECT_ROOT / "src" / "nostos" / "core" / "qc.py",
    PROJECT_ROOT / "src" / "nostos" / "validation" / "metrics.py",
    PROJECT_ROOT / "pyproject.toml",
    PROJECT_ROOT / "uv.lock",
)


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures = []
    for item in payload["files"]:
        target = PROJECT_ROOT / item["path"]
        observed = sha256_file(target) if target.is_file() else None
        if (
            not target.is_file()
            or target.stat().st_size != int(item["bytes"])
            or observed != item["sha256"]
        ):
            failures.append(
                {
                    "path": item["path"],
                    "expected": item,
                    "observed_sha256": observed,
                }
            )
    if failures:
        raise RuntimeError(f"v6 confirmation lock verification failed: {failures}")
    return payload


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
    spectral_band = shared_spectral_band_cycles_per_mm(
        config,
        first.effective_input_spacing_um,
    )
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
                "confirmation_selection": "hash_only_before_pixel_decode",
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


def run(
    *,
    archive: Path,
    structure: str,
    config_path: Path,
    output: Path,
    workers: int,
) -> dict[str, Any]:
    lock = _verify_lock(CONFIRMATION_LOCK)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("Config and v6 runner protocol versions disagree.")
    if structure not in set(config["initial_confirmation"]["structures"]):
        raise ValueError(f"{structure} is not a frozen confirmation structure.")
    specification = config["structures"][structure]
    if not str(specification["role"]).startswith("untouched_"):
        raise ValueError(f"{structure} is not marked untouched.")
    implementation = _implementation_receipt()
    if implementation["sha256"] != lock["implementation_sha256"]:
        raise RuntimeError("Runner implementation differs from the v6 confirmation lock.")
    config_sha = sha256_file(config_path)
    if config_sha != lock["config"]["sha256"]:
        raise RuntimeError("Configuration differs from the v6 confirmation lock.")
    if archive.stat().st_size != int(specification["archive_bytes"]):
        raise RuntimeError("Archive byte count differs from frozen Figshare metadata.")
    observed_md5 = _md5(archive)
    if observed_md5.lower() != str(specification["archive_md5"]).lower():
        raise RuntimeError("Archive MD5 differs from frozen Figshare metadata.")
    archive_sha = sha256_file(archive)

    records = index_biosr_archive(
        archive,
        structure=structure,
        expected_raw_spacing_um=float(config["raw_sim_sampling_um"]),
        upscaling_factor=int(specification["upscaling_factor"]),
        expected_level_count=int(specification["expected_level_count"]),
        spacing_absolute_tolerance_um=float(
            config["mrc_header_spacing_absolute_tolerance_um"]
        ),
        field_of_view_relative_tolerance=float(
            config["field_of_view_relative_tolerance"]
        ),
    )
    by_cell: dict[str, list[BioSRPairRecord]] = {}
    for record in records:
        by_cell.setdefault(record.cell_id, []).append(record)
    cells = select_confirmation_cells(
        by_cell,
        structure=structure,
        count=int(config["initial_confirmation"]["fields_per_structure"]),
    )
    available_reference_group_ids = sorted(
        records_for_cell[0].reference_group_id
        for records_for_cell in by_cell.values()
    )

    output.mkdir(parents=True, exist_ok=True)
    checkpoints = output / "cell_checkpoints"
    checkpoints.mkdir(exist_ok=True)
    pair_index = {
        "schema_version": "nostos-biosr-v6-confirmation-pair-index/1.0",
        "selection_status": "selected_before_pixel_decode_by_frozen_hash_rule",
        "selection_rule": config["initial_confirmation"]["field_selection_rule"],
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_md5": observed_md5,
        "archive_sha256": archive_sha,
        "structure": structure,
        "upscaling_factor": int(specification["upscaling_factor"]),
        "expected_level_count": int(specification["expected_level_count"]),
        "implementation_sha256": implementation["sha256"],
        "selected_cells": cells,
        "available_reference_group_ids": available_reference_group_ids,
        "records": [asdict(record) for record in records if record.cell_id in cells],
    }
    pair_index_path = output / "pair_index.json"
    pair_index_path.write_text(
        json.dumps(pair_index, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    all_rows: list[dict[str, Any]] = []
    pending = []
    checkpoint_receipts = []
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
    endpoint_path = output / "endpoint_cases.jsonl"
    write_rows_jsonl(all_rows, endpoint_path)
    provisional = evaluate_v6_confirmation(all_rows, config=config)
    receipt = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "complete_initial_confirmation_archive",
        "analysis_role": "one_of_three_locked_initial_confirmation_archives",
        "structure": structure,
        "selection": {
            "rule": config["initial_confirmation"]["field_selection_rule"],
            "selected_cells": cells,
            "available_cells": len(by_cell),
            "available_reference_group_ids": available_reference_group_ids,
            "selected_reference_fields": len(cells),
            "outcome_or_pixel_dependent": False,
        },
        "archive": {
            "path": str(archive.resolve()),
            "bytes": archive.stat().st_size,
            "md5": observed_md5,
            "sha256": archive_sha,
            "figshare_file_id": specification["archive_file_id"],
        },
        "config": {
            "path": str(config_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
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
        "checkpoints": sorted(checkpoint_receipts, key=lambda item: item["cell_id"]),
        "rows": len(all_rows),
        "pairs": len({str(row["pair_id"]) for row in all_rows}),
        "provisional_single_archive_policy_summary": provisional,
        "combined_gate_required": True,
        "claim_boundary": config["claim_boundary"],
    }
    receipt_path = output / "archive_receipt.json"
    receipt["artifacts"] = {
        "pair_index": {
            "bytes": pair_index_path.stat().st_size,
            "sha256": sha256_file(pair_index_path),
        },
        "endpoint_cases": {
            "bytes": endpoint_path.stat().st_size,
            "sha256": sha256_file(endpoint_path),
        },
    }
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
        choices=("Microtubules", "F-actin_linear", "F-actin_nonlinear"),
        required=True,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
    )
    args = parser.parse_args()
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
