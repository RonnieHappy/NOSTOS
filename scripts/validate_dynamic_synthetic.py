"""Run the frozen NOSTOS bulk-translation truth test."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, shift

from nostos.features.dynamic import analyze_time_series


PROTOCOL = "nostos-dynamic-synthetic/1.0"


def run(output: Path) -> dict:
    rng = np.random.default_rng(20260827)
    base = gaussian_filter(rng.normal(size=(96, 96)), 2.0)
    truth_pixels = [(3, -5), (-7, 4), (10, 8), (-4, -9)]
    cases = []
    errors = []
    for index, truth in enumerate(truth_pixels):
        moving = shift(base, truth, order=0, mode="wrap") + rng.normal(0, 0.005, base.shape)
        result = analyze_time_series(np.stack([base, moving]), spacing=(2.0, 3.0), temporal_spacing=0.5)
        responses = {item.measurement: item.values[0] for item in result.responses}
        estimate = [responses["displacement_y"], responses["displacement_x"]]
        expected = [truth[0] * 2.0, truth[1] * 3.0]
        error = float(np.linalg.norm(np.asarray(estimate) - np.asarray(expected)))
        errors.append(error)
        cases.append({"case": index, "truth_physical": expected, "estimate_physical": estimate, "error": error, "status": result.status})
    blank = analyze_time_series(np.ones((2, 32, 32)), spacing=(1.0, 1.0), temporal_spacing=1.0)
    gates = {
        "all_translation_errors_at_most_one_physical_pixel": bool(max(errors) <= 3.0),
        "blank_series_abstains": blank.status == "abstain",
        "calibration_retained": all(case["estimate_physical"] == case["truth_physical"] for case in cases),
    }
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "scope": "synthetic_bulk_translation_only",
        "cases": cases,
        "summary": {"case_count": len(cases), "maximum_error": max(errors), "median_error": float(np.median(errors))},
        "gates": gates,
        "limitations": ["integer phase correlation", "bulk translation is not dense flow or object tracking", "public biological validation pending"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dynamic_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve()), indent=2))
