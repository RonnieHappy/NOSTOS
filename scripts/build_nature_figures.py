"""Rebuild manuscript figures with restrained, publication-scale styling."""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cpu_pilot" / "publication"
TEAL, VERMILION, INK, GRID = "#2A7886", "#B84A32", "#202124", "#D9DEE2"

mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman"],
    "font.size": 8.5, "axes.labelsize": 9, "axes.titlesize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.linewidth": .7, "xtick.major.width": .7, "ytick.major.width": .7,
    "xtick.major.size": 3, "ytick.major.size": 3, "figure.dpi": 180,
    "savefig.dpi": 600, "svg.fonttype": "none",
})

def clean(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out", color=INK)

def save(fig, number):
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"figure_{number}.{ext}", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"figure_{number}.jpg", bbox_inches="tight", facecolor="white", pil_kwargs={"quality":96})
    plt.close(fig)

def association_figure(site, number):
    features = pd.read_csv(ROOT / "outputs" / "cpu_pilot" / f"safo_{site.lower()}_features.csv", dtype={"participant_id": str})
    meta = pd.read_csv(ROOT / "manifests" / "metadata.csv", dtype={"participant_id": str})
    data = features.merge(meta, on="participant_id", validate="one_to_one")
    outcomes = [("mean_total_plm", "PLM"), ("mean_total_oarsi", "OARSI"), ("mean_total_hhgs", "HHGS")]
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.35), constrained_layout=True)
    for i, (column, label) in enumerate(outcomes):
        ax = axes[i]; x = data.angular_entropy_median.to_numpy(); y = data[column].to_numpy()
        rng = np.random.default_rng(20260825 + i + number * 10)
        jitter = rng.normal(0, .035 if label != "OARSI" else .06, len(y))
        ax.scatter(x, y + jitter, s=13, facecolor=TEAL, edgecolor="white", linewidth=.35, alpha=.78, rasterized=True)
        slope, intercept = np.polyfit(x, y, 1); xx = np.linspace(x.min(), x.max(), 100)
        ax.plot(xx, slope * xx + intercept, color=VERMILION, lw=1.35)
        rho = spearmanr(x, y).statistic
        ax.text(.04, .96, f"{chr(97+i)}", transform=ax.transAxes, va="top", fontweight="bold", fontsize=10)
        ax.text(.12, .96, f"{label}   ρ = {rho:.2f}", transform=ax.transAxes, va="top")
        ax.set_xlabel("Angular spectral entropy")
        if i == 0: ax.set_ylabel("Expert score")
        clean(ax)
    fig.suptitle(f"{site} Safranin-O sections", x=.52, y=1.02, fontsize=10)
    save(fig, number)

def prediction_figure():
    data = pd.read_csv(ROOT / "outputs" / "cpu_pilot" / "validation" / "table_nested_cv_predictions.csv")
    data = data[(data.outcome == "mean_total_plm") & (data.model == "fft_entropy")]
    fig, ax = plt.subplots(figsize=(3.45, 3.1), constrained_layout=True)
    rng = np.random.default_rng(20260825)
    x = data.observed.to_numpy() + rng.normal(0, .035, len(data)); y = data.predicted.to_numpy()
    ax.scatter(x, y, s=18, facecolor=TEAL, edgecolor="white", linewidth=.4, alpha=.82)
    lo = min(data.observed.min(), data.predicted.min()); hi = max(data.observed.max(), data.predicted.max())
    ax.plot([lo, hi], [lo, hi], color=VERMILION, lw=1.2, ls=(0, (4, 2)))
    ax.text(.03, .97, "a", transform=ax.transAxes, va="top", fontweight="bold", fontsize=10)
    ax.set(xlabel="Observed PLM score", ylabel="Nested-CV predicted PLM score", xlim=(-.25, 6.45), ylim=(-.25, 6.45))
    ax.set_aspect("equal", adjustable="box"); clean(ax); save(fig, 3)

def robustness_figure():
    robust = pd.read_csv(ROOT / "outputs" / "cpu_pilot" / "robustness" / "tile_robustness_summary.csv").sort_values("angular_entropy_relative_drift_median")
    mask = pd.read_csv(ROOT / "outputs" / "cpu_pilot" / "robustness" / "mask_sensitivity_summary.csv")
    labels = robust.perturbation.str.replace("_", " ").str.replace("noise 05", "5% noise").str.replace("noise 01", "1% noise").str.replace("rotation 90", "90° rotation")
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.7), constrained_layout=True)
    y = np.arange(len(robust)); axes[0].barh(y, 100*robust.angular_entropy_relative_drift_median, color=TEAL, height=.62)
    axes[0].scatter(100*robust.angular_entropy_relative_drift_p95, y, color=VERMILION, s=14, label="95th percentile", zorder=3)
    axes[0].set_yticks(y, labels); axes[0].set_xlabel("Absolute entropy drift (%)"); axes[0].legend(frameon=False, loc="lower right")
    axes[1].plot(mask.delta_um, 100*mask.entropy_drift_median, marker="o", ms=3.5, color=TEAL, lw=1.2, label="Median")
    axes[1].plot(mask.delta_um, 100*mask.entropy_drift_p95, marker="s", ms=3.5, color=VERMILION, lw=1.2, label="95th percentile")
    axes[1].axvline(0, color="#888888", lw=.7); axes[1].set(xlabel="Mask-boundary change (µm)", ylabel="Absolute entropy drift (%)"); axes[1].legend(frameon=False)
    for label, ax in zip(("a", "b"), axes): ax.text(.02, .98, label, transform=ax.transAxes, va="top", fontweight="bold", fontsize=10); clean(ax)
    save(fig, 4)

def mechanism_figure():
    data = pd.read_csv(ROOT / "outputs" / "flagship" / "mechanistic" / "table_mechanistic_associations.csv")
    data = data[data.feature == "angular_entropy_median"].copy(); data["column"] = data.site.str[:3] + " " + data.section_rank.astype(str)
    order = ["hhgs_safo_loss", "hhgs_structure", "oarsi_grade", "oarsi_stage", "hhgs_cells", "hhgs_tidemark", "plm_superficial_disorganization", "plm_deep_disorganization", "plm_total_disorganization"]
    labels = ["Safranin-O loss", "HHGS structure", "OARSI grade", "OARSI stage", "HHGS cells", "HHGS tidemark", "PLM superficial", "PLM deep", "PLM total"]
    matrix = data.pivot(index="component", columns="column", values="spearman_rho").reindex(order)
    q = data.pivot(index="component", columns="column", values="q_value_bh_global").reindex(index=matrix.index, columns=matrix.columns)
    fig, ax = plt.subplots(figsize=(4.65, 3.65), constrained_layout=True)
    cmap = mpl.colors.LinearSegmentedColormap.from_list("nostos", ["#175A7A", "#F7F7F5", "#B84A32"])
    im = ax.imshow(matrix, cmap=cmap, vmin=-.5, vmax=.5, aspect="auto")
    ax.set_xticks(range(4), matrix.columns); ax.set_yticks(range(len(labels)), labels)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iloc[i, j]
            if np.isfinite(value): ax.text(j, i, f"{value:.2f}{'*' if q.iloc[i,j] < .05 else ''}", ha="center", va="center", fontsize=7.5, color="white" if value < -.32 else INK)
    bar = fig.colorbar(im, ax=ax, fraction=.045, pad=.04); bar.set_label("Spearman ρ")
    ax.set_xlabel("Site and section rank"); ax.tick_params(length=0); ax.spines[:].set_visible(False)
    save(fig, 5)

if __name__ == "__main__":
    association_figure("Medial", 1); association_figure("Lateral", 2)
    prediction_figure(); robustness_figure(); mechanism_figure()
