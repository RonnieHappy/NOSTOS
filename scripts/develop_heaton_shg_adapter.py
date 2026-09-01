"""Select the SHG adapter on Exp10 only and write a frozen development profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from scipy.stats import spearmanr

from nostos.validation.curvealign_outputs import parse_field_outputs
from nostos.validation.heaton_shg_transfer import adapter_grid, measure_shg_field


PAIRING = {
    "axial_resultant": "coefficient_of_alignment",
    "foreground_occupancy": "detected_pixel_fraction",
    "median_segment_straightness": "median_straightness",
    "median_segment_length_um": "median_length_um",
    "median_local_width_um": "median_width_um",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def select_per_mouse(rows: list[dict[str, Any]], *, fields_per_mouse: int, salt: str) -> list[dict[str, Any]]:
    selected = []
    for mouse in sorted({str(row["mouse"]) for row in rows}):
        candidates = [row for row in rows if str(row["mouse"]) == mouse]
        candidates.sort(
            key=lambda row: hashlib.sha256(f"{salt}|{row['source']}".encode("utf-8")).hexdigest()
        )
        if len(candidates) < fields_per_mouse:
            raise ValueError(f"Mouse {mouse} has only {len(candidates)} fields.")
        selected.extend(candidates[:fields_per_mouse])
    return selected


def _output_roots(stage: Path) -> tuple[Path, Path]:
    ca = sorted({path.parent for path in stage.rglob("*_stats.csv")})
    ct = sorted({path.parent for path in stage.rglob("HistLEN_ctFIRE_*.csv")})
    if len(ca) != 1 or len(ct) != 1:
        raise ValueError(f"Expected one CurveAlign and one CT-FIRE output folder; found {ca} and {ct}.")
    return ca[0], ct[0]


def _job(payload: tuple[str, dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    path_text, params, config = payload
    image = tifffile.imread(path_text)
    measured = measure_shg_field(
        image,
        spacing_um=tuple(float(value) for value in config["dataset"]["pixel_spacing_um"]),
        params=params,
        config=config,
        internal_checks=False,
    )
    return measured


def _correlations(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    output: dict[str, float | None] = {}
    for endpoint, comparator in PAIRING.items():
        pairs = [
            (row["nostos"][endpoint], row["comparator"][comparator])
            for row in rows
            if row["nostos"][endpoint] is not None
            and np.isfinite(row["nostos"][endpoint])
            and np.isfinite(row["comparator"][comparator])
        ]
        if len(pairs) < 4:
            output[endpoint] = None
            continue
        first, second = zip(*pairs, strict=True)
        rho = float(spearmanr(first, second).statistic)
        output[endpoint] = rho if np.isfinite(rho) else None
    return output


def _fisher_mean(correlations: dict[str, float | None]) -> float:
    values = [float(value) for value in correlations.values() if value is not None and np.isfinite(value)]
    if not values:
        return float("-inf")
    return float(np.mean(np.arctanh(np.clip(values, -0.999999, 0.999999))))


def _relative_drift(first: dict[str, float | None], second: dict[str, float | None]) -> float:
    values = []
    for endpoint in PAIRING:
        a, b = first[endpoint], second[endpoint]
        if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
            return float("inf")
        if endpoint in {"axial_resultant", "median_segment_straightness"}:
            values.append(abs(float(a) - float(b)))
        else:
            values.append(abs(float(a) - float(b)) / max(abs(float(a)), np.finfo(float).eps))
    return float(max(values))


def develop(stage: Path, config_path: Path, protocol_path: Path, output: Path, workers: int) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    receipt = json.loads((stage / "stage_receipt.json").read_text(encoding="utf-8"))
    if receipt.get("experiment") != "Exp10" or receipt.get("status") != "development_stage_parameters_locked":
        raise PermissionError("Adapter development requires the locked Exp10 stage.")
    ca_root, ct_root = _output_roots(stage)
    comparators = {
        row["field_stem"]: parse_field_outputs(
            stage,
            field_stem=row["field_stem"],
            pixel_spacing_um=float(config["dataset"]["pixel_spacing_um"][0]),
            curvealign_root=ca_root,
            ctfire_root=ct_root,
        )
        for row in receipt["rows"]
    }
    selection = config["adapter_selection"]
    selected = select_per_mouse(
        receipt["rows"],
        fields_per_mouse=int(selection["fields_per_mouse"]),
        salt="nostos-heaton-shg-adapter-v1",
    )
    candidates = adapter_grid(config)
    jobs = [
        (str(stage / row["staged_name"]), params, config)
        for params in candidates
        for row in selected
    ]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        measurements = list(executor.map(_job, jobs, chunksize=2))
    summaries = []
    cursor = 0
    candidate_rows: list[list[dict[str, Any]]] = []
    for index, params in enumerate(candidates):
        rows = []
        for source in selected:
            measured = measurements[cursor]
            cursor += 1
            rows.append(
                {
                    "mouse": source["mouse"],
                    "field_stem": source["field_stem"],
                    "nostos": measured["endpoints"],
                    "complete": measured["complete"],
                    "segment_count": measured["segment_count"],
                    "comparator": comparators[source["field_stem"]],
                }
            )
        candidate_rows.append(rows)
        complete_fraction = float(np.mean([row["complete"] for row in rows]))
        median_segments = float(np.median([row["segment_count"] for row in rows]))
        correlations = _correlations(rows)
        eligible = (
            complete_fraction >= float(selection["minimum_complete_field_fraction"])
            and median_segments >= float(selection["minimum_median_accepted_segments"])
        )
        summaries.append(
            {
                "candidate_index": index,
                "parameters": params,
                "eligible": bool(eligible),
                "complete_fraction": complete_fraction,
                "median_segment_count": median_segments,
                "correlations": correlations,
                "correlations_at_least_target": int(
                    sum(value is not None and value >= float(selection["correlation_target"]) for value in correlations.values())
                ),
                "mean_fisher_z": _fisher_mean(correlations),
                "median_threshold_drift": None,
            }
        )
    eligible = [item for item in summaries if item["eligible"]]
    if not eligible:
        raise RuntimeError("No adapter candidate met the preregistered support criteria.")
    best_primary = max(item["correlations_at_least_target"] for item in eligible)
    tied = [item for item in eligible if item["correlations_at_least_target"] == best_primary]
    best_secondary = max(item["mean_fisher_z"] for item in tied)
    tied = [item for item in tied if math.isclose(item["mean_fisher_z"], best_secondary, abs_tol=1e-12)]
    # Only exact primary/secondary ties require the computationally expensive
    # predeclared threshold-stability tie break.
    for summary in tied:
        index = int(summary["candidate_index"])
        params = dict(summary["parameters"])
        drifts = []
        for row, clean in zip(selected, candidate_rows[index], strict=True):
            image = tifffile.imread(stage / row["staged_name"])
            for delta in (-0.05, 0.05):
                neighbour = dict(params)
                neighbour["foreground_quantile"] = float(np.clip(float(params["foreground_quantile"]) + delta, 0.01, 0.99))
                measured = measure_shg_field(
                    image,
                    spacing_um=tuple(float(value) for value in config["dataset"]["pixel_spacing_um"]),
                    params=neighbour,
                    config=config,
                    internal_checks=False,
                )
                drifts.append(_relative_drift(clean["nostos"], measured["endpoints"]))
        summary["median_threshold_drift"] = float(np.median(drifts))
    def rank(item: dict[str, Any]) -> tuple[Any, ...]:
        params = item["parameters"]
        drift = item["median_threshold_drift"] if item["median_threshold_drift"] is not None else float("inf")
        return (
            -int(item["correlations_at_least_target"]),
            -float(item["mean_fisher_z"]),
            float(drift),
            float(params["background_opening_radius_um"]),
            tuple(params["ridge_scales_um"]),
            float(params["foreground_quantile"]),
            float(params["minimum_component_length_um"]),
        )
    winner = min(eligible, key=rank)
    winner_index = int(winner["candidate_index"])
    payload = {
        "schema_version": "nostos.heaton_shg_adapter_development.v1",
        "status": "development_complete_confirmation_still_sealed",
        "config_sha256": sha256_file(config_path),
        "protocol_sha256": sha256_file(protocol_path),
        "stage_receipt_sha256": sha256_file(stage / "stage_receipt.json"),
        "selected_fields": [row["field_stem"] for row in selected],
        "selected_mice": sorted({row["mouse"] for row in selected}),
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(eligible),
        "winner": winner,
        "winner_field_rows": candidate_rows[winner_index],
        "candidate_summaries": summaries,
        "claim_boundary": "Exp10 adapter development only; no Exp15 result or positive transfer claim.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    args = parser.parse_args()
    result = develop(
        args.stage.resolve(),
        args.config.resolve(),
        args.protocol.resolve(),
        args.output.resolve(),
        args.workers,
    )
    print(json.dumps({"status": result["status"], "winner": result["winner"]}, indent=2))


if __name__ == "__main__":
    main()

