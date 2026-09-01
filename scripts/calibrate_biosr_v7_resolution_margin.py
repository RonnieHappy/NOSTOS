"""Calibrate one cross-domain v7 resolution-margin cutoff before F-actin access."""

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
from scipy import ndimage

from nostos.features.physical_tensor import (
    axial_circular_wasserstein_degrees,
    physical_structure_tensor_response,
)
from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    _robust_unit,
    read_mrc_bytes,
    sha256_file,
)
from nostos.validation.tensor_contract_audit_v7 import (
    incremental_comparator,
    summarize_policy,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_ROWS = ROOT / "outputs/nostos0-biosr-v7-tensor-distribution-development/tensor_cases.jsonl"
DEVELOPMENT = ROOT / "outputs/nostos0-biosr-v7-tensor-distribution-development/tensor_distribution_development.json"
OUTPUT = ROOT / "outputs/nostos0-biosr-v7-resolution-margin-calibration"
SCALES = (0.2504, 0.3756, 0.5008, 0.7512, 1.0016)
SIGMA_EFFECTIVE_INPUT_PIXELS = 2.0
SOURCES = {
    "CCPs": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\CCPs.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-ccp-threshold-calibration-v5/pair_index.json",
    },
    "ER": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\ER.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-er-threshold-calibration-v5/pair_index.json",
    },
    "Microtubules": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\Microtubules.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation/pair_index.json",
    },
}
RULES = {
    "target_observed_risk": 0.10,
    "maximum_cluster_bootstrap_risk_upper95": 0.15,
    "minimum_overall_coverage": 0.80,
    "minimum_structure_family_coverage": 0.70,
    "maximum_full_minus_qc_risk": 0.0,
    "maximum_coverage_loss_vs_qc": 0.10,
    "minimum_invalid_enrichment_among_qc_only_rejections": 2.0,
}


def _response(image: np.ndarray, spacing: float):
    return physical_structure_tensor_response(
        image,
        spacing_um=(spacing, spacing),
        scales_um=SCALES,
        derivative_scale_fraction=0.5,
        integration_scale_factor=1.0,
    )


def _process_cell(
    archive: str,
    records_payload: list[dict[str, Any]],
    base_payload: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    started = time.perf_counter()
    records = [BioSRPairRecord(**item) for item in records_payload]
    rows = []
    with zipfile.ZipFile(archive) as opened:
        for record in records:
            raw = read_mrc_bytes(opened.read(record.input_member))
            image = _robust_unit(np.mean(raw.astype(np.float64), axis=0))
            sigma_grid = (
                SIGMA_EFFECTIVE_INPUT_PIXELS
                * record.effective_input_spacing_um
                / record.input_grid_spacing_um
            )
            probe = _response(
                ndimage.gaussian_filter(image, sigma=sigma_grid, mode="reflect"),
                record.input_grid_spacing_um,
            )
            for index, scale in enumerate(SCALES):
                for endpoint, probe_value in (
                    (
                        "tensor_orientation_distribution",
                        list(probe.orientation_histograms[index]),
                    ),
                    ("tensor_coherence", float(probe.coherency[index])),
                ):
                    case_id = f"{record.pair_id}|{endpoint}|{scale}"
                    base = base_payload[case_id]
                    if endpoint == "tensor_orientation_distribution":
                        drift = axial_circular_wasserstein_degrees(
                            base["estimate"], probe_value
                        )
                    else:
                        drift = abs(float(base["estimate"]) - float(probe_value))
                    rows.append(
                        {
                            "case_id": case_id,
                            "resolution_margin_drift": drift,
                            "normalized_resolution_margin_drift": drift
                            / float(base["invalidity_tolerance"]),
                        }
                    )
    return {
        "structure": records[0].structure,
        "cell_id": records[0].cell_id,
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _candidate_rows(
    base_rows: list[dict[str, Any]],
    drift: dict[str, dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    result = []
    for row in base_rows:
        clone = dict(row)
        clone["scores"] = dict(row["scores"])
        normalized = float(drift[row["case_id"]]["normalized_resolution_margin_drift"])
        clone["scores"]["full_contract"] = max(
            float(row["scores"]["full_contract"]),
            normalized / threshold,
        )
        clone["resolution_margin"] = {
            "sigma_effective_input_pixels": SIGMA_EFFECTIVE_INPUT_PIXELS,
            "drift": drift[row["case_id"]]["resolution_margin_drift"],
            "normalized_to_endpoint_tolerance": normalized,
            "candidate_threshold": threshold,
        }
        result.append(clone)
    return result


def _passes(full: dict[str, Any], comparator: dict[str, Any]) -> bool:
    return bool(
        full["coverage"] >= RULES["minimum_overall_coverage"]
        and full["risk"] is not None
        and full["risk"] <= RULES["target_observed_risk"]
        and full["cluster_bootstrap_risk_upper95"] is not None
        and full["cluster_bootstrap_risk_upper95"]
        <= RULES["maximum_cluster_bootstrap_risk_upper95"]
        and all(
            item["coverage"] >= RULES["minimum_structure_family_coverage"]
            and item["risk"] is not None
            and item["risk"] <= RULES["target_observed_risk"]
            and item["cluster_bootstrap_risk_upper95"] is not None
            and item["cluster_bootstrap_risk_upper95"]
            <= RULES["maximum_cluster_bootstrap_risk_upper95"]
            for item in full["combinations"]
        )
        and comparator["full_minus_comparator_risk"]
        <= RULES["maximum_full_minus_qc_risk"]
        and comparator["coverage_loss_vs_comparator"]
        <= RULES["maximum_coverage_loss_vs_qc"]
        and comparator["invalid_enrichment_among_comparator_only_rejections"]
        is not None
        and comparator["invalid_enrichment_among_comparator_only_rejections"]
        >= RULES["minimum_invalid_enrichment_among_qc_only_rejections"]
    )


def main() -> None:
    development = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
    if development["scope"]["f_actin_image_members_decoded"] != 0:
        raise ValueError("F-actin is not sealed in the development receipt.")
    base_rows = [
        json.loads(line)
        for line in BASE_ROWS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base_by_id = {row["case_id"]: row for row in base_rows}
    base_by_pair: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in base_rows:
        base_by_pair[str(row["pair_id"])][str(row["case_id"])] = row
    jobs = []
    source_receipts = []
    for structure, source in SOURCES.items():
        pair_index = json.loads(source["pair_index"].read_text(encoding="utf-8"))
        records = [BioSRPairRecord(**item) for item in pair_index["records"]]
        grouped: dict[str, list[BioSRPairRecord]] = defaultdict(list)
        for record in records:
            grouped[record.cell_id].append(record)
        jobs.extend(
            (
                str(source["archive"]),
                [asdict(record) for record in cell_records],
            )
            for cell_records in grouped.values()
        )
        source_receipts.append(
            {
                "structure": structure,
                "fields": len(grouped),
                "pairs": len(records),
                "pair_index_sha256": sha256_file(source["pair_index"]),
            }
        )

    drift_rows = []
    checkpoints = []
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {}
        for archive, records in jobs:
            cell_base: dict[str, dict[str, Any]] = {}
            for record in records:
                cell_base.update(base_by_pair[str(record["pair_id"])])
            future = executor.submit(_process_cell, archive, records, cell_base)
            futures[future] = records[0]["cell_id"]
        for future in as_completed(futures):
            result = future.result()
            drift_rows.extend(result["rows"])
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
    drift = {row["case_id"]: row for row in drift_rows}
    if set(drift) != set(base_by_id):
        raise ValueError("Resolution-margin rows do not cover every base case exactly once.")

    candidates = sorted(
        {
            float(row["normalized_resolution_margin_drift"])
            for row in drift_rows
        },
        reverse=True,
    )
    evaluations = []
    selected = None
    for threshold in candidates:
        rows = _candidate_rows(base_rows, drift, threshold)
        full = summarize_policy(rows, condition="full_contract")
        comparator = incremental_comparator(rows)
        passed = _passes(full, comparator)
        evaluations.append(
            {
                "threshold_fraction_of_endpoint_tolerance": threshold,
                "full": {
                    key: full[key]
                    for key in (
                        "eligible",
                        "accepted",
                        "coverage",
                        "invalid",
                        "risk",
                        "cluster_bootstrap_risk_upper95",
                    )
                },
                "combinations": [
                    {
                        key: item[key]
                        for key in (
                            "structure",
                            "endpoint_family",
                            "coverage",
                            "invalid",
                            "risk",
                            "cluster_bootstrap_risk_upper95",
                        )
                    }
                    for item in full["combinations"]
                ],
                "incremental_comparator": comparator,
                "passes": passed,
            }
        )
        if passed:
            selected = evaluations[-1]
            break
    OUTPUT.mkdir(parents=True, exist_ok=True)
    drift_path = OUTPUT / "resolution_margin_rows.jsonl"
    with drift_path.open("w", encoding="utf-8") as stream:
        for row in sorted(drift_rows, key=lambda item: item["case_id"]):
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload = {
        "schema_version": "nostos-biosr-v7-resolution-margin-calibration/1.0",
        "status": (
            "threshold_selected_pending_v7_freeze"
            if selected is not None
            else "no_threshold_do_not_freeze"
        ),
        "probe": {
            "operation": "Gaussian blur on the normalized input before measurement",
            "sigma_effective_input_pixels": SIGMA_EFFECTIVE_INPUT_PIXELS,
            "score": "endpoint drift divided by endpoint invalidity tolerance",
        },
        "selection_rule": "Evaluate unique observed normalized drifts from most to least permissive and select the first satisfying every overall, structure-family, clustered-risk and incremental-comparator rule.",
        "rules": RULES,
        "candidate_thresholds": len(candidates),
        "evaluated_candidates": len(evaluations),
        "selected": selected,
        "evaluations": evaluations,
        "scope": {
            "structures": list(SOURCES),
            "reference_fields": sum(item["fields"] for item in source_receipts),
            "paired_acquisitions": sum(item["pairs"] for item in source_receipts),
            "endpoint_rows": len(base_rows),
            "f_actin_image_members_decoded": 0,
            "f_actin_endpoint_outcomes_computed": 0,
        },
        "sources": source_receipts,
        "lineage": {
            "base_development": {
                "path": str(DEVELOPMENT.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(DEVELOPMENT),
            },
            "base_rows_sha256": sha256_file(BASE_ROWS),
            "implementation_sha256": sha256_file(Path(__file__)),
        },
        "checkpoints": sorted(
            checkpoints, key=lambda item: (item["structure"], item["cell_id"])
        ),
        "artifacts": {
            "resolution_margin_rows": {
                "path": str(drift_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": drift_path.stat().st_size,
                "sha256": sha256_file(drift_path),
            }
        },
        "claim_boundary": "Development calibration only; not confirmation or evidence about F-actin.",
    }
    output_path = OUTPUT / "resolution_margin_calibration.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
                "status": payload["status"],
                "selected_threshold": (
                    None
                    if selected is None
                    else selected["threshold_fraction_of_endpoint_tolerance"]
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
