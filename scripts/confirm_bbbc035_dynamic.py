"""Execute the frozen BBBC035 public-content dynamic confirmation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import shift
from skimage.registration import phase_cross_correlation

from nostos.features.dynamic import analyze_time_series


PROTOCOL = "nostos-bbbc035-dynamic-confirmation/1.0"
ARCHIVE_SHA256 = "0a3dac2b367814df8a3223d474de758d535f5bef0bb368ec87cf783e74064cef"
FRAME_SHA256 = "dc13c97d5273277dd5b05696dba0ffaa0ec635a685f50ea55d5660bf07409370"


def run(frame_path: Path, output: Path) -> dict:
    import skimage

    volume = tifffile.imread(frame_path)
    projection = np.asarray(volume, dtype=float).max(axis=0)
    calibration = 0.1267
    rng = np.random.default_rng(35035)
    truths = [(3, -5), (-7, 4), (10, 8), (-4, -9)]
    cases = []
    generated_hash = hashlib.sha256()
    nostos_errors, comparator_errors = [], []
    for index, truth in enumerate(truths):
        moving = shift(projection, truth, order=0, mode="wrap")
        moving += rng.normal(0, 0.01 * float(projection.std()), projection.shape)
        series = np.stack([projection, moving])
        generated_hash.update(np.ascontiguousarray(series).tobytes())
        result = analyze_time_series(series, spacing=(calibration, calibration), temporal_spacing=29.0, temporal_unit="min")
        responses = {item.measurement: item.values[0] for item in result.responses}
        estimate_pixels = np.asarray([responses["displacement_y"], responses["displacement_x"]]) / calibration
        comparator_alignment, comparator_error, _ = phase_cross_correlation(projection, moving, upsample_factor=1)
        comparator_displacement = -np.asarray(comparator_alignment)
        nostos_error = float(np.linalg.norm(estimate_pixels - np.asarray(truth)))
        upstream_error = float(np.linalg.norm(comparator_displacement - np.asarray(truth)))
        nostos_errors.append(nostos_error)
        comparator_errors.append(upstream_error)
        cases.append({
            "case": index, "truth_pixels": list(truth), "nostos_pixels": estimate_pixels.tolist(),
            "comparator_pixels": comparator_displacement.tolist(), "nostos_error_pixels": nostos_error,
            "comparator_error_pixels": upstream_error, "nostos_status": result.status,
            "physical_displacement_um": [responses["displacement_y"], responses["displacement_x"]],
        })
    blank = analyze_time_series(np.ones((2, 32, 32)), spacing=(calibration, calibration), temporal_spacing=29.0, temporal_unit="min")
    gates = {
        "provenance_complete": hashlib.sha256(frame_path.read_bytes()).hexdigest() == FRAME_SHA256 and skimage.__version__ == "0.25.2",
        "every_nostos_error_at_most_one_pixel": max(nostos_errors) <= 1.0,
        "nostos_median_no_worse_than_comparator_plus_0_25": float(np.median(nostos_errors)) <= float(np.median(comparator_errors)) + 0.25,
        "physical_and_temporal_calibration_retained": all(case["nostos_status"] == "valid" for case in cases),
        "constant_series_abstains": blank.status == "abstain",
        "all_four_cases_retained": len(cases) == 4,
    }
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "source": {"dataset": "BBBC035v1", "archive_sha256": ARCHIVE_SHA256, "frame_sha256": FRAME_SHA256, "license": "CC BY 3.0", "url": "https://bbbc.broadinstitute.org/BBBC035"},
        "generated_series_sha256": generated_hash.hexdigest(),
        "comparator": {"implementation": "skimage.registration.phase_cross_correlation", "version": skimage.__version__, "upsample_factor": 1},
        "summary": {"maximum_nostos_error_pixels": max(nostos_errors), "median_nostos_error_pixels": float(np.median(nostos_errors)), "median_comparator_error_pixels": float(np.median(comparator_errors))},
        "gates": gates, "cases": cases,
        "interpretation": "Public-content bulk-registration confirmation; not dense flow, cell tracking or native biological motion validation.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "bbbc035_dynamic_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.frame.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
