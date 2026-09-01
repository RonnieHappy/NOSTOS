"""Build compact, evidence-linked supplementary figures for Small Methods v34."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import findfont

from nostos.validation.phantoms import generate_phantom


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0_small_methods_si"
INK = "#17212B"
MID = "#74818C"
PALE = "#E7ECEF"
TEAL = "#087F8C"
TEAL_LIGHT = "#B9DEDC"
AMBER = "#D89B24"


def configure_style() -> None:
    findfont("Times New Roman", fallback_to_default=False)
    mpl.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.serif": ["Times New Roman"],
            "font.size": 8.0,
            "axes.linewidth": 0.65,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def panel(ax: plt.Axes, letter: str) -> None:
    ax.text(
        -0.08,
        1.04,
        letter,
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="bottom",
        ha="left",
        clip_on=False,
        color=INK,
    )


def save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        kwargs = {"bbox_inches": "tight", "pad_inches": 0.04, "facecolor": "white"}
        if suffix == "png":
            kwargs["dpi"] = 600
        fig.savefig(OUT / f"{stem}.{suffix}", **kwargs)
    plt.close(fig)


def build_synthetic_validation() -> None:
    validation = json.loads(
        (ROOT / "outputs" / "nostos0-synthetic-v1" / "validation.json").read_text(encoding="utf-8")
    )
    matrix = json.loads(
        (ROOT / "outputs" / "nostos0-module-perturbations-v1" / "module_perturbation_matrix.json").read_text(
            encoding="utf-8"
        )
    )

    fig = plt.figure(figsize=(7.08, 4.18), constrained_layout=False)
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.12, top=0.955, hspace=0.30, wspace=0.65)
    gs = fig.add_gridspec(2, 20, height_ratios=[1.0, 1.12])

    constructs = ["orientation", "blob", "tube", "network", "heterogeneity"]
    cmaps = ["gray", "magma", "magma", "viridis", "cividis"]
    for index, (name, cmap) in enumerate(zip(constructs, cmaps, strict=True)):
        ax = fig.add_subplot(gs[0, index * 4 : (index + 1) * 4])
        phantom = generate_phantom(name)
        ax.imshow(phantom.image, cmap=cmap, interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(name, fontsize=8.0, fontweight="bold", pad=3)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if index == 0:
            panel(ax, "a")

    ax = fig.add_subplot(gs[1, :7])
    panel(ax, "b")
    perturbations = validation["perturbation_results"]
    names = [row["perturbation"]["kind"].replace("partial_volume", "partial\nvolume") for row in perturbations]
    angular = np.asarray([row["errors"]["circular_angular_error_degrees"] for row in perturbations])
    scale = 100 * np.asarray([row["errors"]["relative_scale_error"] for row in perturbations])
    x = np.arange(len(names))
    ax.plot(x, angular, "o-", color=TEAL, lw=1.7, ms=3.5, label="angle (°)")
    ax.plot(x, scale, "s-", color=AMBER, lw=1.7, ms=3.5, label="scale (%)")
    ax.set_xticks(x, names, rotation=38, ha="right", fontsize=6.2)
    ax.set_ylabel("error")
    ax.legend(frameon=False, ncol=2, loc="upper center", fontsize=6.8)
    ax.grid(axis="y", color=PALE, lw=0.65)
    ax.spines[["top", "right"]].set_visible(False)

    ax = fig.add_subplot(gs[1, 8:16])
    panel(ax, "c")
    modules = ["tensor", "Hessian", "geometry", "network", "spatial"]
    module_keys = ["tensor", "hessian", "geometry", "network", "spatial"]
    perturbation_names = ["rotation", "resampling", "blur", "noise", "contrast"]
    status = np.full((len(modules), len(perturbation_names)), np.nan)
    for row in matrix["results"]:
        kind = row["perturbation"]["kind"]
        if row["module"] in module_keys and kind in perturbation_names:
            i = module_keys.index(row["module"])
            j = perturbation_names.index(kind)
            status[i, j] = float(bool(row["passed"]))
    cmap = mpl.colors.ListedColormap(["#CB4A58", TEAL])
    ax.imshow(np.ma.masked_invalid(status), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_facecolor(PALE)
    ax.set_xticks(range(len(perturbation_names)), perturbation_names, rotation=38, ha="right", fontsize=6.4)
    ax.set_yticks(range(len(modules)), modules, fontsize=6.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax = fig.add_subplot(gs[1, 17:])
    panel(ax, "d")
    survival = np.asarray(validation["module_gates"]["network"]["surviving_fraction"], dtype=float)
    steps = np.arange(survival.size)
    ax.plot(steps, survival, "o-", color=TEAL, lw=2.1, ms=4.2)
    ax.fill_between(steps, survival, color=TEAL_LIGHT, alpha=0.55)
    ax.set_xlabel("erosion step")
    ax.set_xticks(steps)
    ax.set_ylim(-0.04, 1.05)
    ax.grid(axis="y", color=PALE, lw=0.65)
    ax.spines[["top", "right"]].set_visible(False)

    save(fig, "figure_s1_synthetic_validation")


def main() -> None:
    configure_style()
    build_synthetic_validation()
    print(OUT / "figure_s1_synthetic_validation.png")


if __name__ == "__main__":
    main()
