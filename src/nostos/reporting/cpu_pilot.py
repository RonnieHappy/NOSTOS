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


OUTCOMES = ("mean_total_plm", "mean_total_oarsi", "mean_total_hhgs")


def benjamini_hochberg(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0, 1)
    return result


def bootstrap_spearman(x: np.ndarray, y: np.ndarray, *, repeats: int = 5000, seed: int = 240826) -> tuple[float, float]:
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repeats):
        sample = rng.integers(0, len(x), len(x))
        if np.unique(x[sample]).size > 1 and np.unique(y[sample]).size > 1:
            estimates.append(float(spearmanr(x[sample], y[sample]).statistic))
    return tuple(np.quantile(estimates, [0.025, 0.975]))


def correlation_table(data: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    rows = []
    for feature in features:
        for outcome in OUTCOMES:
            x = pd.to_numeric(data[feature], errors="coerce").to_numpy(float)
            y = pd.to_numeric(data[outcome], errors="coerce").to_numpy(float)
            valid = np.isfinite(x) & np.isfinite(y)
            test = spearmanr(x[valid], y[valid])
            lower, upper = bootstrap_spearman(x, y)
            rows.append({
                "feature": feature,
                "outcome": outcome,
                "n": int(valid.sum()),
                "spearman_rho": float(test.statistic),
                "bootstrap_ci_lower": lower,
                "bootstrap_ci_upper": upper,
                "p_value": float(test.pvalue),
            })
    frame = pd.DataFrame(rows)
    frame["q_value_bh"] = benjamini_hochberg(frame["p_value"].to_numpy())
    return frame.sort_values(["q_value_bh", "p_value", "feature", "outcome"])


def _outcome_label(name: str) -> str:
    return name.removeprefix("mean_total_").upper()


def plot_entropy(data: pd.DataFrame, output: Path) -> None:
    feature = "angular_entropy_median"
    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.35), constrained_layout=True)
    for axis, outcome in zip(axes, OUTCOMES):
        x = data[feature].to_numpy(float)
        y = data[outcome].to_numpy(float)
        valid = np.isfinite(x) & np.isfinite(y)
        x, y = x[valid], y[valid]
        axis.scatter(x, y, s=23, facecolor="#43BFC7", edgecolor="#173E42", linewidth=.45, alpha=.82)
        coefficients = np.polyfit(x, y, 1)
        grid = np.linspace(x.min(), x.max(), 100)
        axis.plot(grid, np.polyval(coefficients, grid), color="#C55443", linewidth=1.6)
        rho = spearmanr(x, y).statistic
        axis.set(title=f"{_outcome_label(outcome)}  ρ={rho:.2f}", xlabel="Angular spectral entropy", ylabel="Expert score")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(color="#DDE5E6", linewidth=.6, alpha=.65)
    fig.suptitle("Cartilage angular spectral entropy across histologic outcomes", fontsize=12)
    for suffix in ("png", "svg"):
        fig.savefig(output / f"figure_cpu_entropy_associations.{suffix}", dpi=300)
    plt.close(fig)


def plot_effects(correlations: pd.DataFrame, output: Path) -> None:
    selected = correlations[correlations["feature"].isin([
        "angular_entropy_median", "anisotropy_median", "tensor_coherence_median", "glcm_contrast_median"
    ])].copy()
    labels = {
        "angular_entropy_median": "FFT entropy",
        "anisotropy_median": "FFT anisotropy",
        "tensor_coherence_median": "Structure tensor",
        "glcm_contrast_median": "GLCM contrast",
    }
    fig, axes = plt.subplots(1, 3, figsize=(10.8, 4.2), sharex=True, constrained_layout=True)
    for axis, outcome in zip(axes, OUTCOMES):
        subset = selected[selected["outcome"] == outcome].set_index("feature").loc[list(labels)]
        y = np.arange(len(subset))[::-1]
        rho = subset["spearman_rho"].to_numpy()
        lower = subset["bootstrap_ci_lower"].to_numpy()
        upper = subset["bootstrap_ci_upper"].to_numpy()
        axis.errorbar(rho, y, xerr=[rho - lower, upper - rho], fmt="o", color="#173E42", ecolor="#43BFC7", capsize=3)
        axis.axvline(0, color="#8A989A", linewidth=.8)
        axis.set(title=_outcome_label(outcome), xlabel="Spearman ρ", yticks=y, yticklabels=list(labels.values()))
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.grid(axis="x", color="#DDE5E6", linewidth=.6)
    for suffix in ("png", "svg"):
        fig.savefig(output / f"figure_cpu_fft_vs_comparators.{suffix}", dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CPU-first NOSTOS pilot statistics and figures")
    parser.add_argument("features", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    features = pd.read_csv(args.features, dtype={"participant_id": str})
    metadata = pd.read_csv(args.metadata, dtype={"participant_id": str})
    features["participant_id"] = features["participant_id"].str.zfill(3)
    metadata["participant_id"] = metadata["participant_id"].str.zfill(3)
    data = features.merge(metadata, on="participant_id", validate="one_to_one")
    feature_columns = [column for column in features if column.endswith("_median")]
    correlations = correlation_table(data, feature_columns)
    args.output.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output / "table_cpu_participant_features.csv", index=False)
    correlations.to_csv(args.output / "table_cpu_correlations.csv", index=False)
    correlations[correlations["q_value_bh"] < .05].to_csv(args.output / "table_cpu_fdr_significant.csv", index=False)
    plot_entropy(data, args.output)
    plot_effects(correlations, args.output)
    report = {
        "participants": len(data),
        "feature_tests": len(correlations),
        "fdr_significant": int((correlations["q_value_bh"] < .05).sum()),
        "minimum_tiles": int(data["analyzed_tiles"].min()),
        "median_tiles": float(data["analyzed_tiles"].median()),
    }
    (args.output / "cpu_pilot_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
