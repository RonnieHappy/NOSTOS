from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from nostos.modeling.grouped_ridge import grouped_nested_ridge_predictions, participant_permutation_test


OUTCOMES = ("mean_total_plm", "mean_total_oarsi", "mean_total_hhgs")
FEATURE_SETS = {
    "fft_entropy": ["angular_entropy_median"],
    "fft_multiscale": [
        "angular_entropy_median", "anisotropy_median", "spectral_slope_median",
        "characteristic_frequency_cycles_per_mm_median",
    ],
    "conventional_texture": ["tensor_coherence_median", "glcm_contrast_median", "glcm_homogeneity_median"],
    "combined": [
        "angular_entropy_median", "anisotropy_median", "spectral_slope_median",
        "characteristic_frequency_cycles_per_mm_median", "tensor_coherence_median",
        "glcm_contrast_median", "glcm_homogeneity_median",
    ],
}


def participant_average(medial: pd.DataFrame, lateral: pd.DataFrame) -> pd.DataFrame:
    keys = [column for column in medial if column.endswith("_median")]
    first = medial[["participant_id", *keys]].copy()
    second = lateral[["participant_id", *keys]].copy()
    paired = first.merge(second, on="participant_id", suffixes=("_medial", "_lateral"), validate="one_to_one")
    result = paired[["participant_id"]].copy()
    for key in keys:
        result[key] = paired[[f"{key}_medial", f"{key}_lateral"]].mean(axis=1)
    return result


def validate_models(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, predictions = [], []
    for outcome in OUTCOMES:
        for model_name, columns in FEATURE_SETS.items():
            subset = data[["participant_id", outcome, *columns]].dropna(subset=[outcome]).copy()
            result = grouped_nested_ridge_predictions(
                subset[columns].to_numpy(float), subset[outcome].to_numpy(float),
                subset["participant_id"].to_numpy(str), outer_splits=5, inner_splits=4,
            )
            observed, predicted = result.observed, result.predicted
            rho = spearmanr(observed, predicted)
            summary.append({
                "outcome": outcome,
                "model": model_name,
                "n": len(observed),
                "mae": mean_absolute_error(observed, predicted),
                "rmse": np.sqrt(mean_squared_error(observed, predicted)),
                "r2": r2_score(observed, predicted),
                "spearman_rho": rho.statistic,
                "spearman_p": rho.pvalue,
            })
            predictions.extend({
                "outcome": outcome, "model": model_name, "participant_id": participant,
                "observed": truth, "predicted": estimate, "outer_fold": fold, "selected_alpha": alpha,
            } for participant, truth, estimate, fold, alpha in zip(
                result.participant_ids, observed, predicted, result.outer_fold, result.selected_alpha
            ))
    return pd.DataFrame(summary), pd.DataFrame(predictions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Participant-level CPU FFT validation and ablations")
    parser.add_argument("medial", type=Path)
    parser.add_argument("lateral", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--permutations", type=int, default=1000)
    args = parser.parse_args()
    medial = pd.read_csv(args.medial, dtype={"participant_id": str})
    lateral = pd.read_csv(args.lateral, dtype={"participant_id": str})
    metadata = pd.read_csv(args.metadata, dtype={"participant_id": str})
    for frame in (medial, lateral, metadata):
        frame["participant_id"] = frame["participant_id"].str.zfill(3)
    average = participant_average(medial, lateral).merge(metadata, on="participant_id", validate="one_to_one")
    summary, predictions = validate_models(average)
    primary_columns = FEATURE_SETS["fft_multiscale"]
    permutation = participant_permutation_test(
        average[primary_columns].to_numpy(float), average["mean_total_plm"].to_numpy(float),
        average["participant_id"].to_numpy(str), iterations=args.permutations,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    average.to_csv(args.output / "table_paired_safo_features.csv", index=False)
    summary.to_csv(args.output / "table_nested_cv_ablations.csv", index=False)
    predictions.to_csv(args.output / "table_nested_cv_predictions.csv", index=False)
    (args.output / "primary_permutation_test.json").write_text(json.dumps(permutation, indent=2) + "\n", encoding="utf-8")
    primary = predictions[(predictions["outcome"] == "mean_total_plm") & (predictions["model"] == "fft_multiscale")]
    fig, axis = plt.subplots(figsize=(4.2, 4.0), constrained_layout=True)
    axis.scatter(primary["observed"], primary["predicted"], s=28, color="#43BFC7", edgecolor="#173E42", linewidth=.5)
    limits = [min(primary["observed"].min(), primary["predicted"].min()), max(primary["observed"].max(), primary["predicted"].max())]
    axis.plot(limits, limits, color="#C55443", linewidth=1.2, linestyle="--")
    axis.set(xlabel="Observed PLM score", ylabel="Nested-CV predicted PLM score", title="Participant-level SafO FFT validation")
    axis.spines[["top", "right"]].set_visible(False)
    for suffix in ("png", "svg"):
        fig.savefig(args.output / f"figure_nested_cv_plm.{suffix}", dpi=300)
    plt.close(fig)
    print(json.dumps({"participants": len(average), "models": len(summary), "permutation": permutation}, indent=2))


if __name__ == "__main__":
    main()
