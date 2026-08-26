"""Build evidence-linked NOSTOS-0 main figures 2 and 3."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
from PIL import Image
from matplotlib.colors import Normalize
from scipy.ndimage import distance_transform_edt

from nostos.features.response_modules import maximal_sphere_local_thickness
from nostos.validation.phantoms import generate_phantom

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0"
BLUE, TEAL, RED, AMBER = "#1769AA", "#168A8A", "#C94C4C", "#D89B24"
INK, MID, PALE = "#20262E", "#717983", "#E9EDF1"

mpl.rcParams.update({
    "font.family": "Times New Roman",
    "font.size": 8,
    "axes.linewidth": 0.7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "svg.fonttype": "none",
})


def panel(ax, letter: str) -> None:
    ax.text(-0.08, 1.04, letter, transform=ax.transAxes, fontsize=12,
            fontweight="bold", va="bottom", ha="left", clip_on=False)


def save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.png", dpi=600, bbox_inches="tight", pad_inches=0.04,
                facecolor="white")
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight", pad_inches=0.04,
                facecolor="white")
    plt.close(fig)


def figure2() -> None:
    validation = json.loads((ROOT / "outputs/nostos0-synthetic-v1/validation.json").read_text())
    matrix = json.loads((ROOT / "outputs/nostos0-module-perturbations-v1/module_perturbation_matrix.json").read_text())
    bench = json.loads((ROOT / "outputs/nostos0-benchmark-v1/representation_benchmark.json").read_text())
    kym = json.loads((ROOT / "outputs/nostos0-benchmark-v1/kymatio_benchmark.json").read_text())
    pyr = json.loads((ROOT / "outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json").read_text())

    fig = plt.figure(figsize=(7.2, 5.0), constrained_layout=True)
    gs = fig.add_gridspec(3, 12, height_ratios=[1.15, 1.0, 1.15])
    constructs = ["orientation", "blob", "tube", "roughness", "network", "heterogeneity"]
    cmaps = ["gray", "magma", "magma", "gray", "viridis", "cividis"]
    for i, (name, cmap) in enumerate(zip(constructs, cmaps, strict=True)):
        ax = fig.add_subplot(gs[0, i * 2:(i + 1) * 2])
        phantom = generate_phantom(name)
        ax.imshow(phantom.image, cmap=cmap, interpolation="nearest")
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(name.capitalize(), fontsize=7, pad=2)
        for spine in ax.spines.values(): spine.set_visible(False)
        if i == 0: panel(ax, "a")

    ax = fig.add_subplot(gs[1, :5]); panel(ax, "b")
    perturb = validation["perturbation_results"]
    names = [p["perturbation"]["kind"].replace("partial_volume", "partial\nvolume") for p in perturb]
    angular = np.asarray([p["errors"]["circular_angular_error_degrees"] for p in perturb])
    scale = 100 * np.asarray([p["errors"]["relative_scale_error"] for p in perturb])
    x = np.arange(len(names))
    ax.plot(x, angular, "o-", color=BLUE, lw=1.4, ms=3, label="angle (°)")
    ax.plot(x, scale, "s-", color=AMBER, lw=1.4, ms=3, label="scale (%)")
    ax.set_xticks(x, names, rotation=40, ha="right", fontsize=6.5)
    ax.set_ylabel("error")
    ax.legend(ncol=2, loc="upper left", fontsize=7)
    ax.axhline(0, color=PALE, lw=0.7, zorder=0)

    ax = fig.add_subplot(gs[1, 5:9]); panel(ax, "c")
    modules = ["tensor", "hessian", "geometry", "network", "spatial"]
    pert_names = ["rotation", "resampling", "blur", "noise", "contrast"]
    status = np.full((len(modules), len(pert_names)), np.nan)
    for result in matrix["results"]:
        if result["perturbation"]["kind"] == "mask_error": continue
        if result["module"] in modules and result["perturbation"]["kind"] in pert_names:
            i, j = modules.index(result["module"]), pert_names.index(result["perturbation"]["kind"])
            status[i, j] = max(status[i, j] if np.isfinite(status[i, j]) else 0, int(result["passed"]))
    ax.imshow(np.ma.masked_invalid(status), cmap=mpl.colors.ListedColormap([RED, TEAL]), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pert_names)), pert_names, rotation=40, ha="right", fontsize=6.5)
    ax.set_yticks(range(len(modules)), modules, fontsize=7)
    ax.tick_params(length=0)
    for spine in ax.spines.values(): spine.set_visible(False)

    ax = fig.add_subplot(gs[1, 9:]); panel(ax, "d")
    curve = validation["module_gates"]["network"]["surviving_fraction"]
    ax.plot(range(len(curve)), curve, "o-", color=TEAL, lw=2, ms=4)
    ax.fill_between(range(len(curve)), curve, color=TEAL, alpha=.12)
    ax.set(xlabel="erosion step", ylabel="surviving fraction", ylim=(-.03, 1.05))
    ax.set_xticks(range(len(curve)))

    ax = fig.add_subplot(gs[2, :7]); panel(ax, "e")
    values = {
        "conventional": next(r["balanced_accuracy"] for r in bench["results"] if r["representation"] == "conventional_scalar"),
        "naive": next(r["balanced_accuracy"] for r in bench["results"] if r["representation"] == "naive_response_summaries"),
        "NOSTOS": next(r["balanced_accuracy"] for r in bench["results"] if r["representation"] == "nostos_response_curves"),
        "Kymatio": kym["balanced_accuracy"],
        "PyRadiomics": pyr["synthetic_benchmark"]["balanced_accuracy"],
    }
    labels, vals = list(values), list(values.values())
    colors = [MID, MID, BLUE, RED, TEAL]
    ax.barh(range(len(labels)), vals, color=colors, height=.58, edgecolor="white")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlim(.82, 1.015); ax.set_xlabel("held-out balanced accuracy")
    ax.invert_yaxis()
    for y, value in enumerate(vals): ax.text(value + .004, y, f"{value:.3f}", va="center", fontsize=7)

    ax = fig.add_subplot(gs[2, 7:]); panel(ax, "f")
    ablations = [(r["representation"].replace("nostos_without_", "−"), r["balanced_accuracy"])
                 for r in bench["results"] if r["representation"].startswith("nostos_without_")]
    names, vals = zip(*ablations)
    ax.bar(range(len(vals)), vals, color=[RED if v < 1 else BLUE for v in vals], width=.65)
    ax.set_xticks(range(len(names)), names, rotation=35, ha="right", fontsize=6.5)
    ax.set_ylim(.82, 1.02); ax.set_ylabel("balanced accuracy")
    ax.axhline(1, color=INK, lw=.7, ls=":")
    save(fig, "figure_2_synthetic_validation")


def figure3(data_root: Path) -> None:
    receipt = json.loads((ROOT / "outputs/external-bone-v1/external_bone_validation.json").read_text())
    cases = receipt["cases"]
    case = max(cases, key=lambda row: row["bone_fraction"])
    seg_path = data_root / f"{case['case']}_SEG_SUB.nii"
    ref_path = data_root / f"{case['case']}_SEG_SUB_DT_THICK_CONVERT.nii"
    mask = np.asanyarray(nib.load(seg_path).dataobj) > 0
    ref = np.asanyarray(nib.load(ref_path).dataobj).astype(float)
    spacing = tuple(float(v) for v in nib.load(seg_path).header.get_zooms()[:3])
    est = maximal_sphere_local_thickness(mask, spacing_um=spacing, size_bins=32)
    z = mask.shape[2] // 2
    display = np.where(mask[:, :, z], ref[:, :, z], np.nan)
    estimate = np.where(mask[:, :, z], est[:, :, z], np.nan)
    residual = estimate - display

    fig = plt.figure(figsize=(7.2, 4.6), constrained_layout=True)
    gs = fig.add_gridspec(2, 12, height_ratios=[1.25, 1])
    vmax = np.nanpercentile(np.r_[display[np.isfinite(display)], estimate[np.isfinite(estimate)]], 99)
    for i, (arr, title) in enumerate([(display, "reference"), (estimate, "NOSTOS"), (residual, "residual")]):
        ax = fig.add_subplot(gs[0, i * 4:(i + 1) * 4])
        if i < 2:
            im = ax.imshow(arr, cmap="inferno", vmin=0, vmax=vmax)
        else:
            lim = np.nanpercentile(np.abs(arr), 99)
            im = ax.imshow(arr, cmap="coolwarm", vmin=-lim, vmax=lim)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title, fontsize=8)
        for spine in ax.spines.values(): spine.set_visible(False)
        panel(ax, chr(ord("a") + i))
        inset = ax.inset_axes([.08, .06, .55, .035])
        mpl.colorbar.ColorbarBase(inset, cmap=im.cmap, norm=im.norm, orientation="horizontal")
        inset.tick_params(labelsize=5, length=1); inset.set_xlabel("mm", fontsize=6, labelpad=0)

    ax = fig.add_subplot(gs[1, :4]); panel(ax, "d")
    refs = np.asarray([r["reference_mean_thickness_mm"] for r in cases])
    preds = np.asarray([r["nostos_mean_thickness_mm"] for r in cases])
    ax.scatter(refs, preds, s=25, color=BLUE, edgecolor="white", linewidth=.5, zorder=3)
    lo, hi = min(refs.min(), preds.min()), max(refs.max(), preds.max())
    ax.plot([lo, hi], [lo, hi], color=INK, lw=.8, ls=":")
    ax.set(xlabel="reference mean (mm)", ylabel="NOSTOS mean (mm)")

    ax = fig.add_subplot(gs[1, 4:8]); panel(ax, "e")
    rhos = [r["voxelwise_spearman"] for r in cases]
    ax.scatter(range(len(cases)), rhos, color=TEAL, s=27)
    ax.axhline(np.median(rhos), color=INK, ls=":", lw=.8)
    ax.set(xlabel="volume", ylabel="voxelwise Spearman ρ", ylim=(.88, .96))
    ax.set_xticks(range(len(cases)), range(1, len(cases) + 1))

    ax = fig.add_subplot(gs[1, 8:]); panel(ax, "f")
    n_mae = np.asarray([r["mae_mm"] for r in cases])
    b_mae = np.asarray([r["nearest_boundary_baseline_mae_mm"] for r in cases])
    for i in range(len(cases)):
        ax.plot([0, 1], [b_mae[i], n_mae[i]], color=PALE, lw=1)
        ax.scatter([0], [b_mae[i]], color=RED, s=18, zorder=3)
        ax.scatter([1], [n_mae[i]], color=BLUE, s=18, zorder=3)
    ax.set_xticks([0, 1], ["nearest\nboundary", "NOSTOS"])
    ax.set_ylabel("MAE (mm)")
    save(fig, "figure_3_bone_validation")


def figure4(filament_root: Path, cartilage_root: Path) -> None:
    receipt = json.loads((ROOT / "outputs/external-filament-v1/external_filament_validation.json").read_text())
    comparison = receipt["summary"]["representation_comparison"]
    assoc = pd.read_csv(ROOT / "outputs/cartilage-ablation-analysis-v1_1/ablation_associations.csv")
    selected = assoc[(assoc.site == "Medial") & (assoc.outcome == "meanhhgsscore")]
    order = [
        "baseline_072_angular_entropy_median",
        "strict_095_angular_entropy_median",
        "surface_excluded_100um_angular_entropy_median",
        "surface_excluded_250um_angular_entropy_median",
        "extreme_dark_object_excluded_25um_angular_entropy_median",
    ]
    selected = selected.set_index("feature").loc[order].reset_index()

    fig = plt.figure(figsize=(8.4, 5.25), constrained_layout=False)
    fig.subplots_adjust(left=.055, right=.985, bottom=.12, top=.94, wspace=1.35, hspace=.55)
    gs = fig.add_gridspec(2, 12, height_ratios=[1.05, 1])
    species = ["GS", "PO", "TS"]
    for i, species_name in enumerate(species):
        path = sorted((filament_root / species_name / "image").glob("*.jpg"))[0]
        image = np.asarray(Image.open(path).convert("RGB"))
        ax = fig.add_subplot(gs[0, i * 2:(i + 1) * 2])
        ax.imshow(image); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(species_name, fontsize=8, pad=2)
        for spine in ax.spines.values(): spine.set_visible(False)
        if i == 0: panel(ax, "a")

    ax = fig.add_subplot(gs[0, 6:9]); panel(ax, "b")
    keys = ["nostos_response_geometry", "conventional_scalar", "naive_block_summaries"]
    vals = [comparison[k] for k in keys]
    ax.barh(range(3), vals, color=[BLUE, MID, MID], height=.55)
    ax.set_yticks(range(3), ["response", "scalar", "summary"], fontsize=6.5)
    ax.set_xlim(.5, .74); ax.set_xlabel("balanced accuracy")
    ax.invert_yaxis()
    for y, value in enumerate(vals): ax.text(value - .004, y, f"{value:.3f}", va="center", ha="right", color="white", fontsize=6.5)

    ax = fig.add_subplot(gs[0, 9:]); panel(ax, "c")
    ablation_keys = [k for k in comparison if k.startswith("nostos_without_")]
    ablation_vals = [comparison[k] for k in ablation_keys]
    labels = [k.replace("nostos_without_", "−") for k in ablation_keys]
    colors = [TEAL if v > comparison["nostos_response_geometry"] else RED for v in ablation_vals]
    ax.bar(range(len(labels)), ablation_vals, color=colors, width=.65)
    ax.axhline(comparison["nostos_response_geometry"], color=INK, ls=":", lw=.8)
    ax.set_xticks(range(len(labels)), labels, rotation=42, ha="right", fontsize=5.7)
    ax.set_ylim(.62, .75); ax.set_ylabel("balanced accuracy")

    review = sorted(cartilage_root.glob("*_proposal.png"))[0]
    ax = fig.add_subplot(gs[1, :5]); panel(ax, "d")
    ax.imshow(Image.open(review).convert("RGB")); ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.text(.01, .02, "algorithmic proposal", transform=ax.transAxes, fontsize=7,
            color="white", bbox={"facecolor": INK, "edgecolor": "none", "pad": 2})

    ax = fig.add_subplot(gs[1, 5:9]); panel(ax, "e")
    y = np.arange(len(selected))
    rho = selected.spearman_rho.to_numpy()
    lower = rho - selected.ci95_low.to_numpy()
    upper = selected.ci95_high.to_numpy() - rho
    ax.errorbar(rho, y, xerr=np.vstack([lower, upper]), fmt="o", color=BLUE,
                ecolor=MID, elinewidth=1, capsize=2, ms=4)
    ax.axvline(0, color=INK, lw=.7, ls=":")
    ax.set_yticks(y, ["baseline", "95% purity", "surface 100", "surface 250", "dark objects"], fontsize=6.5)
    ax.invert_yaxis(); ax.set_xlabel("Spearman ρ with medial HHGS")
    ax.set_xlim(-.62, .08)

    ax = fig.add_subplot(gs[1, 9:]); panel(ax, "f")
    statuses = ["physical scale", "cross-species", "cartilage ROI", "clinical use"]
    levels = [1, .55, .25, 0]
    colors = [TEAL, AMBER, RED, MID]
    ax.barh(range(4), levels, color=colors, height=.5)
    ax.set_yticks(range(4), statuses, fontsize=6.2)
    ax.set_xlim(0, 1.02); ax.set_xticks([0, .5, 1], ["absent", "exploratory", "supported"], fontsize=6)
    ax.invert_yaxis()
    save(fig, "figure_4_cross_domain_boundaries")


if __name__ == "__main__":
    figure2()
    figure3(Path(r"E:\NOSTOS\data\public\trabecular-bone-zenodo-11061947"))
    figure4(
        Path(r"E:\NOSTOS\data\public\myceliumseg-zenodo-15224240\extracted\labeled-GS_PO_TS"),
        Path(r"E:\NOSTOS\validation\cartilage-mask-review-v1\review_images"),
    )
