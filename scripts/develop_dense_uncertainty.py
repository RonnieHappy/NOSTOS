"""Post-failure uncertainty development on the opened analytic cohort only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import map_coordinates
from scipy.stats import rankdata, spearmanr
from skimage.registration import optical_flow_ilk

from nostos.features.dynamic import _robust_normalize, dense_deformation_pair
from validate_dense_deformation import FAMILIES, deform, texture, truth_field


def ranked(values: np.ndarray) -> np.ndarray:
    return rankdata(values, method="average") / max(values.size, 1)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    all_error: list[np.ndarray] = []
    signals: dict[str, list[np.ndarray]] = {name: [] for name in (
        "forward_backward", "photometric", "estimator_disagreement",
        "fb_photometric_rank_mean", "all_rank_mean",
    )}
    for index, seed in enumerate(range(2400, 2436)):
        family = FAMILIES[index % len(FAMILIES)]
        rng = np.random.default_rng(seed + 50000)
        first = texture(seed); truth = truth_field(family, seed + 1000); second = deform(first, truth)
        sigma = 0.01 * float(np.percentile(first, 99) - np.percentile(first, 1))
        first += rng.normal(0, sigma, first.shape); second += rng.normal(0, sigma, second.shape)
        result = dense_deformation_pair(first, second); flow = result["flow_pixels"]
        ilk = np.asarray(optical_flow_ilk(first, second, radius=7, num_warp=10, gaussian=True, prefilter=True), dtype=float)
        yy, xx = np.mgrid[: first.shape[0], : first.shape[1]]
        support = result["eligible"] & (yy >= 10) & (yy < 118) & (xx >= 10) & (xx < 118)
        error = np.hypot(flow[0] - truth[0], flow[1] - truth[1])[support]
        normalized_first = _robust_normalize(first); normalized_second = _robust_normalize(second)
        warped = map_coordinates(normalized_second, (yy + flow[0], xx + flow[1]), order=1, mode="constant", cval=np.nan)
        fb = result["forward_backward_error_pixels"][support]
        photo = np.abs(normalized_first - warped)[support]
        disagreement = np.hypot(flow[0] - ilk[0], flow[1] - ilk[1])[support]
        all_error.append(error)
        signals["forward_backward"].append(fb); signals["photometric"].append(photo)
        signals["estimator_disagreement"].append(disagreement)
        signals["fb_photometric_rank_mean"].append((ranked(fb) + ranked(photo)) / 2)
        signals["all_rank_mean"].append((ranked(fb) + ranked(photo) + ranked(disagreement)) / 3)
    truth_error = np.concatenate(all_error)
    correlations = {name: float(spearmanr(np.concatenate(parts), truth_error).statistic) for name, parts in signals.items()}
    selected = max(correlations, key=correlations.get)
    selected_values = np.concatenate(signals[selected])
    conformal_offset = float(np.quantile(truth_error - selected_values, 0.95, method="higher"))
    upper_bound = np.maximum(0.0, selected_values + conformal_offset)
    payload = {
        "protocol_version": "nostos0-dense-uncertainty-development/1.0", "status": "development_complete",
        "opened_cohort": "analytic seeds 2400-2435 from failed frozen run",
        "candidate_uncertainty_error_spearman": correlations,
        "selection_rule": "highest pooled Spearman correlation on opened development pixels",
        "selected": selected,
        "conformal_calibration": {
            "target_coverage": 0.95,
            "additive_offset_pixels": conformal_offset,
            "development_coverage": float(np.mean(truth_error <= upper_bound)),
            "median_upper_bound_pixels": float(np.median(upper_bound))
        },
        "interpretation": "Post-failure development only. The selected score requires disjoint analytic and public-content confirmation.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "dense_uncertainty_development.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__": main()
