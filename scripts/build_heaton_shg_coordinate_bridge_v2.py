"""Compile a post-failure SHG coordinate bridge from all opened Heaton fields."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from nostos.validation.shg_coordinate_bridge import leave_one_mouse_out_models


PAIRING = {
    "axial_resultant": "coefficient_of_alignment",
    "foreground_occupancy": "detected_pixel_fraction",
    "median_segment_straightness": "median_straightness",
    "median_segment_length_um": "median_length_um",
    "median_local_width_um": "median_width_um",
}
ERROR_RULES = {
    "axial_resultant": ("absolute", 0.15),
    "foreground_occupancy": ("relative", 0.25),
    "median_segment_straightness": ("absolute", 0.10),
    "median_segment_length_um": ("relative", 0.30),
    "median_local_width_um": ("relative", 0.30),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def compile_bridge(development_path: Path, confirmation_path: Path, output: Path) -> dict[str, Any]:
    exp10 = read_jsonl(development_path)
    exp15 = read_jsonl(confirmation_path)
    rows = []
    for experiment, source in (("Exp10", exp10), ("Exp15", exp15)):
        for row in source:
            clone = {"experiment": experiment, "mouse": f"{experiment}|{row['mouse']}"}
            for endpoint, comparator in PAIRING.items():
                clone[endpoint] = float(row["nostos"][endpoint])
                clone[comparator] = float(row["comparator"][comparator])
            rows.append(clone)
    endpoints: dict[str, Any] = {}
    for endpoint, comparator in PAIRING.items():
        reference = np.asarray([float(row[comparator]) for row in rows], dtype=float)
        floor = float(max(np.percentile(np.abs(reference), 5.0), np.finfo(float).eps))
        mode, tolerance = ERROR_RULES[endpoint]
        compiled = leave_one_mouse_out_models(
            rows,
            observed_key=endpoint,
            reference_key=comparator,
            mode=mode,
            tolerance=tolerance,
            denominator_floor=floor,
        )
        split_correlations = {}
        for experiment, source in (("Exp10", exp10), ("Exp15", exp15)):
            x = [float(row["nostos"][endpoint]) for row in source]
            y = [float(row["comparator"][comparator]) for row in source]
            split_correlations[experiment] = float(spearmanr(x, y).statistic)
        rank_supported = all(value >= 0.50 for value in split_correlations.values())
        mapping_supported = compiled["selected_model"] is not None
        enabled = bool(rank_supported and mapping_supported)
        endpoints[endpoint] = {
            **compiled,
            "comparator_endpoint": comparator,
            "error_mode": mode,
            "tolerance": tolerance,
            "denominator_floor": floor,
            "split_spearman_rho": split_correlations,
            "enabled_for_external_confirmation": enabled,
            "disabled_reason": (
                None
                if enabled
                else (
                    "no finite non-collapsed coordinate bridge"
                    if not mapping_supported
                    else "rank transfer below 0.50 in at least one opened acquisition experiment"
                )
            ),
        }
    payload = {
        "schema_version": "nostos.heaton_shg_coordinate_bridge_development.v2",
        "status": "post_failure_development_only_external_confirmation_required",
        "sources": {
            "exp10_clean_rows": {
                "path": "outputs/nostos0-heaton-in-vivo-shg-v1-risk-development/development_clean_rows.jsonl",
                "sha256": sha256_file(development_path),
                "fields": len(exp10),
            },
            "exp15_clean_rows": {
                "path": "outputs/nostos0-heaton-in-vivo-shg-v1-confirmation/confirmation_clean_rows.jsonl",
                "sha256": sha256_file(confirmation_path),
                "fields": len(exp15),
                "original_role": "opened failed v1 confirmation; development-only for v2",
            },
        },
        "independent_mice": len({row["mouse"] for row in rows}),
        "fields": len(rows),
        "selection_rule": (
            "Among identity, robust affine and robust log-affine bridges, select the finite non-collapsed "
            "candidate with lowest leave-one-mouse-out median tolerance-normalized error, then p90 error, "
            "then the declared model order. Enable an endpoint only when Spearman rho is at least 0.50 "
            "separately in Exp10 and Exp15."
        ),
        "endpoints": endpoints,
        "claim_boundary": (
            "Post-failure coordinate development on 79 already-open Heaton fields. No repaired transfer claim; "
            "the selected bridge and endpoint enablement require a new untouched acquisition family."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compile_bridge(args.development.resolve(), args.confirmation.resolve(), args.output.resolve())
    print(json.dumps({
        "status": result["status"],
        "enabled": [name for name, item in result["endpoints"].items() if item["enabled_for_external_confirmation"]],
        "disabled": [name for name, item in result["endpoints"].items() if not item["enabled_for_external_confirmation"]],
    }, indent=2))


if __name__ == "__main__":
    main()
