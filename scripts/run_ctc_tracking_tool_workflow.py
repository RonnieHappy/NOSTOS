"""Run the frozen public HeLa continuation-tracking application workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from nostos.app.measure import track_series_files


def directory_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.tif")):
        digest.update(path.name.encode()); digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--masks", type=Path, required=True); parser.add_argument("--work", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    started = time.perf_counter(); summary = track_series_files(args.masks, args.work, spacing="1.6", spatial_unit="um", temporal_spacing=10, temporal_unit="min")
    runtime = time.perf_counter() - started; result = json.loads((args.work / "tracking.json").read_text(encoding="utf-8"))
    finite = all(all(np.isfinite(edge[key]) for key in ("displacement_y", "displacement_x", "speed", "cost", "confidence")) for edge in result["edges"])
    gates = {"all_frames": summary["frames"] == 92, "valid": summary["status"] == "valid", "edge_count": summary["edges"] >= 8000,
             "finite": finite, "calibration": result["calibration"] == {"spacing": [1.6, 1.6], "spatial_unit": "um", "temporal_spacing": 10, "temporal_unit": "min"},
             "scope": result["scope"]["division_tracking"] == "not_requested", "provenance": len(result["source"]["mask_files"]) == 92, "runtime": runtime < 120}
    payload = {"protocol_version": "nostos0-ctc-tracking-tool-workflow/1.0", "status": "pass" if all(gates.values()) else "fail",
               "mask_directory_sha256": directory_hash(args.masks), "runtime_seconds": runtime, "summary": summary, "gates": gates,
               "interpretation": "Author-operated application workflow on opened public data; not independent usability or new scientific confirmation."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "ctc_tracking_tool_workflow.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2)); raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__": main()
