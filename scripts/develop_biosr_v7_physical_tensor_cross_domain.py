"""Screen physical tensor scale paths across disclosed BioSR structures without probes."""

from __future__ import annotations

import json
import time
import zipfile
from collections import defaultdict
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
OUTPUT = ROOT / "outputs/nostos0-biosr-v7-physical-tensor-cross-domain-development"
SCALES = (0.2504, 0.3756, 0.5008, 0.7512, 1.0016)
CANDIDATES = (
    ("d035_i100", 0.35, 1.0),
    ("d050_i100", 0.50, 1.0),
    ("d050_i150", 0.50, 1.5),
    ("d050_i200", 0.50, 2.0),
    ("d075_i150", 0.75, 1.5),
    ("d100_i200", 1.00, 2.0),
)
SOURCES = {
    "CCPs": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\CCPs.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-ccp-threshold-calibration-v5/pair_index.json",
        "legacy_rows": ROOT / "outputs/nostos0-biosr-ccp-threshold-calibration-v5/endpoint_cases.jsonl",
    },
    "ER": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\ER.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-er-threshold-calibration-v5/pair_index.json",
        "legacy_rows": ROOT / "outputs/nostos0-biosr-er-threshold-calibration-v5/endpoint_cases.jsonl",
    },
}
MICRO_ROWS = ROOT / "outputs/nostos0-biosr-v7-physical-tensor-development/physical_tensor_candidate_rows.jsonl"
MICRO_LEGACY = ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation/endpoint_cases.jsonl"
FAILURE_RECEIPT = ROOT / "manifests/paired_acquisition_support_v6_confirmation_failure_receipt.json"


def _process_cell(archive: str, records_payload: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    records = [BioSRPairRecord(**item) for item in records_payload]
    first = records[0]
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as opened:
        reference_image = _robust_unit(
            read_mrc_bytes(opened.read(first.reference_member))
        )
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
            raw = read_mrc_bytes(opened.read(record.input_member))
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
                    prefix = f"{record.pair_id}|"
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
                            "orientation_case_id": f"{prefix}tensor_orientation|{scale}",
                            "coherence_case_id": f"{prefix}tensor_coherence|{scale}",
                            "orientation_estimate": estimate.orientation_degrees[index],
                            "orientation_reference": reference.orientation_degrees[index],
                            "orientation_error": axial_angular_error_degrees(
                                estimate.orientation_degrees[index],
                                reference.orientation_degrees[index],
                            ),
                            "coherence_estimate": estimate.coherency[index],
                            "coherence_reference": reference.coherency[index],
                            "coherence_error": abs(
                                estimate.coherency[index]
                                - reference.coherency[index]
                            ),
                            "input_resultant": estimate.orientation_resultant[index],
                            "reference_resultant": reference.orientation_resultant[index],
                            "input_jackknife_axis_drift": estimate.jackknife_axis_drift_degrees[index],
                            "reference_jackknife_axis_drift": reference.jackknife_axis_drift_degrees[index],
                        }
                    )
    return {
        "structure": first.structure,
        "cell_id": first.cell_id,
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _load_legacy() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    paths = [source["legacy_rows"] for source in SOURCES.values()] + [MICRO_LEGACY]
    for path in paths:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["endpoint"] in {"tensor_orientation", "tensor_coherence"}:
                    index[str(row["case_id"])] = row
    return index


def _metrics(values: list[float], tolerance: float) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    return {
        "eligible": len(array),
        "invalid": int(np.sum(array > tolerance)),
        "risk": float(np.mean(array > tolerance)) if len(array) else None,
        "median_error": float(np.median(array)) if len(array) else None,
        "q90_error": float(np.quantile(array, 0.9)) if len(array) else None,
        "maximum_error": float(np.max(array)) if len(array) else None,
    }


def _summaries(
    rows: list[dict[str, Any]], legacy: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for name, derivative, integration in CANDIDATES:
        candidate = [row for row in rows if row["candidate"] == name]
        structures = []
        for structure in sorted({row["structure"] for row in candidate}):
            subset = [row for row in candidate if row["structure"] == structure]
            orientation = [
                row["orientation_error"]
                for row in subset
                if legacy[row["orientation_case_id"]]["pair_registration_eligible"]
                and legacy[row["orientation_case_id"]]["reference_eligible"]
            ]
            coherence = [
                row["coherence_error"]
                for row in subset
                if legacy[row["coherence_case_id"]]["pair_registration_eligible"]
                and legacy[row["coherence_case_id"]]["reference_eligible"]
            ]
            structures.append(
                {
                    "structure": structure,
                    "orientation": _metrics(orientation, 10.0),
                    "coherence": _metrics(coherence, 0.15),
                }
            )
        assessable_orientation = [
            item["orientation"] for item in structures if item["orientation"]["eligible"]
        ]
        assessable_coherence = [
            item["coherence"] for item in structures if item["coherence"]["eligible"]
        ]
        results.append(
            {
                "candidate": name,
                "derivative_scale_fraction": derivative,
                "integration_scale_factor": integration,
                "structures": structures,
                "worst_structure_orientation_risk": max(
                    (item["risk"] for item in assessable_orientation), default=None
                ),
                "worst_structure_orientation_q90_degrees": max(
                    (item["q90_error"] for item in assessable_orientation), default=None
                ),
                "worst_structure_coherence_risk": max(
                    (item["risk"] for item in assessable_coherence), default=None
                ),
                "worst_structure_coherence_q90": max(
                    (item["q90_error"] for item in assessable_coherence), default=None
                ),
            }
        )
    return results


def main() -> None:
    failure = json.loads(FAILURE_RECEIPT.read_text(encoding="utf-8"))
    if failure["status"] != "prospective_v6_failed_after_first_untouched_structure":
        raise ValueError("The v6 failure is not sealed.")
    jobs = []
    sources = []
    for structure, source in SOURCES.items():
        pair_index = json.loads(source["pair_index"].read_text(encoding="utf-8"))
        records = [BioSRPairRecord(**item) for item in pair_index["records"]]
        grouped: dict[str, list[BioSRPairRecord]] = defaultdict(list)
        for record in records:
            grouped[record.cell_id].append(record)
        jobs.extend(
            (str(source["archive"]), [asdict(record) for record in cell_records])
            for cell_records in grouped.values()
        )
        sources.append(
            {
                "structure": structure,
                "fields": len(grouped),
                "pairs": len(records),
                "pair_index_sha256": sha256_file(source["pair_index"]),
                "legacy_rows_sha256": sha256_file(source["legacy_rows"]),
            }
        )

    rows: list[dict[str, Any]] = []
    checkpoints = []
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_process_cell, archive, records): records[0]["cell_id"]
            for archive, records in jobs
        }
        for future in as_completed(futures):
            result = future.result()
            rows.extend(result["rows"])
            checkpoints.append(
                {
                    "structure": result["structure"],
                    "cell_id": result["cell_id"],
                    "elapsed_seconds": result["elapsed_seconds"],
                }
            )
            print(
                f"completed {result['structure']} {result['cell_id']} "
                f"in {result['elapsed_seconds']:.1f} s",
                flush=True,
            )
    with MICRO_ROWS.open("r", encoding="utf-8") as stream:
        micro = [json.loads(line) for line in stream if line.strip()]
    if {row["candidate"] for row in micro} != {item[0] for item in CANDIDATES}:
        raise ValueError("Microtubules candidate set differs from this screen.")
    rows.extend(micro)
    rows.sort(
        key=lambda row: (
            row["candidate"],
            row["structure"],
            row["cell_id"],
            row["signal_level"],
            row["scale_um"],
        )
    )
    legacy = _load_legacy()
    results = _summaries(rows, legacy)
    payload = {
        "schema_version": "nostos-biosr-v7-physical-tensor-cross-domain-development/1.0",
        "status": "candidate_screen_complete_no_selection_frozen",
        "structures": ["CCPs", "ER", "Microtubules"],
        "candidate_definitions": [
            {
                "name": name,
                "derivative_scale_fraction": derivative,
                "integration_scale_factor": integration,
            }
            for name, derivative, integration in CANDIDATES
        ],
        "common_evaluation_domain": "The prospective v5/v6 pair-registration and reference-eligibility flags are reused identically for every tensor candidate.",
        "results": results,
        "selection_rule": "Retain only candidates with raw error risk <=0.10 for every assessable structure and both tensor families; among survivors minimize worst-structure orientation q90, then coherence q90, then computational support size. If none survives, do not select a scalar path and develop a preserved two-scale response surface.",
        "selection_status": "not_yet_evaluated",
        "sources": sources,
        "microtubules_reused_artifact": {
            "path": str(MICRO_ROWS.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(MICRO_ROWS),
        },
        "checkpoints": sorted(
            checkpoints, key=lambda item: (item["structure"], item["cell_id"])
        ),
        "f_actin_image_members_decoded": 0,
        "f_actin_endpoint_outcomes_computed": 0,
        "claim_boundary": "Cross-domain development screen only; not confirmation.",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows_path = OUTPUT / "candidate_rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload["artifacts"] = {
        "candidate_rows": {
            "path": str(rows_path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": rows_path.stat().st_size,
            "sha256": sha256_file(rows_path),
        }
    }
    output_path = OUTPUT / "candidate_screen.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"path": str(output_path.relative_to(ROOT)).replace("\\", "/"), "bytes": output_path.stat().st_size, "sha256": sha256_file(output_path)}, indent=2))


if __name__ == "__main__":
    main()
