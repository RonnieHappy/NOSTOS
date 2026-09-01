"""Benchmark physical two-scale tensor candidates on consumed Microtubules fields only."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from nostos.features.physical_tensor import physical_structure_tensor_response
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    _robust_unit,
    read_mrc_bytes,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path(
    r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\Microtubules.zip"
)
PAIR_INDEX = ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation/pair_index.json"
LEGACY_ROWS = ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation/endpoint_cases.jsonl"
FAILURE_RECEIPT = ROOT / "manifests/paired_acquisition_support_v6_confirmation_failure_receipt.json"
OUTPUT = ROOT / "outputs/nostos0-biosr-v7-physical-tensor-development"
SCALES = (0.2504, 0.3756, 0.5008, 0.7512, 1.0016)
CANDIDATES = (
    ("d035_i100", 0.35, 1.0),
    ("d050_i100", 0.50, 1.0),
    ("d050_i150", 0.50, 1.5),
    ("d050_i200", 0.50, 2.0),
    ("d075_i150", 0.75, 1.5),
    ("d100_i200", 1.00, 2.0),
)


def _load_legacy() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with LEGACY_ROWS.open("r", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["endpoint"] in {"tensor_orientation", "tensor_coherence"}:
                rows[str(row["case_id"])] = row
    return rows


def _process_cell(
    records_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    started = time.perf_counter()
    records = [BioSRPairRecord(**item) for item in records_payload]
    first = records[0]
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(ARCHIVE) as opened:
        reference_payload = opened.read(first.reference_member)
        reference_image = _robust_unit(read_mrc_bytes(reference_payload))
        references = {
            name: physical_structure_tensor_response(
                reference_image,
                spacing_um=(first.reference_spacing_um, first.reference_spacing_um),
                scales_um=SCALES,
                derivative_scale_fraction=derivative,
                integration_scale_factor=integration,
            )
            for name, derivative, integration in CANDIDATES
        }
        for record in records:
            raw_payload = opened.read(record.input_member)
            raw = read_mrc_bytes(raw_payload)
            input_image = _robust_unit(np.mean(raw.astype(np.float64), axis=0))
            for name, derivative, integration in CANDIDATES:
                estimate = physical_structure_tensor_response(
                    input_image,
                    spacing_um=(record.input_grid_spacing_um, record.input_grid_spacing_um),
                    scales_um=SCALES,
                    derivative_scale_fraction=derivative,
                    integration_scale_factor=integration,
                )
                reference = references[name]
                for index, scale in enumerate(SCALES):
                    legacy_prefix = f"{record.pair_id}|"
                    rows.append(
                        {
                            "candidate": name,
                            "derivative_scale_fraction": derivative,
                            "integration_scale_factor": integration,
                            "structure": record.structure,
                            "cell_id": record.cell_id,
                            "reference_group_id": record.reference_group_id,
                            "signal_level": record.signal_level,
                            "scale_um": scale,
                            "orientation_case_id": f"{legacy_prefix}tensor_orientation|{scale}",
                            "coherence_case_id": f"{legacy_prefix}tensor_coherence|{scale}",
                            "orientation_estimate": estimate.orientation_degrees[index],
                            "orientation_reference": reference.orientation_degrees[index],
                            "orientation_error": axial_angular_error_degrees(
                                estimate.orientation_degrees[index],
                                reference.orientation_degrees[index],
                            ),
                            "coherence_estimate": estimate.coherency[index],
                            "coherence_reference": reference.coherency[index],
                            "coherence_error": abs(
                                estimate.coherency[index] - reference.coherency[index]
                            ),
                            "input_resultant": estimate.orientation_resultant[index],
                            "reference_resultant": reference.orientation_resultant[index],
                            "input_jackknife_axis_drift": estimate.jackknife_axis_drift_degrees[index],
                            "reference_jackknife_axis_drift": reference.jackknife_axis_drift_degrees[index],
                        }
                    )
    return {
        "cell_id": first.cell_id,
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _summary(rows: list[dict[str, Any]], legacy: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, derivative, integration in CANDIDATES:
        candidate = [row for row in rows if row["candidate"] == name]
        orientation = [
            row
            for row in candidate
            if legacy[row["orientation_case_id"]]["pair_registration_eligible"]
            and legacy[row["orientation_case_id"]]["reference_eligible"]
        ]
        coherence = [
            row
            for row in candidate
            if legacy[row["coherence_case_id"]]["pair_registration_eligible"]
            and legacy[row["coherence_case_id"]]["reference_eligible"]
        ]
        orientation_errors = np.asarray(
            [row["orientation_error"] for row in orientation], dtype=float
        )
        coherence_errors = np.asarray(
            [row["coherence_error"] for row in coherence], dtype=float
        )
        by_field = {}
        for field in sorted({row["reference_group_id"] for row in orientation}):
            values = [
                row["orientation_error"]
                for row in orientation
                if row["reference_group_id"] == field
            ]
            by_field[field] = {
                "cases": len(values),
                "invalid": sum(value > 10.0 for value in values),
                "median_error_degrees": float(np.median(values)),
                "maximum_error_degrees": float(np.max(values)),
            }
        results.append(
            {
                "candidate": name,
                "derivative_scale_fraction": derivative,
                "integration_scale_factor": integration,
                "orientation": {
                    "eligible": len(orientation),
                    "invalid": int(np.sum(orientation_errors > 10.0)),
                    "risk": float(np.mean(orientation_errors > 10.0)),
                    "median_error_degrees": float(np.median(orientation_errors)),
                    "q90_error_degrees": float(np.quantile(orientation_errors, 0.9)),
                    "maximum_error_degrees": float(np.max(orientation_errors)),
                    "by_field": by_field,
                },
                "coherence": {
                    "eligible": len(coherence),
                    "invalid": int(np.sum(coherence_errors > 0.15)),
                    "risk": float(np.mean(coherence_errors > 0.15)),
                    "median_absolute_error": float(np.median(coherence_errors)),
                    "q90_absolute_error": float(np.quantile(coherence_errors, 0.9)),
                    "maximum_absolute_error": float(np.max(coherence_errors)),
                },
                "scale_response": {
                    "median_input_orientation_range_degrees": float(
                        np.median(
                            [
                                max(group) - min(group)
                                for group in (
                                    [
                                        row["orientation_estimate"]
                                        for row in candidate
                                        if row["cell_id"] == cell
                                        and row["signal_level"] == level
                                    ]
                                    for cell in sorted({row["cell_id"] for row in candidate})
                                    for level in sorted(
                                        {
                                            row["signal_level"]
                                            for row in candidate
                                            if row["cell_id"] == cell
                                        }
                                    )
                                )
                            ]
                        )
                    ),
                },
            }
        )
    return results


def main() -> None:
    failure = json.loads(FAILURE_RECEIPT.read_text(encoding="utf-8"))
    if failure["status"] != "prospective_v6_failed_after_first_untouched_structure":
        raise ValueError("v6 failure is not sealed.")
    pair_index = json.loads(PAIR_INDEX.read_text(encoding="utf-8"))
    records = [BioSRPairRecord(**item) for item in pair_index["records"]]
    selected = set(failure["microtubules_result"]["selected_fields"])
    if {record.cell_id for record in records} != selected:
        raise ValueError("Development cells differ from the sealed failed tranche.")
    by_cell: dict[str, list[BioSRPairRecord]] = {}
    for record in records:
        by_cell.setdefault(record.cell_id, []).append(record)

    all_rows: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_process_cell, [asdict(record) for record in cell_records]): cell
            for cell, cell_records in by_cell.items()
        }
        for future in as_completed(futures):
            result = future.result()
            all_rows.extend(result["rows"])
            checkpoints.append(
                {
                    "cell_id": result["cell_id"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "rows": len(result["rows"]),
                }
            )
            print(
                f"completed {result['cell_id']} in {result['elapsed_seconds']:.1f} s",
                flush=True,
            )
    all_rows.sort(
        key=lambda row: (
            row["candidate"],
            row["cell_id"],
            row["signal_level"],
            row["scale_um"],
        )
    )
    legacy = _load_legacy()
    payload = {
        "schema_version": "nostos-biosr-v7-physical-tensor-development/1.0",
        "status": "development_only_after_v6_failure",
        "scope": {
            "structure": "Microtubules",
            "fields": sorted(selected),
            "paired_acquisitions": len(records),
            "candidate_count": len(CANDIDATES),
            "f_actin_image_members_decoded": 0,
            "f_actin_endpoint_outcomes_computed": 0,
        },
        "lineage": {
            "v6_failure_receipt": {
                "path": str(FAILURE_RECEIPT.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(FAILURE_RECEIPT),
            },
            "micro_pair_index_sha256": sha256_file(PAIR_INDEX),
            "micro_legacy_rows_sha256": sha256_file(LEGACY_ROWS),
            "implementation_sha256": sha256_file(Path(__file__)),
            "physical_tensor_sha256": sha256_file(
                ROOT / "src/nostos/features/physical_tensor.py"
            ),
        },
        "candidate_definitions": [
            {
                "name": name,
                "derivative_scale_fraction": derivative,
                "integration_scale_factor": integration,
            }
            for name, derivative, integration in CANDIDATES
        ],
        "comparison_eligibility": "Identical pair-registration and reference-eligibility flags emitted prospectively by v6; no candidate may alter which Microtubules cases are compared.",
        "results": _summary(all_rows, legacy),
        "checkpoints": sorted(checkpoints, key=lambda item: item["cell_id"]),
        "selection_status": "candidate_benchmark_only_no_v7_choice_yet",
        "claim_boundary": "Post-failure development on eight consumed Microtubules fields; not confirmation and not evidence about F-actin.",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows_path = OUTPUT / "physical_tensor_candidate_rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload["artifacts"] = {
        "rows": {
            "path": str(rows_path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": rows_path.stat().st_size,
            "sha256": sha256_file(rows_path),
        }
    }
    output_path = OUTPUT / "candidate_benchmark.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
