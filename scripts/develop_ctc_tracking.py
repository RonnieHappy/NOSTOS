"""Develop frozen NOSTOS object-linkage weights on SIM+ sequence 01 only."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import tifffile

from nostos.features.tracking import centroid_flow, extract_objects, track_instance_series


CANDIDATES = ((1.0, 0.0, 0.0), (1.0, 0.25, 0.5), (1.0, 0.35, 0.75), (1.0, 0.5, 1.0), (1.0, 0.75, 0.5))


def load_stack(directory: Path, pattern: str) -> np.ndarray:
    paths = sorted(directory.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No files match {directory / pattern}")
    return np.stack([tifffile.imread(path) for path in paths])


def parse_tracks(path: Path) -> dict[int, tuple[int, int, int]]:
    tracks = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        identity, start, end, parent = (int(value) for value in line.split())
        tracks[identity] = (start, end, parent)
    return tracks


def local_reference_maps(masks: np.ndarray, reference: np.ndarray) -> tuple[list[dict[int, int]], float]:
    mappings, mapped, total = [], 0, 0
    for frame in range(masks.shape[0]):
        objects, coords = extract_objects(masks[frame], frame); frame_map = {}
        for obj, pixels in zip(objects, coords, strict=True):
            values, counts = np.unique(reference[frame][pixels[:, 0], pixels[:, 1]], return_counts=True)
            eligible = values != 0
            if np.any(eligible):
                candidates = values[eligible]; candidate_counts = counts[eligible]
                frame_map[obj.local_id] = int(candidates[int(np.argmax(candidate_counts))]); mapped += 1
            total += 1
        mappings.append(frame_map)
    return mappings, mapped / max(total, 1)


def reference_edges(tracks: dict[int, tuple[int, int, int]], frames: int) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    edges, divisions = set(), set()
    for identity, (start, end, parent) in tracks.items():
        for frame in range(start, min(end, frames - 1)):
            edges.add((frame, identity, identity))
        if parent > 0 and start > 0 and start < frames:
            edge = (start - 1, parent, identity); edges.add(edge); divisions.add(edge)
    return edges, divisions


def metrics(result: dict, mappings: list[dict[int, int]], truth: set[tuple[int, int, int]], truth_divisions: set[tuple[int, int, int]]) -> dict:
    predicted, predicted_divisions, unmapped = set(), set(), 0
    for edge in result["edges"]:
        frame = edge["frame"]
        parent = mappings[frame].get(edge["parent_local_id"]); child = mappings[frame + 1].get(edge["child_local_id"])
        if parent is None or child is None:
            unmapped += 1; continue
        item = (frame, parent, child); predicted.add(item)
        if edge["edge_type"] == "division": predicted_divisions.add(item)
    def scores(pred: set, ref: set) -> dict:
        tp = len(pred & ref); precision = tp / len(pred) if pred else 0.0; recall = tp / len(ref) if ref else 1.0
        return {"true_positive": tp, "predicted": len(pred), "reference": len(ref), "precision": precision, "recall": recall,
                "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    edge_scores = scores(predicted, truth); division_scores = scores(predicted_divisions, truth_divisions)
    return {"links": edge_scores, "divisions": division_scores, "incorrect_links": len(predicted - truth),
            "identity_switch_fraction": len(predicted - truth) / max(len(predicted), 1), "unmapped_predicted_edges": unmapped}


def precompute(images: np.ndarray, masks: np.ndarray) -> list[np.ndarray]:
    flows = []
    for frame in range(len(images) - 1):
        objects, _ = extract_objects(masks[frame], frame)
        centroids = np.asarray([(obj.centroid_y, obj.centroid_x) for obj in objects])
        flows.append(centroid_flow(images[frame], images[frame + 1], centroids))
    return flows


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    started = time.perf_counter(); images = load_stack(args.root / "01", "t*.tif"); masks = load_stack(args.root / "01_GT/SEG", "man_seg*.tif"); reference = load_stack(args.root / "01_GT/TRA", "man_track*.tif")
    tracks = parse_tracks(args.root / "01_GT/TRA/man_track.txt"); mappings, coverage = local_reference_maps(masks, reference); truth, divisions = reference_edges(tracks, len(images)); flows = precompute(images, masks)
    candidates = []
    for weights in CANDIDATES:
        result = track_instance_series(masks, spacing=(0.125, 0.125), temporal_spacing=29.0, images=images, weights=weights, precomputed_flows=flows)
        candidate = {"weights": list(weights), **metrics(result, mappings, truth, divisions)}; candidates.append(candidate)
    selected = max(candidates, key=lambda item: (item["links"]["f1"], item["divisions"]["f1"], -item["incorrect_links"]))
    baseline_result = track_instance_series(masks, spacing=(0.125, 0.125), temporal_spacing=29.0, images=None, weights=(1, 0, 0), use_flow=False, allow_divisions=False)
    payload = {"protocol_version": "nostos0-ctc-tracking-development/1.0", "status": "development_complete",
               "source": {"archive_sha256": "3e809148c87ace80c72f563b56c35e0d9448dcdeb461a09c83f61e93f5e40ec8", "dataset": "Fluo-N2DH-SIM+", "sequence": "01"},
               "input": {"frames": len(images), "shape": list(images.shape[1:]), "tracks": len(tracks), "reference_edges": len(truth), "reference_division_edges": len(divisions), "mapping_coverage": coverage,
                         "image_stack_sha256": hashlib.sha256(np.ascontiguousarray(images).tobytes()).hexdigest(), "mask_stack_sha256": hashlib.sha256(np.ascontiguousarray(masks).tobytes()).hexdigest()},
               "candidates": candidates, "selection_rule": "maximum link F1, then division F1, then fewer incorrect links", "selected_weights": selected["weights"],
               "baseline": metrics(baseline_result, mappings, truth, divisions), "runtime_seconds": time.perf_counter() - started,
               "interpretation": "Development on SIM+ sequence 01 only; sequence 02 and HeLa remained unopened."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "ctc_tracking_development.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "coverage": coverage, "baseline": payload["baseline"], "runtime_seconds": payload["runtime_seconds"]}, indent=2))


if __name__ == "__main__": main()
