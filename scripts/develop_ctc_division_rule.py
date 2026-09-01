"""Post-failure division-rule development on opened SIM+ sequence 01."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from nostos.features.tracking import track_instance_series
from develop_ctc_tracking import load_stack, local_reference_maps, metrics, parse_tracks, reference_edges


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, required=True); parser.add_argument("--sequence", default="01"); parser.add_argument("--expanded", action="store_true"); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    masks = load_stack(args.root / f"{args.sequence}_GT/SEG", "man_seg*.tif"); reference = load_stack(args.root / f"{args.sequence}_GT/TRA", "man_track*.tif")
    tracks = parse_tracks(args.root / f"{args.sequence}_GT/TRA/man_track.txt"); mappings, coverage = local_reference_maps(masks, reference); truth, divisions = reference_edges(tracks, len(masks))
    candidates = []
    grid = itertools.product((0.4, 0.5), (1.5, 2.0), (0.05, 0.1), (0.85, 1.3), (5.0, 8.0), (2.0,), (3.0,)) if args.expanded else itertools.product((0.6,), (1.5, 2.2), (0.15,), (0.85, 1.2), (3.0, 5.0), (2.0, 3.0), (3.0, 4.0))
    for combined_low, combined_high, child_low, child_high, balance, distance, separation in grid:
        params = {"division_combined_area_range": (combined_low, combined_high), "division_child_area_range": (child_low, child_high),
                  "division_balance_max": balance, "division_distance_radii": distance, "division_separation_radii": separation}
        result = track_instance_series(masks, spacing=(0.125, 0.125), temporal_spacing=29.0, weights=(1, 0, 0), use_flow=False, allow_divisions=True, division_parameters=params)
        candidates.append({"parameters": {key: list(value) if isinstance(value, tuple) else value for key, value in params.items()}, **metrics(result, mappings, truth, divisions)})
    selected = max(candidates, key=lambda item: (item["divisions"]["f1"], item["links"]["f1"], -item["incorrect_links"]))
    payload = {"protocol_version": "nostos0-ctc-division-rule-development/1.0", "status": "development_complete",
               "opened_cohort": f"Fluo-N2DH-SIM+ sequence {args.sequence}", "mapping_coverage": coverage, "candidate_count": len(candidates),
               "selection_rule": "maximum division F1, then link F1, then fewer incorrect links", "selected": selected, "candidates": candidates,
               "interpretation": "Post-failure development only; SIM+ sequence 02 and both HeLa sequences remained unopened."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "ctc_division_rule_development.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "candidate_count": len(candidates)}, indent=2))


if __name__ == "__main__": main()
