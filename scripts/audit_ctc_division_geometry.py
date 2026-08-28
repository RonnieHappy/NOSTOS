"""Outcome-aware division geometry audit on the opened SIM+ development sequence."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from develop_ctc_tracking import load_stack, parse_tracks


def object_stats(mask: np.ndarray, identity: int) -> tuple[np.ndarray, int, float] | None:
    coords = np.argwhere(mask == identity)
    if not len(coords): return None
    area = len(coords); return coords.mean(axis=0), area, float(np.sqrt(area / np.pi))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, required=True); parser.add_argument("--sequence", default="01"); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    masks = load_stack(args.root / f"{args.sequence}_GT/SEG", "man_seg*.tif"); tracks = parse_tracks(args.root / f"{args.sequence}_GT/TRA/man_track.txt")
    children: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for identity, (start, _, parent) in tracks.items():
        if parent: children[parent].append((identity, start))
    rows = []
    for parent, daughters in children.items():
        if len(daughters) != 2 or daughters[0][1] != daughters[1][1]: continue
        frame = daughters[0][1] - 1
        if frame < 0 or frame + 1 >= len(masks): continue
        parent_stats = object_stats(masks[frame], parent); child_stats = [object_stats(masks[frame + 1], item[0]) for item in daughters]
        if parent_stats is None or any(item is None for item in child_stats): continue
        pc, pa, pr = parent_stats; c1, c2 = child_stats  # type: ignore[misc]
        rows.append({"parent": parent, "frame": frame,
                     "combined_area_ratio": (c1[1] + c2[1]) / pa,
                     "maximum_child_area_ratio": max(c1[1], c2[1]) / pa,
                     "minimum_child_area_ratio": min(c1[1], c2[1]) / pa,
                     "child_area_balance": max(c1[1], c2[1]) / min(c1[1], c2[1]),
                     "maximum_distance_radii": max(np.linalg.norm(c1[0] - pc), np.linalg.norm(c2[0] - pc)) / pr,
                     "separation_radii": np.linalg.norm(c1[0] - c2[0]) / pr})
    keys = [key for key in rows[0] if key not in {"parent", "frame"}]
    summary = {key: {"min": float(np.min([r[key] for r in rows])), "q05": float(np.quantile([r[key] for r in rows], .05)),
                     "median": float(np.median([r[key] for r in rows])), "q95": float(np.quantile([r[key] for r in rows], .95)),
                     "max": float(np.max([r[key] for r in rows]))} for key in keys}
    payload = {"protocol_version": "nostos0-ctc-division-geometry-audit/1.0", "status": "development_complete",
               "dataset": f"Fluo-N2DH-SIM+ sequence {args.sequence} only", "division_count": len(rows), "summary": summary, "divisions": rows,
               "interpretation": "Outcome-aware post-failure development; no confirmation sequence opened."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "ctc_division_geometry.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"division_count": len(rows), "summary": summary}, indent=2))


if __name__ == "__main__": main()
