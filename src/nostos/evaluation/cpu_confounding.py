from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.linear_model import LinearRegression


OUTCOMES = ("mean_total_plm", "mean_total_oarsi", "mean_total_hhgs")
FEATURES = ("angular_entropy_median", "anisotropy_median")


def _average_sites(medial: pd.DataFrame, lateral: pd.DataFrame) -> pd.DataFrame:
    columns = [*FEATURES, "cartilage_fraction", "bone_fraction", "analyzed_tiles"]
    paired = medial[["participant_id", *columns]].merge(
        lateral[["participant_id", *columns]], on="participant_id", suffixes=("_medial", "_lateral"), validate="one_to_one"
    )
    result = paired[["participant_id"]].copy()
    for column in columns:
        result[column] = paired[[f"{column}_medial", f"{column}_lateral"]].mean(axis=1)
    return result


def partial_rank_correlation(x: np.ndarray, y: np.ndarray, covariates: np.ndarray) -> float:
    ranked_x, ranked_y = rankdata(x), rankdata(y)
    ranked_covariates = np.column_stack([rankdata(covariates[:, index]) for index in range(covariates.shape[1])])
    residual_x = ranked_x - LinearRegression().fit(ranked_covariates, ranked_x).predict(ranked_covariates)
    residual_y = ranked_y - LinearRegression().fit(ranked_covariates, ranked_y).predict(ranked_covariates)
    return float(spearmanr(residual_x, residual_y).statistic)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap covariate-adjusted SafO FFT associations")
    parser.add_argument("medial", type=Path)
    parser.add_argument("lateral", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=5000)
    args = parser.parse_args()
    medial = pd.read_csv(args.medial, dtype={"participant_id": str})
    lateral = pd.read_csv(args.lateral, dtype={"participant_id": str})
    metadata = pd.read_csv(args.metadata, dtype={"participant_id": str})
    for frame in (medial, lateral, metadata):
        frame["participant_id"] = frame["participant_id"].str.zfill(3)
    data = _average_sites(medial, lateral).merge(metadata, on="participant_id", validate="one_to_one")
    encoded = pd.get_dummies(data[["sex", "surgery_side"]], drop_first=True, dtype=float)
    covariates = np.column_stack([
        data["age"].to_numpy(float), encoded.to_numpy(float), data[["cartilage_fraction", "bone_fraction", "analyzed_tiles"]].to_numpy(float)
    ])
    rng = np.random.default_rng(240826)
    rows = []
    for feature in FEATURES:
        for outcome in OUTCOMES:
            x, y = data[feature].to_numpy(float), data[outcome].to_numpy(float)
            estimate = partial_rank_correlation(x, y, covariates)
            bootstrap = []
            for _ in range(args.bootstrap):
                index = rng.integers(0, len(data), len(data))
                bootstrap.append(partial_rank_correlation(x[index], y[index], covariates[index]))
            lower, upper = np.quantile(bootstrap, [.025, .975])
            unadjusted = spearmanr(x, y)
            rows.append({
                "feature": feature, "outcome": outcome, "n": len(data),
                "unadjusted_rho": unadjusted.statistic, "unadjusted_p": unadjusted.pvalue,
                "adjusted_partial_rho": estimate, "bootstrap_ci_lower": lower, "bootstrap_ci_upper": upper,
                "covariates": "age;sex;surgery_side;cartilage_fraction;bone_fraction;analyzed_tiles",
            })
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    report = {"participants": len(data), "associations": len(frame), "bootstrap_repeats": args.bootstrap, "cis_excluding_zero": int(((frame.bootstrap_ci_lower > 0) | (frame.bootstrap_ci_upper < 0)).sum())}
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
