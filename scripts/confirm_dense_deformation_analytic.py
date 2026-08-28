"""Disjoint analytic confirmation of dense deformation and frozen uncertainty bound."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from skimage.registration import optical_flow_ilk

from nostos.features.dynamic import dense_deformation_pair
from validate_dense_deformation import FAMILIES, deform, texture, truth_field


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    cases = []
    for index, seed in enumerate(range(3000, 3036)):
        family = FAMILIES[index % len(FAMILIES)]; rng = np.random.default_rng(seed + 50000)
        first = texture(seed); truth = truth_field(family, seed + 1000); second = deform(first, truth)
        sigma = 0.01 * float(np.percentile(first, 99) - np.percentile(first, 1))
        first += rng.normal(0, sigma, first.shape); second += rng.normal(0, sigma, second.shape)
        result = dense_deformation_pair(first, second); flow = result["flow_pixels"]
        comparator = np.asarray(optical_flow_ilk(first, second, radius=7, num_warp=10, gaussian=True, prefilter=True), dtype=float)
        yy, xx = np.mgrid[:128, :128]
        support = result["eligible"] & (yy >= 10) & (yy < 118) & (xx >= 10) & (xx < 118)
        error = np.hypot(flow[0] - truth[0], flow[1] - truth[1])[support]
        bound = result["uncertainty_upper_bound_pixels"][support]
        comparator_error = np.hypot(comparator[0] - truth[0], comparator[1] - truth[1])[support]
        cases.append({
            "seed": seed, "family": family, "median_endpoint_error_pixels": float(np.median(error)),
            "p95_endpoint_error_pixels": float(np.percentile(error, 95)),
            "uncertainty_coverage": float(np.mean(error <= bound)),
            "median_uncertainty_bound_pixels": float(np.median(bound)),
            "eligible_fraction": float(np.mean(result["eligible"][(yy >= 10) & (yy < 118) & (xx >= 10) & (xx < 118)])),
            "comparator_median_endpoint_error_pixels": float(np.median(comparator_error)),
        })
    med = lambda key: float(np.median([case[key] for case in cases]))
    family_eligible = {family: float(np.median([c["eligible_fraction"] for c in cases if c["family"] == family])) for family in FAMILIES}
    summary = {
        "case_count": len(cases), "median_endpoint_error_pixels": med("median_endpoint_error_pixels"),
        "median_case_p95_endpoint_error_pixels": med("p95_endpoint_error_pixels"),
        "pooled_case_median_uncertainty_coverage": med("uncertainty_coverage"),
        "median_uncertainty_bound_pixels": med("median_uncertainty_bound_pixels"),
        "median_eligible_fraction": med("eligible_fraction"), "family_median_eligible_fraction": family_eligible,
        "comparator_median_endpoint_error_pixels": med("comparator_median_endpoint_error_pixels"),
    }
    gates = {
        "median_endpoint_error": summary["median_endpoint_error_pixels"] <= 1.0,
        "p95_endpoint_error": summary["median_case_p95_endpoint_error_pixels"] <= 2.5,
        "uncertainty_coverage": summary["pooled_case_median_uncertainty_coverage"] >= 0.90,
        "uncertainty_efficiency": summary["median_uncertainty_bound_pixels"] <= 1.50,
        "eligible_fraction": summary["median_eligible_fraction"] >= 0.70 and min(family_eligible.values()) >= 0.50,
        "comparator_noninferiority": summary["median_endpoint_error_pixels"] <= 1.25 * summary["comparator_median_endpoint_error_pixels"],
    }
    payload = {"protocol_version": "nostos0-dense-deformation-analytic-confirmation/1.0",
               "status": "pass" if all(gates.values()) else "fail", "seed_range": [3000, 3035],
               "cases": cases, "summary": summary, "gates": gates,
               "interpretation": "Disjoint analytic confirmation; not native biological motion, tracking, strain or mechanics."}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "dense_deformation_analytic_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], **summary, "gates_passed": sum(gates.values()), "gates_total": len(gates)}, indent=2))
    raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__": main()
