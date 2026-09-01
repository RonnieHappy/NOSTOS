"""Build the compact specimen-first NOSTOS Small Methods v36 figures.

The visual grammar follows the supplied 2026 Small Methods examples: authentic
microscopy dominates, plots are subordinate and every panel has one inferential
job. Biological pixels are loaded only from checksum-locked public archives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

import build_nostos0_small_methods_figures as sm
import build_nostos0_small_methods_figures_v35 as v35
import build_nostos0_validity_figures as vf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0_small_methods_v36"
sm.OUT = OUT
v35.OUT = OUT

INK = sm.INK
MID = sm.MID
LIGHT = sm.LIGHT
PALE = sm.PALE
TEAL = sm.TEAL
TEAL_LIGHT = sm.TEAL_LIGHT
BLUE = sm.BLUE
RED = sm.RED
RED_DARK = sm.RED_DARK
AMBER = sm.AMBER
WHITE = sm.WHITE

mpl.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "font.size": 7.7,
        "axes.titlesize": 7.8,
        "axes.labelsize": 7.4,
        "xtick.labelsize": 6.7,
        "ytick.labelsize": 6.7,
        "legend.fontsize": 6.7,
        "svg.fonttype": "none",
        "svg.hashsalt": "nostos-small-methods-v36",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def panel(ax: mpl.axes.Axes, letter: str, *, inside: bool = False) -> None:
    writer = getattr(ax, "text2D", ax.text)
    writer(
        0.018 if inside else -0.050,
        0.982 if inside else 1.018,
        letter,
        transform=ax.transAxes,
        ha="left" if inside else "right",
        va="top" if inside else "bottom",
        fontsize=9.2,
        fontweight="bold",
        color=WHITE if inside else INK,
        clip_on=False,
        zorder=60,
    )


def compact_image(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    label: str,
    *,
    cmap: str | mpl.colors.Colormap | None = "gray",
    vmin: float | None = None,
    vmax: float | None = None,
) -> mpl.image.AxesImage:
    mappable = ax.imshow(image, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.text(
        0.5,
        1.020,
        label,
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=7.5,
        fontweight="bold",
        color=INK,
    )
    return mappable


def clean_axes(ax: mpl.axes.Axes, *, grid: bool = True) -> None:
    sm.clean_axes(ax, grid=grid)
    ax.margins(x=0.02)


def support_matrix(ax: mpl.axes.Axes, supported: set[tuple[str, float]]) -> None:
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    matrix = np.array(
        [[1 if (acquisition, scale) in supported else 0 for scale in scales] for acquisition in acquisitions]
    )
    colors = np.empty((*matrix.shape, 4), dtype=float)
    colors[matrix == 1] = mpl.colors.to_rgba(TEAL)
    colors[matrix == 0] = mpl.colors.to_rgba("#E8ECEF")
    ax.imshow(colors, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(3), ["4", "8", "16"])
    ax.set_yticks(range(5), ["raw", "2", "4", "8", "16"])
    ax.set_xlabel("scale (px)")
    ax.set_ylabel("captures")
    for row in range(5):
        for column in range(3):
            ax.text(
                column,
                row,
                "●" if matrix[row, column] else "×",
                ha="center",
                va="center",
                color=WHITE if matrix[row, column] else MID,
                fontsize=8.5,
                fontweight="bold",
            )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def measurement_rail(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    orientation: np.ndarray,
    supported: set[tuple[str, float]],
) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    positions = [(0.02, 0.18, 0.20, 0.66), (0.29, 0.18, 0.20, 0.66)]
    for (x, y, width, height), data, cmap in (
        (positions[0], vf.robust_unit(image), "gray"),
        (positions[1], orientation, None),
    ):
        inset = ax.inset_axes([x, y, width, height])
        inset.imshow(data, cmap=cmap, interpolation="nearest")
        inset.set_axis_off()
    lattice = ax.inset_axes([0.57, 0.20, 0.18, 0.60])
    support_matrix(lattice, supported)
    lattice.set_xticks([])
    lattice.set_yticks([])
    lattice.set_xlabel("")
    lattice.set_ylabel("")
    for start, end in ((0.22, 0.285), (0.49, 0.565)):
        ax.add_patch(
            FancyArrowPatch(
                (start, 0.51),
                (end, 0.51),
                arrowstyle="-|>",
                mutation_scale=8,
                linewidth=0.9,
                color=MID,
            )
        )
    ax.plot([0.75, 0.80], [0.51, 0.51], color=MID, linewidth=0.9)
    ax.plot([0.80, 0.80], [0.33, 0.67], color=MID, linewidth=0.9)
    for y in (0.33, 0.67):
        ax.add_patch(FancyArrowPatch((0.80, y), (0.825, y), arrowstyle="-|>", mutation_scale=8, linewidth=0.9, color=MID))
    ax.add_patch(Rectangle((0.83, 0.56), 0.14, 0.22, facecolor="#D8EFEE", edgecolor=TEAL, linewidth=1.0))
    ax.add_patch(Rectangle((0.83, 0.22), 0.14, 0.22, facecolor="#F1F3F5", edgecolor="#AAB3BA", linewidth=1.0))
    ax.text(0.90, 0.67, "emit", ha="center", va="center", color=TEAL, fontweight="bold")
    ax.text(0.90, 0.33, "withhold", ha="center", va="center", color=MID, fontweight="bold", fontsize=6.5)


def figure1(
    biosr: Mapping[str, Any],
    biosr_rows: Sequence[Mapping[str, Any]],
    fmd: Mapping[str, Any],
    strict_profile: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    bio_input = vf.center_crop(biosr["clean"], 430)
    bio_reference = vf.center_crop(biosr["reference"], 860)
    bio_orientation, bio_coherence = vf.orientation_rgb(bio_input, sigma=3.0)
    fmd_input = vf.center_crop(fmd["ladder"]["avg8"], 430)
    fmd_orientation, fmd_coherence = vf.orientation_rgb(fmd_input, sigma=2.0)
    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in strict_profile["supported_cells"]
    }

    fig = plt.figure(figsize=(7.08, 3.82))
    fig.subplots_adjust(left=0.065, right=0.99, top=0.970, bottom=0.110, hspace=0.17, wspace=0.52)
    gs = fig.add_gridspec(2, 12, height_ratios=[0.90, 1.10])
    top = gs[0, :].subgridspec(1, 7, wspace=0.035)
    displays = [
        (vf.robust_unit(bio_input), "BioSR input", "gray"),
        (vf.robust_unit(bio_reference), "paired reference", "gray"),
        (bio_orientation, "orientation", None),
        (bio_coherence, "coherence", "viridis"),
        (vf.robust_unit(fmd_input), "FMD input", "gray"),
        (fmd_orientation, "orientation", None),
        (fmd_coherence, "coherence", "viridis"),
    ]
    coherence_mappable = None
    coherence_axis = None
    for index, (data, label, cmap) in enumerate(displays):
        ax = fig.add_subplot(top[0, index])
        coherence = label == "coherence"
        image = compact_image(ax, data, label, cmap=cmap, vmin=0.0 if coherence else None, vmax=1.0 if coherence else None)
        if coherence:
            coherence_mappable = image
            coherence_axis = ax
        if index == 0:
            panel(ax, "a", inside=True)
    color_axis = coherence_axis.inset_axes([0.18, -0.075, 0.64, 0.022])
    colorbar = fig.colorbar(coherence_mappable, cax=color_axis, orientation="horizontal")
    colorbar.set_ticks([0, 1])
    colorbar.ax.tick_params(labelsize=5.5, length=1.2, pad=0.8)
    colorbar.outline.set_linewidth(0.35)

    ax = fig.add_subplot(gs[1, :4])
    panel(ax, "b")
    clean_rows = sorted(
        [
            row
            for row in biosr_rows
            if row["reference_group_id"] == "F-actin_linear|Cell_024"
            and "level_01" in str(row["pair_id"])
            and row["endpoint_family"] == "tensor_coherence"
            and row["metadata"]["degradation_id"] == "clean"
        ],
        key=lambda row: float(row["requested_scale_um"]),
    )
    scales = np.array([float(row["requested_scale_um"]) for row in clean_rows])
    reference = np.array([float(row["reference"]) for row in clean_rows])
    estimate = np.array([float(row["estimate"]) for row in clean_rows])
    ax.plot(scales, reference, "o-", color=INK, linewidth=1.5, markersize=3.4, label="reference")
    ax.plot(scales, estimate, "o-", color=TEAL, linewidth=1.8, markersize=3.4, label="NOSTOS")
    ax.fill_between(scales, reference, estimate, color=TEAL_LIGHT, alpha=0.35, linewidth=0)
    ax.set(xlabel="physical scale (µm)", ylabel="coherence", xlim=(0.20, 1.04), ylim=(0.40, 0.56))
    ax.legend(loc="lower right")
    clean_axes(ax)

    ax = fig.add_subplot(gs[1, 4:7])
    panel(ax, "c")
    support_matrix(ax, supported)

    ax = fig.add_subplot(gs[1, 7:])
    panel(ax, "d")
    measurement_rail(ax, fmd_input, fmd_orientation, supported)
    return sm.save_figure(fig, "figure_1_measurement_contract")


def figure2(
    biosr: Mapping[str, Any],
    biosr_rows: Sequence[Mapping[str, Any]],
    receipt: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = vf.biosr_eligible(biosr_rows)
    evaluation = receipt["confirmation_evaluation"]
    full = evaluation["full_contract"]
    qc = evaluation["conventional_acquisition_qc"]
    assert (len(rows), full["accepted"], full["invalid"], qc["invalid"]) == (980, 931, 36, 72)

    clean = vf.center_crop(biosr["clean"], 430)
    reference = vf.center_crop(biosr["reference"], 860)
    blur = vf.center_crop(biosr["degraded"]["blur_4px"], 430)
    clean_rgb, _ = vf.orientation_rgb(clean, sigma=3.0)
    blur_rgb, _ = vf.orientation_rgb(blur, sigma=3.0)

    fig = plt.figure(figsize=(7.08, 4.25))
    fig.subplots_adjust(left=0.080, right=0.99, top=0.975, bottom=0.105, hspace=0.24, wspace=0.52)
    gs = fig.add_gridspec(2, 12, height_ratios=[1.18, 1.28])
    images = gs[0, :].subgridspec(1, 5, wspace=0.035)
    displays = [
        (vf.robust_unit(reference), "reference", "gray"),
        (vf.robust_unit(clean), "input", "gray"),
        (clean_rgb, "orientation", None),
        (vf.robust_unit(blur), "blur 4 px", "gray"),
        (blur_rgb, "orientation", None),
    ]
    for index, (data, label, cmap) in enumerate(displays):
        ax = fig.add_subplot(images[0, index])
        compact_image(ax, data, label, cmap=cmap)
        if index == 0:
            panel(ax, "a", inside=True)

    ax = fig.add_subplot(gs[1, :5])
    panel(ax, "b")
    y = np.arange(len(sm.CONDITION_ORDER))
    valid_fraction, invalid_fraction, abstain_fraction = [], [], []
    for condition in sm.CONDITION_ORDER:
        subset = [row for row in rows if row["metadata"]["degradation_id"] == condition]
        valid = sum(vf.biosr_accept(row, "full_contract") and not row["invalid"] for row in subset)
        invalid = sum(vf.biosr_accept(row, "full_contract") and row["invalid"] for row in subset)
        valid_fraction.append(valid / len(subset))
        invalid_fraction.append(invalid / len(subset))
        abstain_fraction.append(1.0 - (valid + invalid) / len(subset))
    ax.barh(y, valid_fraction, height=0.67, color=TEAL, label="valid")
    ax.barh(y, invalid_fraction, left=valid_fraction, height=0.67, color=RED, label="invalid")
    ax.barh(y, abstain_fraction, left=np.array(valid_fraction) + np.array(invalid_fraction), height=0.67, color=LIGHT, label="withheld")
    ax.set_yticks(y, sm.CONDITION_LABELS)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("fraction")
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    clean_axes(ax, grid=False)
    ax.spines["left"].set_visible(False)

    ax = fig.add_subplot(gs[1, 5:8])
    panel(ax, "c")
    groups = sorted({row["reference_group_id"] for row in rows})
    for group in groups:
        subset = [row for row in rows if row["reference_group_id"] == group]
        qc_rows = [row for row in subset if vf.biosr_accept(row, "conventional_acquisition_qc")]
        nt_rows = [row for row in subset if vf.biosr_accept(row, "full_contract")]
        values = [np.mean([row["invalid"] for row in qc_rows]), np.mean([row["invalid"] for row in nt_rows])]
        ax.plot([0, 1], values, color=LIGHT, linewidth=1.0, zorder=1)
        ax.scatter([0, 1], values, color=[BLUE, TEAL], s=21, edgecolor=WHITE, linewidth=0.45, zorder=3)
    ax.set_xticks([0, 1], ["QC", "NOSTOS"])
    ax.set_ylabel("")
    ax.set_ylim(-0.01, 0.205)
    ax.set_yticks([0, 0.10, 0.20])
    ax.set_xlim(-0.18, 1.18)
    ax.tick_params(axis="x", labelsize=6.2, pad=2)
    clean_axes(ax)

    ax = fig.add_subplot(gs[1, 9:])
    panel(ax, "d")
    qx, qy = vf.tied_risk_curve(vf.biosr_curve_rows(rows, "conventional_acquisition_qc"), "score")
    nx, ny = vf.tied_risk_curve(vf.biosr_curve_rows(rows, "full_contract"), "score")
    ax.plot(qx, qy, color=BLUE, linewidth=1.5, label="QC")
    ax.plot(nx, ny, color=TEAL, linewidth=1.8, label="NOSTOS")
    ax.scatter([qc["coverage"], full["coverage"]], [qc["risk"], full["risk"]], color=[BLUE, TEAL], s=30, edgecolor=WHITE, linewidth=0.5, zorder=4)
    ax.set(xlabel="coverage", ylabel="risk", xlim=(0, 1.015), ylim=(-0.004, 0.105))
    ax.legend(loc="upper left")
    clean_axes(ax)
    return sm.save_figure(fig, "figure_2_biosr_confirmation")


def accepted(row: Mapping[str, Any], threshold: float) -> bool:
    return not bool(row["candidate_hard_abstention"]) and float(row["calibrated_risk"]) <= threshold


def figure3(
    fmd: Mapping[str, Any],
    extension_rows: Sequence[Mapping[str, Any]],
    extension_audit: Mapping[str, Any],
    strict_profile: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    threshold = float(extension_audit["frozen_profile"]["predicted_risk_threshold"])
    focus = [
        row
        for row in extension_rows
        if row["endpoint_family"] == "tensor_coherence"
        and row["metadata"]["acquisition_level"] == "avg8"
        and float(row["requested_scale_value"]) == 16.0
        and accepted(row, threshold)
    ]
    assert (len(focus), sum(bool(row["invalid"]) for row in focus)) == (26, 6)

    fig = plt.figure(figsize=(7.08, 4.05))
    fig.subplots_adjust(left=0.060, right=0.99, top=0.975, bottom=0.105, hspace=0.19, wspace=0.52)
    gs = fig.add_gridspec(2, 15, height_ratios=[1.05, 1.0])
    ladder = gs[0, :].subgridspec(1, 6, wspace=0.035)
    for index, level in enumerate(("raw", "avg2", "avg4", "avg8", "avg16", "avg50")):
        ax = fig.add_subplot(ladder[0, index])
        compact_image(ax, vf.robust_unit(fmd["ladder"][level], 1, 99.5), level.replace("avg", "×"), cmap="gray")
        if index == 0:
            panel(ax, "a", inside=True)

    ax = fig.add_subplot(gs[1, :7])
    panel(ax, "b")
    fields = [3, 12, 6, 8, 4, 2, 10]
    for index, field in enumerate(fields):
        subset = [row for row in focus if int(row["metadata"]["field_of_view"]) == field]
        for repeat_index, row in enumerate(subset):
            jitter = (repeat_index - (len(subset) - 1) / 2) * 0.055
            ax.scatter(index + jitter, float(row["error"]), s=23, color=RED if bool(row["invalid"]) else TEAL, edgecolor=WHITE, linewidth=0.45, zorder=3)
    ax.axhline(0.15, color=RED_DARK, linewidth=0.9, linestyle=(0, (3, 2)))
    ax.set_xticks(range(len(fields)), fields)
    ax.set_xlabel("field")
    ax.set_ylabel("|Δ coherence|")
    ax.set_ylim(0, 0.19)
    ax.set_yticks([0, 0.05, 0.10, 0.15])
    clean_axes(ax)

    matrices = gs[1, 7:11].subgridspec(2, 1, hspace=0.60)
    for index, before in enumerate((True, False)):
        ax = fig.add_subplot(matrices[index, 0])
        if index == 0:
            panel(ax, "c")
        v35.support_strip(ax, before=before)
        ax.text(-0.48, 0, "v1.5" if before else "v1.6", ha="right", va="center", fontweight="bold", fontsize=6.9)

    ax = fig.add_subplot(gs[1, 11:13])
    panel(ax, "d")
    summary = extension_audit["extension"]["field_event_summary"]
    rate = float(summary["field_event_rate"])
    low, high = map(float, summary["field_event_exact_ci"])
    ax.errorbar(rate, 0, xerr=[[rate - low], [high - rate]], fmt="o", color=RED, ecolor=INK, elinewidth=1.1, capsize=3.5, markersize=5)
    ax.set_xlim(-0.03, 0.75)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel("field failure")
    ax.text(rate, 0.23, "2/7", ha="center", color=RED_DARK, fontweight="bold")
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)

    ax = fig.add_subplot(gs[1, 13:])
    panel(ax, "e")
    upper = float(strict_profile["supported_cells"][0]["field_event_summary"]["two_sided_exact_ci95"][1])
    ax.errorbar(0.0, 0, xerr=[[0.0], [upper]], fmt="o", color=TEAL, ecolor=INK, elinewidth=1.1, capsize=3.5, markersize=5)
    ax.set_xlim(-0.03, 0.25)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel("development event")
    ax.text(0.0, 0.23, "0/19", ha="center", color=TEAL, fontweight="bold")
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    return sm.save_figure(fig, "figure_3_falsification_and_repair")


def figure4(
    certified_image: np.ndarray,
    confocal_image: np.ndarray,
    widefield_g_image: np.ndarray,
    external_audit: Mapping[str, Any],
    guard_audit: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    fig = plt.figure(figsize=(7.08, 3.82))
    fig.subplots_adjust(left=0.065, right=0.99, top=0.975, bottom=0.115, hspace=0.20, wspace=0.56)
    gs = fig.add_gridspec(2, 15, height_ratios=[1.30, 0.90])
    top = gs[0, :].subgridspec(1, 6, wspace=0.035)
    sources = [
        (certified_image, "widefield mitochondria"),
        (confocal_image, "confocal mitochondria"),
        (widefield_g_image, "widefield F-actin"),
    ]
    coherence_axes = []
    mappable = None
    for group, (source, label) in enumerate(sources):
        _, coherence = vf.orientation_rgb(source, sigma=4.0)
        ax = fig.add_subplot(top[0, group * 2])
        compact_image(ax, vf.robust_unit(source, 1, 99.5), label, cmap="gray")
        if group == 0:
            panel(ax, "a", inside=True)
        ax = fig.add_subplot(top[0, group * 2 + 1])
        mappable = ax.imshow(coherence, cmap="viridis", vmin=0, vmax=1, interpolation="nearest")
        ax.set_axis_off()
        ax.text(0.5, 1.02, "coherence", transform=ax.transAxes, ha="center", va="bottom", fontweight="bold", fontsize=7.5)
        coherence_axes.append(ax)
    color_axis = coherence_axes[-1].inset_axes([0.18, -0.085, 0.64, 0.025])
    colorbar = fig.colorbar(mappable, cax=color_axis, orientation="horizontal")
    colorbar.set_ticks([0, 1])
    colorbar.ax.tick_params(labelsize=5.8, length=1.5, pad=1)
    colorbar.outline.set_linewidth(0.4)

    ax = fig.add_subplot(gs[1, :7])
    panel(ax, "b")
    source_order = ["Confocal_BPAE_R", "WideField_BPAE_G"]
    summaries = {item["dataset_key"]: item["field_event_summary"] for item in external_audit["per_source"]}
    x = 0
    ticks, labels = [], []
    for source in source_order:
        for field in summaries[source]["fields"]:
            accepted_count = int(field["accepted"])
            invalid_count = int(field["invalid"])
            if accepted_count == 0:
                ax.scatter(x, 0, marker="x", color=MID, s=25, linewidth=1.1)
            else:
                risk = invalid_count / accepted_count
                ax.scatter(x, risk, color=RED if risk else TEAL, s=30, edgecolor=WHITE, linewidth=0.45)
            ticks.append(x)
            labels.append(field["reference_group_id"].split("fov")[-1])
            x += 1
        x += 1
    ax.axhline(0.15, color=RED_DARK, linewidth=0.8, linestyle=(0, (3, 2)))
    ax.axvline(7, color=LIGHT, linewidth=0.8)
    ax.set_xticks(ticks, labels)
    ax.set_xlabel("field")
    ax.set_ylabel("accepted risk")
    ax.set_ylim(-0.08, 1.08)
    clean_axes(ax)

    ax = fig.add_subplot(gs[1, 7:11])
    panel(ax, "c")
    before = guard_audit["external"]["before_guard"]
    after = guard_audit["external"]["after_guard"]
    ax.bar([0, 1], [before["accepted"], after["accepted"]], color=[AMBER, LIGHT], width=0.56)
    ax.bar([0, 1], [before["invalid"], after["invalid"]], color=[RED, RED], width=0.56)
    ax.set_xticks([0, 1], ["unscoped", "guarded"])
    ax.set_ylabel("outputs")
    ax.set_ylim(0, 92)
    ax.text(0, before["accepted"] + 4, f"{before['invalid']}/{before['accepted']}", ha="center", color=RED_DARK, fontweight="bold")
    ax.text(1, 4, "0", ha="center", color=MID, fontweight="bold")
    clean_axes(ax)

    ax = fig.add_subplot(gs[1, 11:])
    panel(ax, "d")
    rows = [
        ("widefield R", True, True),
        ("confocal R", False, False),
        ("widefield G", False, False),
    ]
    ax.set_xlim(-0.2, 2.2)
    ax.set_ylim(-0.6, 2.6)
    for index, (label, in_scope, emit) in enumerate(rows):
        y = 2 - index
        ax.text(-0.08, y, label, ha="right", va="center")
        ax.scatter(0.55, y, s=55, color=TEAL if in_scope else LIGHT, edgecolor=WHITE, linewidth=0.45)
        ax.scatter(1.55, y, s=55, color=TEAL if emit else LIGHT, edgecolor=WHITE, linewidth=0.45)
        ax.text(0.55, y, "●" if in_scope else "×", ha="center", va="center", color=WHITE if in_scope else MID, fontweight="bold")
        ax.text(1.55, y, "●" if emit else "×", ha="center", va="center", color=WHITE if emit else MID, fontweight="bold")
    ax.set_xticks([0.55, 1.55], ["scope", "emit"])
    ax.set_yticks([])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    assert external_audit["status"] == "fail"
    assert before["accepted"] == 84 and before["invalid"] == 36
    assert after["accepted"] == 0 and after["invalid"] == 0
    return sm.save_figure(fig, "figure_4_external_domain_failure")


def build_manifest(
    outputs: Mapping[str, Any],
    sources: Sequence[Path],
    archives: Sequence[Path],
) -> Path:
    payload = {
        "schema_version": "nostos-small-methods-figures/1.3",
        "status": "complete",
        "generated_by": Path(__file__).relative_to(ROOT).as_posix(),
        "generated_by_sha256": sha256(Path(__file__)),
        "declaration": "Every microscopy pixel originates in a cited public BioSR or FMD archive. All maps and summaries are deterministic. No generated microscopy, anatomy, mask, heatmap or numerical result appears.",
        "font": {"family": "Times New Roman", "resolved_path": sm.TIMES_PATH},
        "outputs": outputs,
        "sources": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sources
        ],
        "archives": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in archives
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "small_methods_figures_v36.manifest.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark"))
    args = parser.parse_args()
    paths = {
        "biosr_rows": ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/tensor_cases.jsonl",
        "biosr_receipt": ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/confirmation_receipt.json",
        "v14_rows": ROOT / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_scored.jsonl",
        "v15_rows": ROOT / "outputs/nostos0-fmd-widefield-v1-5-extended-confirmation-audit/extension_scored.jsonl",
        "v15_audit": ROOT / "outputs/nostos0-fmd-widefield-v1-5-extended-confirmation-audit/extended_confirmation_audit.json",
        "strict_profile": ROOT / "outputs/nostos0-fmd-full-archive-strict-support-v1-6-development/strict_support_profile.json",
        "external_rows": ROOT / "outputs/nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1/external_transfer_scored.jsonl",
        "external_audit": ROOT / "outputs/nostos0-fmd-strict-external-transfer-v1-6-audit-v1-6-1/external_transfer_audit.json",
        "guard_audit": ROOT / "outputs/nostos0-fmd-profile-domain-guard-v1-7-development/profile_domain_guard_audit.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    biosr_rows = vf.read_jsonl(paths["biosr_rows"])
    biosr_receipt = read_json(paths["biosr_receipt"])
    v14_rows = vf.read_jsonl(paths["v14_rows"])
    extension_rows = vf.read_jsonl(paths["v15_rows"])
    extension_audit = read_json(paths["v15_audit"])
    strict_profile = read_json(paths["strict_profile"])
    external_rows = vf.read_jsonl(paths["external_rows"])
    external_audit = read_json(paths["external_audit"])
    guard_audit = read_json(paths["guard_audit"])
    biosr = vf.load_biosr_example(args.data_root, biosr_rows)
    widefield_r_archive = args.data_root / "fmd" / "WideField_BPAE_R.tar"
    fmd = vf.load_fmd_images(widefield_r_archive, v14_rows, (1, 5, 14, 20))
    external_root = args.data_root / "fmd" / "external-transfer"
    confocal_archive = external_root / "Confocal_BPAE_R.tar"
    widefield_g_archive = external_root / "WideField_BPAE_G.tar"
    confocal_image, _ = v35.load_external_pair(confocal_archive, external_rows, source_key="Confocal_BPAE_R", field=7)
    widefield_g_image, _ = v35.load_external_pair(widefield_g_archive, external_rows, source_key="WideField_BPAE_G", field=1)
    outputs = {
        "figure_1": figure1(biosr, biosr_rows, fmd, strict_profile),
        "figure_2": figure2(biosr, biosr_rows, biosr_receipt),
        "figure_3": figure3(fmd, extension_rows, extension_audit, strict_profile),
        "figure_4": figure4(fmd["fields"][14]["avg16"], confocal_image, widefield_g_image, external_audit, guard_audit),
        "toc": v35.toc_figure(fmd, strict_profile),
    }
    manifest = build_manifest(outputs, list(paths.values()), [biosr["archive"], widefield_r_archive, confocal_archive, widefield_g_archive])
    print(json.dumps({"status": "complete", "outputs": outputs, "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
