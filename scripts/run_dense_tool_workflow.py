"""Execute the frozen public BBBC035 dense-series file workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import map_coordinates

from nostos.app.measure import measure_series_file
from confirm_bbbc035_dense_deformation import field


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--frame", type=Path, required=True); parser.add_argument("--work", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    volume = np.asarray(tifffile.imread(args.frame), dtype=float); first = volume[33]; truth = field(first.shape, 9911)
    yy, xx = np.mgrid[: first.shape[0], : first.shape[1]]
    second = map_coordinates(first, (yy - truth[0], xx - truth[1]), order=3, mode="reflect")
    series = np.stack((first, second)); args.work.mkdir(parents=True, exist_ok=True); source = args.work / "bbbc035_dense_series.npy"; np.save(source, series)
    started = time.perf_counter()
    result = measure_series_file(source, args.work / "analysis", spacing="0.1267", spatial_unit="um", temporal_spacing=29.0, temporal_unit="min", dense=True)
    runtime = time.perf_counter() - started
    geometry = json.loads((args.work / "analysis/dynamic_response_geometry.json").read_text(encoding="utf-8"))
    responses = {item["measurement"]: item for item in geometry["responses"]}; eligible = np.asarray(responses["dense_eligible"]["values"])
    numeric = [np.asarray(item["values"], dtype=float) for item in responses.values()]
    uncertainty = [np.asarray(item["uncertainty"], dtype=float) for item in responses.values() if item["uncertainty"] is not None]
    gates = {
        "valid": result["status"] == "valid", "four_surfaces": len(responses) == 4,
        "axes_and_calibration": geometry["calibration"]["spacing"] == [0.1267, 0.1267] and all(len(item["axes"]) == 3 for item in responses.values()),
        "finite": all(np.isfinite(value).all() for value in numeric + uncertainty),
        "eligible_fraction": float(np.mean(eligible)) >= 0.60,
        "provenance": bool(hashlib.sha256(args.frame.read_bytes()).hexdigest()) and bool(hashlib.sha256(source.read_bytes()).hexdigest()),
        "runtime": runtime < 120.0,
    }
    payload = {"protocol_version": "nostos0-dense-tool-workflow/1.0", "status": "pass" if all(gates.values()) else "fail",
               "source_frame_sha256": hashlib.sha256(args.frame.read_bytes()).hexdigest(), "generated_series_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "runtime_seconds": runtime, "eligible_fraction": float(np.mean(eligible)), "response_count": len(responses), "gates": gates,
               "interpretation": "Author-operated public-data file workflow; not independent usability or native-motion validation."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "dense_tool_workflow.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2)); raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__": main()
