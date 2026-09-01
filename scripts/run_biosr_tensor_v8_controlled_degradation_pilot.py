"""Run the locked BioSR v8 controlled-degradation engineering pilot."""

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
    index_biosr_tensor_archive_v7,
    select_confirmation_cells_v7,
)
from nostos.validation.controlled_degradation_v8 import (
    apply_controlled_degradation,
    deterministic_condition_seed,
    evaluate_controlled_degradation_pilot,
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
PROTOCOL_VERSION = (
    "nostos-paired-acquisition-tensor/8.0-controlled-degradation-pilot"
)
CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v8_controlled_degradation_pilot.locked.json"
)
LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v8_controlled_degradation_pilot_lock.json"
)
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
DEFAULT_OUTPUT = (
    ROOT / "outputs/nostos0-biosr-tensor-v8-controlled-degradation-pilot"
)
SOURCES = {
    "F-actin_linear": {
        "archive": Path(
            r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin.zip"
        ),
        "config": ROOT / "configs/paired_acquisition_tensor_v7.locked.json",
    },
    "F-actin_nonlinear": {
        "archive": Path(
            r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin_Nonlinear.zip"
        ),
        "config": (
            ROOT / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
        ),
    },
}
IMPLEMENTATION_FILES = (
    Path(__file__).resolve(),
    ROOT / "src/nostos/validation/controlled_degradation_v8.py",
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


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _implementation_receipt() -> dict[str, Any]:
    files = [_artifact(path) for path in IMPLEMENTATION_FILES]
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "files": files}


def _verify_lock() -> dict[str, Any]:
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    for item in payload["files"]:
        path = ROOT / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256_file(path) != item["sha256"]
        ):
            raise RuntimeError(f"v8 locked file differs: {item['path']}")
    implementation = _implementation_receipt()
    if implementation["sha256"] != payload["implementation_sha256"]:
        raise RuntimeError("v8 implementation differs from its lock.")
    if sha256_file(CONFIG) != payload["config"]["sha256"]:
        raise RuntimeError("v8 config differs from its lock.")
    for structure, source in SOURCES.items():
        archive = Path(source["archive"])
        expected = payload["archives"][structure]
        if archive.stat().st_size != int(expected["bytes"]):
            raise RuntimeError(f"Archive byte mismatch for {structure}.")
        if sha256_file(archive) != expected["sha256"]:
            raise RuntimeError(f"Archive hash mismatch for {structure}.")
    return payload


def _read_checkpoint(
    path: Path,
    *,
    lock_sha256: str,
    implementation_sha256: str,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("lock_sha256") != lock_sha256
        or payload.get("implementation_sha256") != implementation_sha256
    ):
        return None
    return payload


def _process_cell(
    archive_path: str,
    records_payload: list[dict[str, Any]],
    source_config: dict[str, Any],
    challenge_config: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    records = [BioSRPairRecord(**item) for item in records_payload]
    first = records[0]
    tensor = source_config["physical_tensor"]
    scales = tuple(float(value) for value in tensor["physical_scales_um"])
    spectral_band = shared_spectral_band_cycles_per_mm(
        source_config, first.effective_input_spacing_um
    )
    derivative = float(tensor["derivative_scale_fraction"])
    integration = float(tensor["integration_scale_factor"])
    margin = source_config["support_contract"][
        "coherence_only_resolution_margin"
    ]
    margin_sigma = float(margin["sigma_effective_input_pixels"])
    margin_threshold = float(margin["threshold_fraction_of_endpoint_tolerance"])
    base_seed = int(challenge_config["randomness"]["base_seed"])
    rows: list[dict[str, Any]] = []

    with zipfile.ZipFile(archive_path) as opened:
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
            clean = np.mean(raw.astype(np.float64), axis=0)
            registration = audit_pair_registration(
                clean,
                reference_image,
                reference_spacing_um=record.reference_spacing_um,
                effective_input_spacing_um=record.effective_input_spacing_um,
            )
            for degradation in challenge_config["degradations"]:
                degradation_id = str(degradation["id"])
                condition_seed = deterministic_condition_seed(
                    base_seed,
                    pair_id=record.pair_id,
                    condition_id=degradation_id,
                )
                candidate = apply_controlled_degradation(
                    clean, degradation, seed=condition_seed
                )
                measured = measure_tensor_support(
                    candidate,
                    grid_spacing_um=record.input_grid_spacing_um,
                    effective_spacing_um=record.effective_input_spacing_um,
                    scales_um=scales,
                    spectral_band_cycles_per_mm=spectral_band,
                    derivative_scale_fraction=derivative,
                    integration_scale_factor=integration,
                )
                strong_probe = measure_resolution_margin_probe(
                    candidate,
                    grid_spacing_um=record.input_grid_spacing_um,
                    effective_spacing_um=record.effective_input_spacing_um,
                    scales_um=scales,
                    sigma_effective_input_pixels=margin_sigma,
                    derivative_scale_fraction=derivative,
                    integration_scale_factor=integration,
                )
                rows.extend(
                    evaluate_tensor_pair(
                        pair_id=f"{record.pair_id}|degradation_{degradation_id}",
                        reference_group_id=record.reference_group_id,
                        structure=record.structure,
                        effective_input_spacing_um=record.effective_input_spacing_um,
                        registration=registration,
                        input_measurement=measured,
                        reference_measurement=reference,
                        scales_um=scales,
                        input_resolution_margin_response=strong_probe,
                        coherence_resolution_margin_threshold_fraction=margin_threshold,
                        resolution_margin_sigma_effective_input_pixels=margin_sigma,
                        metadata={
                            "cell_id": record.cell_id,
                            "signal_level_ordinal": record.signal_level,
                            "input_member": record.input_member,
                            "reference_member": record.reference_member,
                            "raw_stack_sha256": hashlib.sha256(raw_payload).hexdigest(),
                            "clean_input_mean_pixel_sha256": image_sha256(clean),
                            "degraded_input_pixel_sha256": image_sha256(candidate),
                            "reference_mrc_sha256": hashlib.sha256(
                                reference_payload
                            ).hexdigest(),
                            "reference_pixel_sha256": reference_sha,
                            "degradation_id": degradation_id,
                            "degradation_family": degradation["family"],
                            "severity_rank": int(degradation["severity_rank"]),
                            "degradation_specification": dict(degradation),
                            "condition_seed": condition_seed,
                            "registration_authority": (
                                "clean source pair; degradation preserves coordinates"
                            ),
                            "selection": (
                                "v8 hash-only selection before selected-cell pixel decode"
                            ),
                        },
                    )
                )
    return {
        "structure": first.structure,
        "cell_id": first.cell_id,
        "reference_group_id": first.reference_group_id,
        "base_pairs": len(records),
        "degradation_conditions": len(challenge_config["degradations"]),
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _index_sources(
    challenge: dict[str, Any], lock: dict[str, Any]
) -> tuple[list[BioSRPairRecord], dict[str, dict[str, Any]]]:
    v7_lock = json.loads(V7_LOCK.read_text(encoding="utf-8"))
    all_records: list[BioSRPairRecord] = []
    configs: dict[str, dict[str, Any]] = {}
    for structure, source in SOURCES.items():
        config_path = Path(source["config"])
        source_config = json.loads(config_path.read_text(encoding="utf-8"))
        configs[structure] = source_config
        specification = source_config["structures"][structure]
        archive = Path(source["archive"])
        layout = archive_layout_from_central_directory(
            archive,
            structure=structure,
            expected_level_count=int(specification["expected_level_count"]),
            reference_basename=str(specification["primary_reference_basename"]),
            excluded_reference_basenames=tuple(
                specification["excluded_reference_basenames"]
            ),
        )
        prior = set(v7_lock["confirmation"]["selected_cells"][structure])
        eligible = [cell for cell in layout["cells"] if cell not in prior]
        selected = select_confirmation_cells_v7(
            eligible,
            structure=structure,
            count=int(challenge["selection"]["fields_per_structure"]),
            salt=str(challenge["selection"]["selection_salt"]),
        )
        if selected != challenge["selection"]["selected_cells"][structure]:
            raise RuntimeError(f"Config selection mismatch for {structure}.")
        if selected != lock["selected_cells"][structure]:
            raise RuntimeError(f"Lock selection mismatch for {structure}.")
        records = index_biosr_tensor_archive_v7(
            archive,
            structure=structure,
            expected_raw_spacing_um=float(source_config["raw_sim_sampling_um"]),
            upscaling_factor=int(specification["upscaling_factor"]),
            expected_level_count=int(specification["expected_level_count"]),
            expected_input_frames=int(specification["expected_input_frames"]),
            reference_basename=str(specification["primary_reference_basename"]),
            spacing_absolute_tolerance_um=float(
                source_config["mrc_header_spacing_absolute_tolerance_um"]
            ),
            field_of_view_relative_tolerance=float(
                source_config["field_of_view_relative_tolerance"]
            ),
        )
        selected_levels = set(challenge["selection"]["signal_levels"][structure])
        selected_set = set(selected)
        kept = [
            record
            for record in records
            if record.cell_id in selected_set
            and record.signal_level in selected_levels
        ]
        expected = len(selected) * len(selected_levels)
        if len(kept) != expected:
            raise RuntimeError(f"Expected {expected} selected pairs for {structure}.")
        all_records.extend(kept)
    return all_records, configs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive.")

    challenge = json.loads(CONFIG.read_text(encoding="utf-8"))
    if challenge["protocol_version"] != PROTOCOL_VERSION:
        raise RuntimeError("Unexpected v8 protocol version.")
    lock = _verify_lock()
    implementation = _implementation_receipt()
    lock_sha256 = sha256_file(LOCK)
    records, source_configs = _index_sources(challenge, lock)

    args.output.mkdir(parents=True, exist_ok=True)
    pair_index_path = args.output / "pair_index.json"
    pair_index = {
        "schema_version": "nostos-biosr-v8-controlled-degradation-pair-index/1.0",
        "selection_status": "locked_before_selected_cell_pixel_decode",
        "records": [asdict(record) for record in records],
    }
    pair_index_path.write_text(
        json.dumps(pair_index, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    grouped: dict[tuple[str, str], list[BioSRPairRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.structure, record.cell_id)].append(record)
    checkpoints = args.output / "cell_checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    pending: list[tuple[str, str, list[BioSRPairRecord]]] = []
    for (structure, cell), cell_records in sorted(grouped.items()):
        path = checkpoints / f"{structure}_{cell}.json"
        checkpoint = _read_checkpoint(
            path,
            lock_sha256=lock_sha256,
            implementation_sha256=implementation["sha256"],
        )
        if checkpoint is None:
            pending.append((structure, cell, cell_records))
        else:
            results.append(checkpoint["result"])
            print(f"reused {structure} {cell}: {len(checkpoint['result']['rows'])} rows")

    if pending:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    _process_cell,
                    str(SOURCES[structure]["archive"]),
                    [asdict(record) for record in cell_records],
                    source_configs[structure],
                    challenge,
                ): (structure, cell)
                for structure, cell, cell_records in pending
            }
            for future in as_completed(futures):
                structure, cell = futures[future]
                result = future.result()
                checkpoint_path = checkpoints / f"{structure}_{cell}.json"
                checkpoint_path.write_text(
                    json.dumps(
                        {
                            "lock_sha256": lock_sha256,
                            "implementation_sha256": implementation["sha256"],
                            "result": result,
                        },
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                results.append(result)
                print(
                    f"completed {structure} {cell}: {len(result['rows'])} rows "
                    f"in {result['elapsed_seconds']:.1f} s",
                    flush=True,
                )

    rows = [row for result in results for row in result["rows"]]
    expected_rows = (
        int(challenge["selection"]["base_paired_acquisitions"])
        * len(challenge["degradations"])
        * 5
        * 2
    )
    if len(rows) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} rows; observed {len(rows)}.")
    if len({str(row["case_id"]) for row in rows}) != len(rows):
        raise RuntimeError("Duplicate v8 case identifiers detected.")

    rows_path = args.output / "tensor_cases.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in sorted(rows, key=lambda item: str(item["case_id"])):
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    evaluation = evaluate_controlled_degradation_pilot(
        rows, gates=challenge["pilot_success_gates"]
    )
    receipt = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "complete_v8_controlled_degradation_pilot",
        "pilot_evaluation": evaluation,
        "selection": challenge["selection"],
        "degradations": challenge["degradations"],
        "rows": len(rows),
        "base_pairs": len(records),
        "transformed_pairs": len(records) * len(challenge["degradations"]),
        "reference_fields": len(grouped),
        "lock": _artifact(LOCK),
        "config": _artifact(CONFIG),
        "implementation": implementation,
        "archives": lock["archives"],
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
            "workers": args.workers,
        },
        "checkpoints": [
            {
                "structure": result["structure"],
                "cell_id": result["cell_id"],
                "rows": len(result["rows"]),
                "elapsed_seconds": result["elapsed_seconds"],
            }
            for result in sorted(
                results, key=lambda item: (item["structure"], item["cell_id"])
            )
        ],
        "artifacts": {
            "pair_index": _artifact(pair_index_path),
            "tensor_cases": _artifact(rows_path),
        },
        "claim_boundary": challenge["claim_boundary"],
    }
    receipt_path = args.output / "pilot_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "receipt": _artifact(receipt_path),
                "status": evaluation["status"],
                "passes": evaluation["passes"],
                "assessable": evaluation["assessable"],
                "full_coverage": evaluation["overall"]["full_contract"][
                    "coverage"
                ],
                "full_risk": evaluation["overall"]["full_contract"]["risk"],
                "qc_risk": evaluation["overall"][
                    "conventional_acquisition_qc"
                ]["risk"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
