"""Test stronger resolution-margin probes on a small disclosed v7 diagnostic panel."""

from __future__ import annotations

import json
import zipfile
from collections import defaultdict
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


ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "outputs/nostos0-biosr-v7-tensor-distribution-development/tensor_cases.jsonl"
OUTPUT = ROOT / "outputs/nostos0-biosr-v7-resolution-margin-diagnostic"
SCALES = (0.2504, 0.3756, 0.5008, 0.7512, 1.0016)
SOURCES = {
    "CCPs": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\CCPs.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-ccp-threshold-calibration-v5/pair_index.json",
        "fields": {"Cell_006", "Cell_028", "Cell_002", "Cell_004"},
    },
    "ER": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\ER.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-er-threshold-calibration-v5/pair_index.json",
        "fields": {
            "Cell_015",
            "Cell_049",
            "Cell_051",
            "Cell_054",
            "Cell_058",
            "Cell_001",
            "Cell_005",
        },
    },
}
PROBES = (1.0, 1.5, 2.0)


def _response(image: np.ndarray, spacing: float):
    return physical_structure_tensor_response(
        image,
        spacing_um=(spacing, spacing),
        scales_um=SCALES,
        derivative_scale_fraction=0.5,
        integration_scale_factor=1.0,
    )


def main() -> None:
    outcome = {
        row["case_id"]: row
        for row in (
            json.loads(line)
            for line in ROWS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    results: list[dict[str, Any]] = []
    source_receipts = []
    for structure, source in SOURCES.items():
        index = json.loads(source["pair_index"].read_text(encoding="utf-8"))
        records = [
            BioSRPairRecord(**item)
            for item in index["records"]
            if item["cell_id"] in source["fields"]
        ]
        grouped: dict[str, list[BioSRPairRecord]] = defaultdict(list)
        for record in records:
            grouped[record.cell_id].append(record)
        with zipfile.ZipFile(source["archive"]) as opened:
            for cell, cell_records in sorted(grouped.items()):
                for record in cell_records:
                    raw = read_mrc_bytes(opened.read(record.input_member))
                    image = _robust_unit(np.mean(raw.astype(np.float64), axis=0))
                    base = _response(image, record.input_grid_spacing_um)
                    for sigma_effective in PROBES:
                        sigma_grid = (
                            sigma_effective
                            * record.effective_input_spacing_um
                            / record.input_grid_spacing_um
                        )
                        probe = _response(
                            ndimage.gaussian_filter(
                                image, sigma=sigma_grid, mode="reflect"
                            ),
                            record.input_grid_spacing_um,
                        )
                        for index_scale, scale in enumerate(SCALES):
                            orientation_case = (
                                f"{record.pair_id}|tensor_orientation_distribution|{scale}"
                            )
                            coherence_case = (
                                f"{record.pair_id}|tensor_coherence|{scale}"
                            )
                            for endpoint, case_id, drift in (
                                (
                                    "tensor_orientation_distribution",
                                    orientation_case,
                                    axial_circular_wasserstein_degrees(
                                        base.orientation_histograms[index_scale],
                                        probe.orientation_histograms[index_scale],
                                    ),
                                ),
                                (
                                    "tensor_coherence",
                                    coherence_case,
                                    abs(
                                        base.coherency[index_scale]
                                        - probe.coherency[index_scale]
                                    ),
                                ),
                            ):
                                truth = outcome[case_id]
                                if not (
                                    truth["pair_registration_eligible"]
                                    and truth["reference_eligible"]
                                ):
                                    continue
                                results.append(
                                    {
                                        "structure": structure,
                                        "cell_id": cell,
                                        "pair_id": record.pair_id,
                                        "signal_level": record.signal_level,
                                        "scale_um": scale,
                                        "endpoint": endpoint,
                                        "case_id": case_id,
                                        "sigma_effective_input_pixels": sigma_effective,
                                        "resolution_margin_drift": drift,
                                        "error": truth["error"],
                                        "invalid": truth["invalid"],
                                    }
                                )
        source_receipts.append(
            {
                "structure": structure,
                "fields": sorted(source["fields"]),
                "pair_index_sha256": sha256_file(source["pair_index"]),
            }
        )
    summaries = []
    for endpoint in sorted({row["endpoint"] for row in results}):
        for sigma in PROBES:
            subset = [
                row
                for row in results
                if row["endpoint"] == endpoint
                and row["sigma_effective_input_pixels"] == sigma
            ]
            classes = {}
            for invalid in (False, True):
                values = np.asarray(
                    [
                        row["resolution_margin_drift"]
                        for row in subset
                        if row["invalid"] is invalid
                    ],
                    dtype=float,
                )
                classes["invalid" if invalid else "valid"] = {
                    "n": len(values),
                    "median": float(np.median(values)) if len(values) else None,
                    "q75": float(np.quantile(values, 0.75)) if len(values) else None,
                    "q90": float(np.quantile(values, 0.90)) if len(values) else None,
                    "maximum": float(np.max(values)) if len(values) else None,
                }
            summaries.append(
                {
                    "endpoint": endpoint,
                    "sigma_effective_input_pixels": sigma,
                    "classes": classes,
                }
            )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows_path = OUTPUT / "resolution_margin_rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in results:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload = {
        "schema_version": "nostos-biosr-v7-resolution-margin-diagnostic/1.0",
        "status": "small_outcome_informed_diagnostic_only",
        "scope": source_receipts,
        "probe_candidates_sigma_effective_input_pixels": list(PROBES),
        "summaries": summaries,
        "selection_status": "no_probe_selected",
        "lineage": {
            "tensor_rows_sha256": sha256_file(ROWS),
            "implementation_sha256": sha256_file(Path(__file__)),
        },
        "artifacts": {
            "rows": {
                "path": str(rows_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": rows_path.stat().st_size,
                "sha256": sha256_file(rows_path),
            }
        },
        "f_actin_image_members_decoded": 0,
        "claim_boundary": "Outcome-informed development diagnostic on eleven disclosed fields; not threshold calibration or confirmation.",
    }
    output_path = OUTPUT / "resolution_margin_diagnostic.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
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
