"""Execute the frozen NOSTOS-0 analytic dense-deformation protocol."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.stats import spearmanr
from skimage.registration import optical_flow_ilk

from nostos.features.dynamic import analyze_dense_deformation, dense_deformation_pair


FAMILIES = ("translation", "shear", "radial", "sinusoidal_x", "sinusoidal_y", "mixed")


def texture(seed: int, size: int = 128) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:size, :size]
    image = gaussian_filter(rng.normal(size=(size, size)), 1.4)
    for _ in range(8):
        cy, cx = rng.uniform(15, size - 15, 2)
        radius = rng.uniform(2.5, 8.0)
        image += rng.uniform(0.5, 1.5) * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * radius**2))
    image += 0.15 * np.sin(xx / 5.0 + seed) + 0.12 * np.cos(yy / 7.0 - seed)
    return image


def truth_field(family: str, seed: int, size: int = 128, maximum: float = 6.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:size, :size]
    yc, xc = (size - 1) / 2, (size - 1) / 2
    yn, xn = (yy - yc) / yc, (xx - xc) / xc
    if family == "translation":
        dy, dx = np.full_like(yn, rng.uniform(-4, 4)), np.full_like(xn, rng.uniform(-4, 4))
    elif family == "shear":
        dy, dx = 2.0 * xn, 4.0 * yn
    elif family == "radial":
        dy, dx = 3.0 * yn, 3.0 * xn
    elif family == "sinusoidal_x":
        dy, dx = np.zeros_like(yn), 4.0 * np.sin(2 * np.pi * yn)
    elif family == "sinusoidal_y":
        dy, dx = 4.0 * np.sin(2 * np.pi * xn), np.zeros_like(xn)
    else:
        dy = 2.5 * np.sin(2 * np.pi * xn) + 1.2 * yn
        dx = 2.5 * np.cos(2 * np.pi * yn) - 1.2 * xn
    magnitude = np.hypot(dy, dx)
    factor = min(1.0, maximum / max(float(magnitude.max()), np.finfo(float).eps))
    return np.stack((dy * factor, dx * factor))


def deform(image: np.ndarray, flow: np.ndarray) -> np.ndarray:
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]]
    return map_coordinates(image, (yy - flow[0], xx - flow[1]), order=3, mode="reflect")


def evaluate_case(seed: int, family: str) -> dict:
    rng = np.random.default_rng(seed + 50000)
    first = texture(seed)
    truth = truth_field(family, seed + 1000)
    second = deform(first, truth)
    sigma = 0.01 * float(np.percentile(first, 99) - np.percentile(first, 1))
    first = first + rng.normal(0, sigma, first.shape)
    second = second + rng.normal(0, sigma, second.shape)
    result = dense_deformation_pair(first, second)
    comparator = np.asarray(optical_flow_ilk(first, second, radius=7, num_warp=10, gaussian=True, prefilter=True), dtype=float)
    yy, xx = np.mgrid[: first.shape[0], : first.shape[1]]
    interior = (yy >= 10) & (yy < 118) & (xx >= 10) & (xx < 118)
    target_inside = ((yy + truth[0]) >= 0) & ((yy + truth[0]) <= 127) & ((xx + truth[1]) >= 0) & ((xx + truth[1]) <= 127)
    support = interior & target_inside
    eligible = support & result["eligible"]
    error = np.hypot(result["flow_pixels"][0] - truth[0], result["flow_pixels"][1] - truth[1])
    comparator_error = np.hypot(comparator[0] - truth[0], comparator[1] - truth[1])
    return {
        "seed": seed, "family": family,
        "median_endpoint_error_pixels": float(np.median(error[eligible])),
        "p95_endpoint_error_pixels": float(np.percentile(error[eligible], 95)),
        "comparator_median_endpoint_error_pixels": float(np.median(comparator_error[support])),
        "eligible_fraction": float(np.mean(result["eligible"][support])),
        "errors": error[eligible],
        "uncertainty": result["forward_backward_error_pixels"][eligible],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = [evaluate_case(seed, FAMILIES[index % len(FAMILIES)]) for index, seed in enumerate(range(2400, 2436))]
    errors = np.concatenate([case.pop("errors") for case in cases])
    uncertainty = np.concatenate([case.pop("uncertainty") for case in cases])
    rho = float(spearmanr(uncertainty, errors).statistic)
    median_error = float(np.median([case["median_endpoint_error_pixels"] for case in cases]))
    p95_error = float(np.median([case["p95_endpoint_error_pixels"] for case in cases]))
    comparator = float(np.median([case["comparator_median_endpoint_error_pixels"] for case in cases]))
    eligible = float(np.median([case["eligible_fraction"] for case in cases]))
    family_eligible = {family: float(np.median([c["eligible_fraction"] for c in cases if c["family"] == family])) for family in FAMILIES}

    base = texture(999, 96); moved = deform(base, np.stack((np.full((96, 96), 2.0), np.full((96, 96), -3.0))))
    one = analyze_dense_deformation(np.stack((base, moved)), spacing=(1.0, 1.0), temporal_spacing=1.0)
    four = analyze_dense_deformation(np.stack((base, moved)), spacing=(4.0, 4.0), temporal_spacing=1.0)
    one_y = np.asarray(next(r.values for r in one.responses if r.measurement == "dense_displacement_y"))
    four_y = np.asarray(next(r.values for r in four.responses if r.measurement == "dense_displacement_y"))
    calibration_ratio_error = float(np.max(np.abs(four_y - 4 * one_y)))
    blank = analyze_dense_deformation(np.ones((2, 64, 64)), spacing=(1.0, 1.0), temporal_spacing=1.0)
    sparse = np.zeros((2, 64, 64)); sparse[0, 30:34, 30:34] = 1; sparse[1, 31:35, 30:34] = 1
    sparse_result = analyze_dense_deformation(sparse, spacing=(1.0, 1.0), temporal_spacing=1.0)
    gates = {
        "median_endpoint_error": median_error <= 1.0,
        "p95_endpoint_error": p95_error <= 2.5,
        "eligible_fraction": eligible >= 0.70 and min(family_eligible.values()) >= 0.50,
        "uncertainty_error_association": rho >= 0.35,
        "comparator_noninferiority": median_error <= 1.25 * comparator,
        "physical_calibration": calibration_ratio_error <= 1e-8,
        "abstention": blank.status == "abstain" and sparse_result.status == "abstain",
    }
    payload = {
        "protocol_version": "nostos0-dense-deformation-analytic/1.0", "status": "pass" if all(gates.values()) else "fail",
        "software": {"scikit_image": "0.25.2", "nostos": "0.3.0"}, "cases": cases,
        "summary": {"case_count": len(cases), "median_endpoint_error_pixels": median_error,
                    "median_case_p95_endpoint_error_pixels": p95_error, "median_eligible_fraction": eligible,
                    "family_median_eligible_fraction": family_eligible, "uncertainty_error_spearman": rho,
                    "comparator_median_endpoint_error_pixels": comparator,
                    "calibration_ratio_max_error": calibration_ratio_error,
                    "blank_status": blank.status, "sparse_status": sparse_result.status},
        "gates": gates,
        "interpretation": "Analytic dense-deformation truth only; no object tracking, native biological motion, strain or mechanics claim.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "dense_deformation_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], **payload["summary"], "gates_passed": sum(gates.values()), "gates_total": len(gates)}, indent=2))
    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
