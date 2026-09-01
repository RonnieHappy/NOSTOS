"""Untouched public-content confirmation of frozen dense-deformation endpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import map_coordinates
from skimage.registration import optical_flow_ilk

from nostos.features.dynamic import dense_deformation_pair


FRAME_SHA256 = "dc13c97d5273277dd5b05696dba0ffaa0ec635a685f50ea55d5660bf07409370"
PLANES = (0, 8, 17, 25, 33, 41, 50, 58)


def field(shape: tuple[int, int], seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    yn = (yy - (shape[0] - 1) / 2) / ((shape[0] - 1) / 2)
    xn = (xx - (shape[1] - 1) / 2) / ((shape[1] - 1) / 2)
    phase = rng.uniform(0, 2 * np.pi, 2)
    dy = 2.3 * np.sin(2 * np.pi * xn + phase[0]) + 0.8 * yn
    dx = 2.3 * np.cos(2 * np.pi * yn + phase[1]) - 0.8 * xn
    flow = np.stack((dy, dx)); maximum = float(np.max(np.hypot(dy, dx)))
    return flow * min(1.0, 4.0 / maximum)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--frame", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    source_hash = hashlib.sha256(args.frame.read_bytes()).hexdigest()
    volume = np.asarray(tifffile.imread(args.frame), dtype=float)
    cases = []
    for plane, seed in zip(PLANES, range(9100, 9108), strict=True):
        rng = np.random.default_rng(seed + 10000); first = volume[plane]; truth = field(first.shape, seed)
        yy, xx = np.mgrid[: first.shape[0], : first.shape[1]]
        second = map_coordinates(first, (yy - truth[0], xx - truth[1]), order=3, mode="reflect")
        sigma = 0.01 * float(np.percentile(first, 99) - np.percentile(first, 1))
        first_noisy = first + rng.normal(0, sigma, first.shape); second += rng.normal(0, sigma, first.shape)
        result = dense_deformation_pair(first_noisy, second); flow = result["flow_pixels"]
        comparator = np.asarray(optical_flow_ilk(first_noisy, second, radius=7, num_warp=10, gaussian=True, prefilter=True), dtype=float)
        interior = (yy >= 10) & (yy < first.shape[0] - 10) & (xx >= 10) & (xx < first.shape[1] - 10)
        support = interior & result["eligible"]
        error = np.hypot(flow[0] - truth[0], flow[1] - truth[1])[support]
        comparator_error = np.hypot(comparator[0] - truth[0], comparator[1] - truth[1])[support]
        bound = result["uncertainty_upper_bound_pixels"][support]
        cases.append({
            "plane": plane, "seed": seed, "source_plane_sha256": hashlib.sha256(np.ascontiguousarray(volume[plane]).tobytes()).hexdigest(),
            "median_endpoint_error_pixels": float(np.median(error)), "p95_endpoint_error_pixels": float(np.percentile(error, 95)),
            "uncertainty_coverage": float(np.mean(error <= bound)), "median_uncertainty_bound_pixels": float(np.median(bound)),
            "eligible_fraction": float(np.mean(result["eligible"][interior])),
            "comparator_median_endpoint_error_pixels": float(np.median(comparator_error)),
            "finite": bool(np.isfinite(flow).all() and np.isfinite(bound).all()),
        })
    med = lambda key: float(np.median([case[key] for case in cases]))
    summary = {"case_count": len(cases), "median_endpoint_error_pixels": med("median_endpoint_error_pixels"),
               "median_case_p95_endpoint_error_pixels": med("p95_endpoint_error_pixels"),
               "median_uncertainty_coverage": med("uncertainty_coverage"),
               "median_uncertainty_bound_pixels": med("median_uncertainty_bound_pixels"),
               "median_eligible_fraction": med("eligible_fraction"),
               "comparator_median_endpoint_error_pixels": med("comparator_median_endpoint_error_pixels")}
    gates = {
        "provenance_and_all_cases": source_hash == FRAME_SHA256 and len(cases) == 8,
        "median_endpoint_error": summary["median_endpoint_error_pixels"] <= 1.25,
        "p95_endpoint_error": summary["median_case_p95_endpoint_error_pixels"] <= 3.0,
        "eligible_fraction": summary["median_eligible_fraction"] >= 0.60,
        "uncertainty_coverage_and_efficiency": summary["median_uncertainty_coverage"] >= 0.90 and summary["median_uncertainty_bound_pixels"] <= 1.75,
        "comparator_noninferiority": summary["median_endpoint_error_pixels"] <= 1.25 * summary["comparator_median_endpoint_error_pixels"],
        "finite_and_calibratable": all(case["finite"] for case in cases),
    }
    payload = {"protocol_version": "nostos0-bbbc035-dense-deformation-confirmation/1.0",
               "status": "pass" if all(gates.values()) else "fail",
               "source": {"dataset": "BBBC035v1", "frame_sha256": source_hash, "url": "https://bbbc.broadinstitute.org/BBBC035", "license": "CC BY 3.0"},
               "planes": list(PLANES), "summary": summary, "gates": gates, "cases": cases,
               "interpretation": "Public microscopy content under programmed smooth warps; not native motion, tracking, strain or mechanics."}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "bbbc035_dense_deformation_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], **summary, "gates_passed": sum(gates.values()), "gates_total": len(gates)}, indent=2))
    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__": main()
