"""Confirm frozen object tracking on SIM+ sequence 02 and real HeLa sequence 01."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from nostos.features.tracking import track_instance_series
from develop_ctc_tracking import load_stack, local_reference_maps, metrics, parse_tracks, reference_edges


PARAMETERS = {"division_combined_area_range": (0.6, 1.5), "division_child_area_range": (0.15, 0.85),
              "division_balance_max": 3.0, "division_distance_radii": 2.0, "division_separation_radii": 3.0}


def run_dataset(root: Path, sequence: str, mask_relative: str, spacing: float, temporal: float, parameters: dict = PARAMETERS) -> dict:
    started = time.perf_counter(); masks = load_stack(root / mask_relative, "*.tif"); reference = load_stack(root / f"{sequence}_GT/TRA", "man_track*.tif")
    tracks = parse_tracks(root / f"{sequence}_GT/TRA/man_track.txt"); mappings, coverage = local_reference_maps(masks, reference); truth, divisions = reference_edges(tracks, len(masks))
    result = track_instance_series(masks, spacing=(spacing, spacing), temporal_spacing=temporal, weights=(1, 0, 0), use_flow=False, allow_divisions=True, division_parameters=parameters)
    baseline = track_instance_series(masks, spacing=(spacing, spacing), temporal_spacing=temporal, weights=(1, 0, 0), use_flow=False, allow_divisions=False)
    result_metrics = metrics(result, mappings, truth, divisions); baseline_metrics = metrics(baseline, mappings, truth, divisions)
    edges = result["edges"]; finite_fraction = float(np.mean([all(np.isfinite(edge[key]) for key in ("displacement_y", "displacement_x", "speed", "cost", "confidence")) for edge in edges])) if edges else 0.0
    four = track_instance_series(masks, spacing=(4 * spacing, 4 * spacing), temporal_spacing=temporal, weights=(1, 0, 0), use_flow=False, allow_divisions=True, division_parameters=parameters)
    assignments_equal = [(e["frame"], e["parent_local_id"], e["child_local_id"], e["edge_type"]) for e in edges] == [(e["frame"], e["parent_local_id"], e["child_local_id"], e["edge_type"]) for e in four["edges"]]
    scaling_error = max([abs(b["displacement_y"] - 4 * a["displacement_y"]) + abs(b["displacement_x"] - 4 * a["displacement_x"]) + abs(b["speed"] - 4 * a["speed"]) for a, b in zip(edges, four["edges"], strict=True)], default=0.0)
    return {"frames": len(masks), "shape": list(masks.shape[1:]), "tracks": len(tracks), "reference_edges": len(truth), "reference_division_edges": len(divisions),
            "mapping_coverage": coverage, "metrics": result_metrics, "baseline": baseline_metrics, "finite_measurement_fraction": finite_fraction,
            "assignments_invariant_to_spacing": assignments_equal, "fourfold_scaling_max_error": scaling_error, "runtime_seconds": time.perf_counter() - started,
            "mask_stack_sha256": hashlib.sha256(np.ascontiguousarray(masks).tobytes()).hexdigest(), "reference_stack_sha256": hashlib.sha256(np.ascontiguousarray(reference).tobytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--sim-root", type=Path, required=True); parser.add_argument("--hela-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    sim = run_dataset(args.sim_root, "02", "02_GT/SEG", 0.125, 29.0)
    hela = run_dataset(args.hela_root, "01", "01_ST/SEG", 1.6, 10.0)
    sim_gates = {
        "mapping_coverage": sim["mapping_coverage"] >= 0.99, "link_f1": sim["metrics"]["links"]["f1"] >= 0.95,
        "division_f1": sim["metrics"]["divisions"]["reference"] < 5 or sim["metrics"]["divisions"]["f1"] >= 0.80,
        "identity_switches": sim["metrics"]["identity_switch_fraction"] <= 0.005,
        "baseline": sim["metrics"]["links"]["f1"] >= sim["baseline"]["links"]["f1"],
        "calibration": sim["assignments_invariant_to_spacing"] and sim["fourfold_scaling_max_error"] <= 1e-9,
    }
    hela_gates = {
        "mapping_coverage": hela["mapping_coverage"] >= 0.80, "link_f1": hela["metrics"]["links"]["f1"] >= 0.80,
        "identity_switches": hela["metrics"]["identity_switch_fraction"] <= 0.05,
        "baseline": hela["metrics"]["links"]["f1"] >= hela["baseline"]["links"]["f1"] - 0.02,
        "finite_calibrated": hela["finite_measurement_fraction"] >= 0.90,
        "runtime": hela["runtime_seconds"] < 300.0,
    }
    payload = {"protocol_version": "nostos0-ctc-native-tracking-confirmation/1.0",
               "status": "pass" if all(sim_gates.values()) and all(hela_gates.values()) else "fail",
               "sources": {"sim_archive_sha256": "3e809148c87ace80c72f563b56c35e0d9448dcdeb461a09c83f61e93f5e40ec8",
                           "hela_archive_sha256": "35dd99d58e071aba0b03880128d920bd1c063783cc280f9531fbdc5be614c82e", "url": "https://celltrackingchallenge.net/2d-datasets/"},
               "method": {"weights": [1, 0, 0], "use_flow": False, "division_parameters": {key: list(value) if isinstance(value, tuple) else value for key, value in PARAMETERS.items()}},
               "sim_sequence_02": sim, "hela_sequence_01": hela, "sim_gates": sim_gates, "hela_gates": hela_gates,
               "interpretation": "Tracking imported instance masks on exact simulated and real HeLa microscopy; not automatic segmentation, hidden-test performance, mechanics or clinical utility."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "ctc_native_tracking_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "sim": sim, "hela": hela, "sim_gates": sim_gates, "hela_gates": hela_gates}, indent=2))
    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__": main()
