"""Build the NOSTOS Small Methods figure set from frozen public evidence.

The script preserves the v30 analysis and produces a separate, versioned visual
package. All microscopy pixels originate in the cited BioSR and FMD archives;
all maps and summaries are deterministic. The generated ToC graphic contains
the same public microscopy and editable vector shapes. No generated biological
imagery enters any deliverable.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.font_manager import findfont
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image

import build_nostos0_validity_figures as vf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0_small_methods"
BIORENDER_DIR = ROOT / "figures" / "nostos0_biorender"
BIORENDER_ASSETS = {
    "measurement_contract": {
        "path": BIORENDER_DIR / "biorender_measurement_contract_v33_textfree.png",
        "session_id": "a950c5e2-2b4f-45c3-918e-3d449b5ad875",
        "figure_id": "f2e8405964aa5d436a639add",
        "editor_url": "https://app.biorender.com/illustrations/f2e8405964aa5d436a639add?slideId=cdd98e77-dc0f-a51a-a9b8-ab4d2f10f678",
        "role": "illustrative measurement-contract geometry; contains no biological data",
    },
    "hidden_failure": {
        "path": BIORENDER_DIR / "biorender_hidden_failure_v33_textfree.png",
        "session_id": "54f4d9f9-a52e-4273-88a6-11847268efa1",
        "figure_id": "05b085347c02460763c3a4ff",
        "editor_url": "https://app.biorender.com/illustrations/05b085347c02460763c3a4ff?slideId=d6dcfc42-d240-f196-6232-daf2a546b0dc",
        "role": "illustrative failure-localization geometry; contains no biological data",
    },
}

INK = "#17212B"
MID = "#66727E"
LIGHT = "#D7DEE5"
PALE = "#EEF2F5"
TEAL = "#087F8C"
TEAL_LIGHT = "#A5DCDA"
BLUE = "#286BA6"
BLUE_LIGHT = "#B3D0EA"
RED = "#C83E50"
RED_DARK = "#942536"
AMBER = "#D79A24"
WHITE = "#FFFFFF"


def require_times_new_roman() -> str:
    """Return the installed font path and fail instead of substituting."""
    return findfont("Times New Roman", fallback_to_default=False)


TIMES_PATH = require_times_new_roman()
mpl.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "font.size": 8.2,
        "axes.titlesize": 8.6,
        "axes.labelsize": 8.0,
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 7.1,
        "ytick.labelsize": 7.1,
        "legend.fontsize": 7.1,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "svg.hashsalt": "nostos-small-methods-v31",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def panel(ax: mpl.axes.Axes, letter: str) -> None:
    writer = getattr(ax, "text2D", ax.text)
    writer(
        -0.035,
        1.025,
        letter,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=11.5,
        fontweight="bold",
        color=INK,
        clip_on=False,
        zorder=50,
    )


def clean_axes(ax: mpl.axes.Axes, *, grid: bool = True) -> None:
    if grid:
        ax.grid(axis="y", color=PALE, linewidth=0.75, zorder=0)
    ax.spines["left"].set_color(LIGHT)
    ax.spines["bottom"].set_color(LIGHT)
    ax.tick_params(length=2.5, color=LIGHT)


def image_axis(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    label: str,
    *,
    cmap: str | mpl.colors.Colormap | None = "gray",
    label_color: str = INK,
) -> None:
    ax.imshow(image, cmap=cmap, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.text(
        0.5,
        1.025,
        label,
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8.2,
        fontweight="bold",
        color=label_color,
    )


def save_figure(fig: plt.Figure, stem: str) -> dict[str, dict[str, Any]]:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict[str, Any]] = {}
    for suffix, kwargs in (
        ("png", {"dpi": 600, "metadata": {"Software": "NOSTOS"}}),
        (
            "pdf",
            {
                "metadata": {
                    "Creator": "NOSTOS",
                    "Producer": "Matplotlib",
                    "CreationDate": None,
                    "ModDate": None,
                }
            },
        ),
        ("svg", {"metadata": {"Creator": "NOSTOS", "Date": None}}),
    ):
        path = OUT / f"{stem}.{suffix}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.035, **kwargs)
        outputs[suffix] = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    plt.close(fig)
    return outputs


def load_biorender_asset(path: Path, *, padding: int = 18) -> np.ndarray:
    """Load and tightly crop a BioRender schematic while preserving white space."""
    if not path.exists():
        raise FileNotFoundError(f"Missing BioRender asset: {path}")
    with Image.open(path) as source:
        rgb = np.asarray(source.convert("RGB"))
    # BioRender exports include a broad near-white shadow field. A stricter
    # threshold removes that field while preserving every schematic glyph.
    content = np.any(rgb < 244, axis=2)
    y, x = np.where(content)
    if not len(x):
        raise RuntimeError(f"BioRender asset has no visible content: {path}")
    x0 = max(0, int(x.min()) - padding)
    x1 = min(rgb.shape[1], int(x.max()) + padding + 1)
    y0 = max(0, int(y.min()) - padding)
    y1 = min(rgb.shape[0], int(y.max()) + padding + 1)
    return rgb[y0:y1, x0:x1]


def draw_measurement_contract(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    orientation: np.ndarray,
    supported: set[tuple[str, float]],
) -> None:
    """Compose the contract from authentic pixels and deterministic geometry."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    boxes = ((0.02, 0.17, 0.17, 0.66), (0.27, 0.17, 0.17, 0.66))
    for (x, y, width, height), content, cmap in (
        (boxes[0], vf.robust_unit(image), "gray"),
        (boxes[1], orientation, None),
    ):
        inset = ax.inset_axes([x, y, width, height])
        inset.imshow(content, cmap=cmap, interpolation="nearest")
        inset.set_xticks([])
        inset.set_yticks([])
        for spine in inset.spines.values():
            spine.set_visible(False)
    ax.text(0.105, 0.08, "image", ha="center", va="center", fontweight="bold")
    ax.text(0.355, 0.08, "measure", ha="center", va="center", fontweight="bold")
    for x0, x1 in ((0.195, 0.265), (0.445, 0.515), (0.735, 0.805)):
        ax.add_patch(FancyArrowPatch((x0, 0.50), (x1, 0.50), arrowstyle="-|>", mutation_scale=9, lw=0.9, color=MID))

    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    grid_x, grid_y, cell = 0.52, 0.20, 0.055
    for row, acquisition in enumerate(acquisitions):
        for column, scale in enumerate(scales):
            face = TEAL if (acquisition, scale) in supported else "#E3E8EC"
            ax.add_patch(Rectangle((grid_x + column * cell, grid_y + (4 - row) * cell), cell, cell, facecolor=face, edgecolor=WHITE, lw=0.6))
    ax.text(grid_x + 1.5 * cell, 0.08, "support", ha="center", va="center", fontweight="bold")

    for y, label, face, edge, color in (
        (0.61, "emit", "#D8EFEE", TEAL, TEAL),
        (0.27, "abstain", "#F1F3F5", "#AAB3BA", MID),
    ):
        ax.add_patch(FancyBboxPatch((0.81, y - 0.12), 0.16, 0.24, boxstyle="round,pad=0.01,rounding_size=0.025", facecolor=face, edgecolor=edge, lw=1.2))
        ax.text(0.89, y, label, ha="center", va="center", color=color, fontweight="bold")


def draw_failure_localization(ax: mpl.axes.Axes, pooled: Mapping[str, Any]) -> None:
    """Show the failure-repair sequence as data, not decorative clip art."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    accepted = int(pooled["accepted"])
    eligible = int(pooled["eligible"])
    bar_y = 0.64
    ax.add_patch(Rectangle((0.03, bar_y), 0.25, 0.10, facecolor=PALE, edgecolor="none"))
    ax.add_patch(Rectangle((0.03, bar_y), 0.25 * accepted / eligible, 0.10, facecolor=AMBER, edgecolor="none"))
    ax.text(0.155, 0.82, "pooled", ha="center", va="center", fontweight="bold")
    ax.text(0.155, 0.52, f"{accepted}/{eligible}", ha="center", va="center", color=AMBER, fontweight="bold")
    ax.add_patch(FancyArrowPatch((0.30, 0.69), (0.39, 0.69), arrowstyle="-|>", mutation_scale=9, lw=0.9, color=MID))

    for index in range(4):
        ax.add_patch(Circle((0.43 + 0.065 * (index % 2), 0.65 + 0.13 * (index // 2)), 0.023, facecolor=RED, edgecolor=WHITE, lw=0.4))
    ax.text(0.462, 0.91, "unsafe cell", ha="center", va="center", fontweight="bold")
    ax.text(0.462, 0.47, "4/4 invalid", ha="center", va="center", color=RED_DARK, fontweight="bold")
    ax.add_patch(FancyArrowPatch((0.56, 0.69), (0.65, 0.69), arrowstyle="-|>", mutation_scale=9, lw=0.9, color=MID))

    for index in range(4):
        ax.add_patch(Circle((0.70 + 0.065 * (index % 2), 0.65 + 0.13 * (index // 2)), 0.023, facecolor=LIGHT, edgecolor=WHITE, lw=0.4))
    ax.text(0.732, 0.91, "repair", ha="center", va="center", fontweight="bold")
    ax.text(0.732, 0.47, "4 abstained", ha="center", va="center", color=MID, fontweight="bold")
    ax.add_patch(FancyArrowPatch((0.83, 0.69), (0.90, 0.69), arrowstyle="-|>", mutation_scale=9, lw=0.9, color=MID))
    ax.add_patch(FancyBboxPatch((0.90, 0.57), 0.08, 0.24, boxstyle="round,pad=0.008,rounding_size=0.02", facecolor="#D8EFEE", edgecolor=TEAL, lw=1.1))
    ax.text(0.94, 0.69, "0", ha="center", va="center", color=TEAL, fontsize=10, fontweight="bold")


def draw_pipeline(ax: mpl.axes.Axes) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    labels = ["image", "measure", "profile", "decision"]
    colors = [INK, BLUE, AMBER, TEAL]
    centers = [0.09, 0.36, 0.63, 0.88]
    widths = [0.16, 0.18, 0.18, 0.17]
    for i, (x, width, label, color) in enumerate(zip(centers, widths, labels, colors, strict=True)):
        face = color if i in {0, 3} else WHITE
        box = FancyBboxPatch(
            (x - width / 2, 0.32),
            width,
            0.34,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            facecolor=face,
            edgecolor=color,
            linewidth=1.35,
        )
        ax.add_patch(box)
        ax.text(
            x,
            0.49,
            label,
            ha="center",
            va="center",
            fontsize=8.7,
            fontweight="bold",
            color=WHITE if i in {0, 3} else color,
        )
        if i < 3:
            ax.add_patch(
                FancyArrowPatch(
                    (x + width / 2 + 0.01, 0.49),
                    (centers[i + 1] - widths[i + 1] / 2 - 0.01, 0.49),
                    arrowstyle="-|>",
                    mutation_scale=10,
                    linewidth=1.0,
                    color=MID,
                )
            )
    ax.annotate(
        "emit",
        xy=(0.88, 0.69),
        xytext=(0.88, 0.88),
        ha="center",
        va="center",
        color=TEAL,
        fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=1.0),
    )
    ax.annotate(
        "abstain",
        xy=(0.88, 0.30),
        xytext=(0.88, 0.10),
        ha="center",
        va="center",
        color=RED,
        fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.0),
    )


def draw_support_lattice(
    ax: mpl.axes.Axes,
    supported: set[tuple[str, float]],
    *,
    failed: tuple[str, float] | None = None,
) -> None:
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    matrix = np.asarray([[1 if (a, s) in supported else 0 for s in scales] for a in acquisitions])
    rgba = np.zeros((*matrix.shape, 4), dtype=float)
    rgba[matrix == 1] = mpl.colors.to_rgba(TEAL)
    rgba[matrix == 0] = mpl.colors.to_rgba("#E3E8EC")
    if failed is not None:
        i = acquisitions.index(failed[0])
        j = scales.index(float(failed[1]))
        rgba[i, j] = mpl.colors.to_rgba(RED)
    ax.imshow(rgba, aspect="auto")
    ax.set_xticks(range(3), ["4", "8", "16"])
    ax.set_yticks(range(5), ["raw", "2", "4", "8", "16"])
    ax.set_xlabel("scale (px)")
    ax.set_ylabel("captures")
    for i, a in enumerate(acquisitions):
        for j, s in enumerate(scales):
            mark = "●" if matrix[i, j] else "×"
            color = WHITE if matrix[i, j] else MID
            if failed == (a, s):
                mark, color = "×", WHITE
            ax.text(j, i, mark, ha="center", va="center", color=color, fontsize=10, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def draw_mini_outputs(ax: mpl.axes.Axes) -> None:
    ax.set_xlim(-0.4, 7.4)
    ax.set_ylim(-0.6, 4.9)
    ax.axis("off")
    states = [TEAL, TEAL, TEAL, TEAL, LIGHT, TEAL, LIGHT, RED] * 4
    for i, color in enumerate(states):
        x, y = i % 8, 3 - i // 8
        ax.add_patch(Circle((x, y), 0.30, facecolor=color, edgecolor=WHITE, linewidth=0.45))
    ax.text(1.25, 4.25, "emit", ha="center", va="bottom", color=TEAL, fontweight="bold")
    ax.text(4.0, 4.25, "abstain", ha="center", va="bottom", color=MID, fontweight="bold")
    ax.text(6.65, 4.25, "blocked", ha="center", va="bottom", color=RED, fontweight="bold")


def figure1(
    biosr: Mapping[str, Any],
    biosr_rows: Sequence[Mapping[str, Any]],
    fmd: Mapping[str, Any],
    conditional_development: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    bio_input = vf.center_crop(biosr["clean"], 430)
    bio_ref = vf.center_crop(biosr["reference"], 860)
    bio_map, _ = vf.orientation_rgb(bio_input, sigma=3.0)
    fmd_input = vf.center_crop(fmd["ladder"]["avg8"], 430)
    fmd_map, _ = vf.orientation_rgb(fmd_input, sigma=2.0)
    fmd_fft = vf.fft_power(fmd_input)

    fig = plt.figure(figsize=(7.08, 5.38))
    fig.subplots_adjust(left=0.065, right=0.985, top=0.975, bottom=0.075, hspace=0.28, wspace=0.48)
    gs = fig.add_gridspec(3, 12, height_ratios=[1.00, 0.66, 1.20])

    top = gs[0, :].subgridspec(1, 6, wspace=0.035)
    displays = [
        (vf.robust_unit(bio_input), "BioSR", "gray"),
        (vf.robust_unit(bio_ref), "reference", "gray"),
        (bio_map, "orientation", None),
        (vf.robust_unit(fmd_input), "FMD", "gray"),
        (fmd_map, "orientation", None),
        (vf.robust_unit(fmd_fft), "Fourier power", "magma"),
    ]
    for i, (data, label, cmap) in enumerate(displays):
        ax = fig.add_subplot(top[0, i])
        image_axis(ax, data, label, cmap=cmap)
        if i == 0:
            panel(ax, "a")

    ax = fig.add_subplot(gs[1, :])
    panel(ax, "b")
    draw_measurement_contract(ax, fmd_input, fmd_map, {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in conditional_development["supported_cells"]
    })

    ax = fig.add_subplot(gs[2, :4])
    panel(ax, "c")
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
    if len(clean_rows) != 5:
        raise RuntimeError(f"Expected five frozen BioSR scale-response rows, found {len(clean_rows)}")
    scales = np.asarray([float(row["requested_scale_um"]) for row in clean_rows])
    reference = np.asarray([float(row["reference"]) for row in clean_rows])
    measurement = np.asarray([float(row["estimate"]) for row in clean_rows])
    ax.plot(scales, reference, "o-", color=INK, lw=1.7, ms=3.8, label="reference")
    ax.plot(scales, measurement, "o-", color=TEAL, lw=1.9, ms=3.8, label="measurement")
    ax.fill_between(scales, reference, measurement, color=TEAL_LIGHT, alpha=0.42, linewidth=0)
    ax.set(xlabel="physical scale (µm)", ylabel="tensor coherence", xlim=(0.20, 1.04), ylim=(0.40, 0.56))
    ax.legend(loc="lower right")
    clean_axes(ax)

    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in conditional_development["supported_cells"]
    }
    ax = fig.add_subplot(gs[2, 4:8])
    panel(ax, "d")
    draw_support_lattice(ax, supported)

    ax = fig.add_subplot(gs[2, 8:])
    panel(ax, "e")
    draw_mini_outputs(ax)

    return save_figure(fig, "figure_1_measurement_to_decision")


CONDITION_ORDER = [
    "clean",
    "gamma_0_5",
    "gamma_2_0",
    "blur_1px",
    "blur_2px",
    "blur_4px",
    "blur_8px",
    "anisotropic_y_0_5_x_3",
    "anisotropic_y_3_x_0_5",
    "noise_0_03",
    "noise_0_08",
    "noise_0_15",
    "resample_2x",
    "resample_4x",
]
CONDITION_LABELS = [
    "clean",
    "γ 0.5",
    "γ 2",
    "blur 1",
    "blur 2",
    "blur 4",
    "blur 8",
    "aniso x",
    "aniso y",
    "noise .03",
    "noise .08",
    "noise .15",
    "resize 2",
    "resize 4",
]


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

    fig = plt.figure(figsize=(7.08, 4.95))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.975, bottom=0.09, hspace=0.25, wspace=0.65)
    gs = fig.add_gridspec(2, 12, height_ratios=[1.0, 1.45])
    image_grid = gs[0, :].subgridspec(1, 5, wspace=0.035)
    displays = [
        (vf.robust_unit(reference), "reference", "gray"),
        (vf.robust_unit(clean), "input", "gray"),
        (clean_rgb, "orientation", None),
        (vf.robust_unit(blur), "blurred", "gray"),
        (blur_rgb, "orientation", None),
    ]
    for i, (data, label, cmap) in enumerate(displays):
        ax = fig.add_subplot(image_grid[0, i])
        image_axis(ax, data, label, cmap=cmap)
        if i == 0:
            panel(ax, "a")

    lower = gs[1, :].subgridspec(1, 3, width_ratios=[1.72, 0.82, 1.28], wspace=0.42)

    ax = fig.add_subplot(lower[0, 0])
    panel(ax, "b")
    y = np.arange(len(CONDITION_ORDER))
    valid_frac, invalid_frac, abstain_frac = [], [], []
    for condition in CONDITION_ORDER:
        subset = [row for row in rows if row["metadata"]["degradation_id"] == condition]
        valid = sum(vf.biosr_accept(row, "full_contract") and not row["invalid"] for row in subset)
        invalid = sum(vf.biosr_accept(row, "full_contract") and row["invalid"] for row in subset)
        abstain = len(subset) - valid - invalid
        valid_frac.append(valid / len(subset))
        invalid_frac.append(invalid / len(subset))
        abstain_frac.append(abstain / len(subset))
    ax.barh(y, valid_frac, color=TEAL, height=0.68, label="valid")
    ax.barh(y, invalid_frac, left=valid_frac, color=RED, height=0.68, label="invalid")
    ax.barh(y, abstain_frac, left=np.asarray(valid_frac) + np.asarray(invalid_frac), color=LIGHT, height=0.68, label="abstain")
    ax.set_yticks(y, CONDITION_LABELS)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("fraction")
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    clean_axes(ax, grid=False)
    ax.spines["left"].set_visible(False)

    ax = fig.add_subplot(lower[0, 1])
    panel(ax, "c")
    groups = sorted({row["reference_group_id"] for row in rows})
    for group in groups:
        subset = [row for row in rows if row["reference_group_id"] == group]
        qc_rows = [row for row in subset if vf.biosr_accept(row, "conventional_acquisition_qc")]
        nt_rows = [row for row in subset if vf.biosr_accept(row, "full_contract")]
        values = [np.mean([row["invalid"] for row in qc_rows]), np.mean([row["invalid"] for row in nt_rows])]
        ax.plot([0, 1], values, color=LIGHT, lw=1.2, zorder=1)
        ax.scatter([0], [values[0]], color=BLUE, s=24, edgecolor=WHITE, linewidth=0.5, zorder=3)
        ax.scatter([1], [values[1]], color=TEAL, s=24, edgecolor=WHITE, linewidth=0.5, zorder=3)
    ax.set_xticks([0, 1], ["QC", "NOSTOS"])
    ax.set_ylabel("invalid fraction", labelpad=1)
    ax.set_ylim(-0.01, 0.205)
    ax.set_yticks([0.00, 0.10, 0.20])
    clean_axes(ax)

    ax = fig.add_subplot(lower[0, 2])
    panel(ax, "d")
    full_curve = vf.biosr_curve_rows(rows, "full_contract")
    qc_curve = vf.biosr_curve_rows(rows, "conventional_acquisition_qc")
    qx, qy = vf.tied_risk_curve(qc_curve, "score")
    nx, ny = vf.tied_risk_curve(full_curve, "score")
    ax.plot(qx, qy, color=BLUE, lw=1.6, label="QC")
    ax.plot(nx, ny, color=TEAL, lw=1.9, label="NOSTOS")
    ax.scatter([qc["coverage"]], [qc["risk"]], color=BLUE, s=34, edgecolor=WHITE, linewidth=0.6, zorder=4)
    ax.scatter([full["coverage"]], [full["risk"]], color=TEAL, s=34, edgecolor=WHITE, linewidth=0.6, zorder=4)
    ax.set(xlabel="coverage", ylabel="selective risk", xlim=(0, 1.015), ylim=(-0.004, 0.105))
    ax.legend(loc="upper left")
    clean_axes(ax)
    ax.text(0.97, 0.092, "36/49 invalid", ha="right", va="top", color=RED, fontweight="bold")
    ax.text(0.97, 0.081, "NOSTOS-only rejections", ha="right", va="top", color=MID, fontsize=6.9)

    return save_figure(fig, "figure_2_biosr_confirmation")


def draw_cell_matrix(
    ax: mpl.axes.Axes,
    coverage: np.ndarray,
    risk: np.ndarray,
    invalid: np.ndarray,
    *,
    label: str,
) -> None:
    acquisitions = ["raw", "2", "4", "8", "16"]
    scales = ["4", "8", "16"]
    rgba = np.zeros((*coverage.shape, 4), dtype=float)
    for i in range(coverage.shape[0]):
        for j in range(coverage.shape[1]):
            if coverage[i, j] == 0:
                rgba[i, j] = mpl.colors.to_rgba("#E5EAED")
            elif risk[i, j] >= 0.99:
                rgba[i, j] = mpl.colors.to_rgba(RED_DARK)
            elif risk[i, j] > 0:
                rgba[i, j] = mpl.colors.to_rgba(RED)
            else:
                rgba[i, j] = mpl.colors.to_rgba(TEAL_LIGHT)
    ax.imshow(rgba, aspect="auto")
    ax.set_xticks(range(3), scales)
    ax.set_yticks(range(5), acquisitions)
    ax.set_xlabel("scale (px)")
    ax.set_ylabel("captures")
    ax.text(0.5, 1.025, label, transform=ax.transAxes, ha="center", va="bottom", fontweight="bold")
    for i in range(5):
        for j in range(3):
            if coverage[i, j] == 0:
                text, color = "×", MID
            else:
                text = f"{invalid[i, j]}\n{risk[i, j]:.0%}"
                color = WHITE if risk[i, j] > 0.35 else INK
            ax.text(j, i, text, ha="center", va="center", color=color, fontsize=6.6, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def figure3(
    fmd: Mapping[str, Any],
    development_rows: Sequence[Mapping[str, Any]],
    confirmation_rows: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    threshold = float(audit["primary_operating_point"]["predicted_risk_threshold"])
    dev_cov, dev_risk, dev_invalid = vf.cell_matrix(
        development_rows,
        threshold=threshold,
        acceptance=lambda row, value: vf.v13_accept(row, value, development=True),
    )
    con_cov, con_risk, con_invalid = vf.cell_matrix(
        confirmation_rows,
        threshold=threshold,
        acceptance=lambda row, value: vf.v13_accept(row, value, development=False),
    )
    assert int(con_invalid[3, 1]) == 4 and np.isclose(con_risk[3, 1], 1.0)

    fig = plt.figure(figsize=(7.08, 4.55))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.975, bottom=0.09, hspace=0.28, wspace=0.65)
    gs = fig.add_gridspec(2, 12, height_ratios=[0.92, 1.35])
    ladder_grid = gs[0, :].subgridspec(1, 6, wspace=0.035)
    for i, level in enumerate(("raw", "avg2", "avg4", "avg8", "avg16", "avg50")):
        ax = fig.add_subplot(ladder_grid[0, i])
        image_axis(ax, vf.robust_unit(fmd["ladder"][level], 1, 99.5), level.replace("avg", "×"), cmap="gray")
        if i == 0:
            panel(ax, "a")

    lower = gs[1, :].subgridspec(1, 3, width_ratios=[1.0, 1.0, 1.28], wspace=0.30)

    ax = fig.add_subplot(lower[0, 0])
    panel(ax, "b")
    draw_cell_matrix(ax, dev_cov, dev_risk, dev_invalid, label="development")
    ax.add_patch(Rectangle((0.5, 2.5), 1, 1, fill=False, edgecolor=RED_DARK, linewidth=2.2))

    ax = fig.add_subplot(lower[0, 1])
    panel(ax, "c")
    draw_cell_matrix(ax, con_cov, con_risk, con_invalid, label="untouched")
    ax.set_ylabel("")
    ax.add_patch(Rectangle((0.5, 2.5), 1, 1, fill=False, edgecolor=RED_DARK, linewidth=2.2))

    ax = fig.add_subplot(lower[0, 2])
    panel(ax, "d")
    pooled = audit["primary_operating_point"]
    draw_failure_localization(ax, pooled)

    return save_figure(fig, "figure_3_hidden_conditional_failure")


def draw_waffle(ax: mpl.axes.Axes, invalid: int, total: int, label: str, valid_color: str) -> None:
    cols = 8
    rows = int(np.ceil(total / cols))
    for i in range(total):
        x, y = i % cols, rows - 1 - i // cols
        color = RED if i < invalid else valid_color
        ax.add_patch(Circle((x, y), 0.31, facecolor=color, edgecolor=WHITE, linewidth=0.45))
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(-1.55, rows - 0.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text((cols - 1) / 2, rows - 0.10, label, ha="center", va="bottom", fontweight="bold")
    ax.text((cols - 1) / 2, -1.0, f"{invalid}/{total} invalid", ha="center", va="center", color=RED if invalid else TEAL, fontweight="bold")


def figure4(
    fmd: Mapping[str, Any],
    scored_rows: Sequence[Mapping[str, Any]],
    development_audit: Mapping[str, Any],
    confirmation_audit: Mapping[str, Any],
    finite_sample: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    threshold = float(confirmation_audit["primary_operating_point"]["predicted_risk_threshold"])
    accepted = [row for row in scored_rows if vf.conditional_accept(row, threshold)]
    assert (len(accepted), sum(bool(row["invalid"]) for row in accepted)) == (64, 0)

    fig = plt.figure(figsize=(7.08, 5.82))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.975, bottom=0.08, hspace=0.40, wspace=0.68)
    gs = fig.add_gridspec(3, 16, height_ratios=[0.90, 1.12, 1.18])

    for i, field in enumerate((1, 5, 14, 20)):
        ax = fig.add_subplot(gs[0, i * 4 : (i + 1) * 4])
        image_axis(ax, vf.robust_unit(fmd["fields"][field]["avg16"], 1, 99.5), f"field {field}", cmap="gray")
        if i == 0:
            panel(ax, "a")

    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in development_audit["supported_cells"]
    }
    ax = fig.add_subplot(gs[1, :4])
    panel(ax, "b")
    draw_support_lattice(ax, supported)

    supported_keys = [cell["key"] for cell in development_audit["supported_cells"]]
    fields = [1, 5, 14, 20]
    emission = np.zeros((4, 4), dtype=int)
    for i, field in enumerate(fields):
        for j, key in enumerate(supported_keys):
            emission[i, j] = sum(
                1
                for row in accepted
                if int(row["metadata"]["field_of_view"]) == field
                and str(row["conditional_cell"]["key"]) == key
            )
    ax = fig.add_subplot(gs[1, 4:8])
    panel(ax, "c")
    ax.imshow(emission, cmap=mpl.colors.LinearSegmentedColormap.from_list("emit", [PALE, TEAL]), vmin=0, vmax=4, aspect="auto")
    ax.set_xticks(range(4), ["16·16", "16·4", "16·8", "8·16"], rotation=30, ha="right")
    ax.set_yticks(range(4), fields)
    ax.set_xlabel("capture · scale")
    ax.set_ylabel("field")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, emission[i, j], ha="center", va="center", color=WHITE, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    waffles = gs[1, 8:].subgridspec(1, 2, wspace=0.18)
    ax = fig.add_subplot(waffles[0, 0])
    panel(ax, "d")
    draw_waffle(ax, 31, 64, "acquisition QC", BLUE_LIGHT)
    ax = fig.add_subplot(waffles[0, 1])
    draw_waffle(ax, 0, 64, "NOSTOS", TEAL_LIGHT)

    ax = fig.add_subplot(gs[2, :7])
    panel(ax, "e")
    primary_curve = [{"case_id": row["case_id"], "invalid": row["invalid"], "score": float(row["calibrated_risk"])} for row in scored_rows]
    qc_curve = [{"case_id": row["case_id"], "invalid": row["invalid"], "score": float(row["acquisition_qc_calibrated_risk"])} for row in scored_rows]
    qx, qy = vf.tied_risk_curve(qc_curve, "score")
    nx, ny = vf.tied_risk_curve(primary_curve, "score")
    ax.plot(qx, qy, color=BLUE, lw=1.7, label="acquisition QC")
    ax.plot(nx, ny, color=TEAL, lw=2.0, label="hierarchical NOSTOS")
    ax.scatter([64 / 240], [0], color=TEAL, edgecolor=WHITE, linewidth=0.6, s=38, zorder=4)
    ax.set(xlabel="coverage", ylabel="selective risk", xlim=(0, 1.015), ylim=(-0.015, 0.82))
    ax.legend(loc="upper left")
    clean_axes(ax)

    bootstrap = confirmation_audit["risk_coverage"]["cluster_bootstrap_aurc_difference"]
    observed = float(bootstrap["observed"])
    low, high = map(float, bootstrap["bootstrap_ci95"])
    ax = fig.add_subplot(gs[2, 7:11])
    panel(ax, "f")
    ax.errorbar(observed, 0.62, xerr=[[observed - low], [high - observed]], fmt="o", color=TEAL, ecolor=INK, elinewidth=1.4, capsize=4, markersize=6)
    ax.axvline(0, color=RED, lw=0.9, ls=":")
    ax.text(observed, 0.83, f"{observed:.3f}", ha="center", va="bottom", color=TEAL, fontweight="bold", fontsize=10)
    ax.text(observed, 0.40, "QC − NOSTOS", ha="center", va="top", color=MID)
    ax.set_xlim(-0.05, 0.48)
    ax.set_ylim(0.18, 1.02)
    ax.set_yticks([])
    ax.set_xlabel("AURC difference")
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)

    measurement_upper = float(finite_sample["nested_measurement_interval"]["clopper_pearson_95"][1])
    field_upper = float(finite_sample["independent_group_any_failure_interval"]["clopper_pearson_95"][1])
    ax = fig.add_subplot(gs[2, 11:])
    panel(ax, "g")
    ax.hlines([1, 0], [0, 0], [measurement_upper, field_upper], color=[TEAL, AMBER], linewidth=6, alpha=0.85)
    ax.scatter([measurement_upper, field_upper], [1, 0], color=[TEAL, AMBER], s=38, edgecolor=WHITE, linewidth=0.5, zorder=3)
    ax.text(measurement_upper, 1.18, f"≤ {measurement_upper:.1%}", ha="center", color=TEAL, fontweight="bold")
    ax.text(field_upper, 0.18, f"≤ {field_upper:.1%}", ha="center", color=AMBER, fontweight="bold")
    ax.set_yticks([0, 1], ["4 fields", "64 measures"])
    ax.set_xlim(0, 0.68)
    ax.set_ylim(-0.42, 1.42)
    ax.set_xlabel("exact 95% upper bound")
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    ax.tick_params(axis="y", length=0)

    return save_figure(fig, "figure_4_hierarchical_confirmation")


def data_url(array: np.ndarray, *, cmap: str | None = "gray") -> str:
    if array.ndim == 2:
        unit = vf.robust_unit(array)
        if cmap == "gray":
            rgb = np.repeat((unit[..., None] * 255).astype(np.uint8), 3, axis=2)
        else:
            rgb = (plt.get_cmap(cmap)(unit)[..., :3] * 255).astype(np.uint8)
    else:
        rgb = np.clip(array * 255, 0, 255).astype(np.uint8)
    image = Image.fromarray(rgb).resize((300, 300), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def build_toc_drawio(fmd: Mapping[str, Any], development_audit: Mapping[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    image = vf.center_crop(fmd["ladder"]["avg8"], 430)
    orientation, _ = vf.orientation_rgb(image, sigma=2.0)
    image_uri = data_url(image)
    map_uri = data_url(orientation, cmap=None)
    cells: list[str] = []

    def vertex(identifier: str, value: str, style: str, x: float, y: float, w: float, h: float) -> None:
        cells.append(
            f'<mxCell id="{identifier}" value="{escape(value)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
            "</mxCell>"
        )

    def edge(identifier: str, source: str, target: str, color: str) -> None:
        cells.append(
            f'<mxCell id="{identifier}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;'
            f'html=1;strokeColor={color};strokeWidth=2;endArrow=block;endFill=1;" edge="1" parent="1" source="{source}" target="{target}">'
            '<mxGeometry relative="1" as="geometry"/>'
            "</mxCell>"
        )

    label_style = "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;fontFamily=Times New Roman;fontSize=11;fontStyle=1;fontColor=#17212B;"
    image_style = "shape=image;verticalLabelPosition=bottom;verticalAlign=top;imageAspect=0;aspect=fixed;image="
    vertex("img", "", image_style + image_uri + ";", 12, 22, 88, 88)
    vertex("map", "", image_style + map_uri + ";", 142, 22, 88, 88)
    vertex("img-label", "image", label_style, 25, 2, 62, 18)
    vertex("map-label", "measure", label_style, 152, 2, 68, 18)

    grid_x, grid_y, cell = 275, 25, 17
    supported = {
        (str(item["values"][0]), float(item["values"][1]))
        for item in development_audit["supported_cells"]
    }
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    for i, acq in enumerate(acquisitions):
        for j, scale in enumerate(scales):
            color = TEAL if (acq, scale) in supported else "#E3E8EC"
            if (acq, scale) == ("avg8", 8.0):
                color = RED
            style = f"rounded=0;whiteSpace=wrap;html=1;fillColor={color};strokeColor=#FFFFFF;strokeWidth=1;"
            vertex(f"g-{i}-{j}", "", style, grid_x + j * cell, grid_y + i * cell, cell, cell)
    vertex("support-label", "support", label_style, 264, 2, 74, 18)

    vertex("emit", "emit", "rounded=1;whiteSpace=wrap;html=1;fillColor=#D8EFEE;strokeColor=#087F8C;strokeWidth=2;fontFamily=Times New Roman;fontSize=11;fontStyle=1;fontColor=#087F8C;", 400, 20, 86, 38)
    vertex("abstain", "abstain", "rounded=1;whiteSpace=wrap;html=1;fillColor=#F1F3F5;strokeColor=#AAB3BA;strokeWidth=2;fontFamily=Times New Roman;fontSize=11;fontStyle=1;fontColor=#66727E;", 400, 76, 86, 38)
    edge("e1", "img", "map", MID)
    edge("e2", "map", "g-2-2", MID)
    edge("e3", "g-0-0", "emit", TEAL)
    edge("e4", "g-3-1", "abstain", MID)

    xml = (
        '<mxfile host="app.diagrams.net" modified="2026-08-30T00:00:00.000Z" agent="NOSTOS" version="24.7.17">'
        '<diagram id="nostos-toc" name="Page-1">'
        '<mxGraphModel dx="1200" dy="700" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="520" pageHeight="130" math="0" shadow="0" adaptiveColors="auto">'
        '<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )
    path = OUT / "nostos_small_methods_toc.drawio"
    path.write_text(xml, encoding="utf-8")
    return path


def build_toc_render(fmd: Mapping[str, Any], development_audit: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    image = vf.center_crop(fmd["ladder"]["avg8"], 430)
    orientation, _ = vf.orientation_rgb(image, sigma=2.0)
    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in development_audit["supported_cells"]
    }
    fig = plt.figure(figsize=(4.333, 0.787))
    fig.subplots_adjust(left=0.005, right=0.995, bottom=0.02, top=0.98, wspace=0.12)
    gs = fig.add_gridspec(1, 8)
    ax = fig.add_subplot(gs[0, 0:2])
    image_axis(ax, vf.robust_unit(image), "image", cmap="gray")
    ax = fig.add_subplot(gs[0, 2:4])
    image_axis(ax, orientation, "measure", cmap=None)
    ax = fig.add_subplot(gs[0, 4:6])
    draw_support_lattice(ax, supported, failed=("avg8", 8.0))
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.text(0.5, 1.05, "support", transform=ax.transAxes, ha="center", va="bottom", fontweight="bold", fontsize=8)
    ax = fig.add_subplot(gs[0, 6:])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.12, 0.56), 0.76, 0.27, boxstyle="round,pad=0.01,rounding_size=0.03", facecolor="#D8EFEE", edgecolor=TEAL, linewidth=1.3))
    ax.add_patch(FancyBboxPatch((0.12, 0.12), 0.76, 0.27, boxstyle="round,pad=0.01,rounding_size=0.03", facecolor="#F1F3F5", edgecolor="#AAB3BA", linewidth=1.3))
    ax.text(0.5, 0.695, "emit", ha="center", va="center", color=TEAL, fontweight="bold", fontsize=8)
    ax.text(0.5, 0.255, "abstain", ha="center", va="center", color=MID, fontweight="bold", fontsize=8)
    return save_figure(fig, "nostos_small_methods_toc")


def build_manifest(outputs: Mapping[str, Any], sources: Sequence[Path], archives: Sequence[Path], toc_drawio: Path) -> Path:
    payload = {
        "schema_version": "nostos-small-methods-figures/1.1",
        "status": "complete",
        "generated_by": Path(__file__).relative_to(ROOT).as_posix(),
        "generated_by_sha256": sha256(Path(__file__)),
        "declaration": (
            "All biological image pixels originate from the cited public BioSR and FMD archives; "
            "all measurement maps and statistical summaries are deterministic. BioRender-generated artwork is "
            "restricted to explicitly illustrative workflow geometry and contains no biological observations or data."
        ),
        "font": {"family": "Times New Roman", "resolved_path": TIMES_PATH},
        "outputs": outputs,
        "toc_drawio": {
            "path": toc_drawio.relative_to(ROOT).as_posix(),
            "bytes": toc_drawio.stat().st_size,
            "sha256": sha256(toc_drawio),
        },
        "sources": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sources
        ],
        "biorender_assets": {
            name: {
                "path": item["path"].relative_to(ROOT).as_posix(),
                "bytes": item["path"].stat().st_size,
                "sha256": sha256(item["path"]),
                "session_id": item["session_id"],
                "figure_id": item["figure_id"],
                "editor_url": item["editor_url"],
                "role": item["role"],
            }
            for name, item in BIORENDER_ASSETS.items()
        },
        "archives": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in archives
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = OUT / "small_methods_figures.manifest.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark"),
    )
    args = parser.parse_args()

    paths = {
        "biosr_rows": ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/tensor_cases.jsonl",
        "biosr_receipt": ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/confirmation_receipt.json",
        "v13_development": ROOT / "outputs/nostos0-fmd-widefield-v1-3-compiled/development_scored.jsonl",
        "v13_confirmation": ROOT / "outputs/nostos0-fmd-widefield-v1-3-confirmation-audit-v1-1/confirmation_scored.jsonl",
        "v13_audit": ROOT / "outputs/nostos0-fmd-widefield-v1-3-confirmation-audit-v1-1/confirmation_audit.json",
        "conditional_development": ROOT / "outputs/nostos0-fmd-widefield-v1-4-conditional-development/development_audit.json",
        "conditional_scored": ROOT / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_scored.jsonl",
        "conditional_audit": ROOT / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_audit.json",
        "finite_sample": ROOT / "outputs/nostos0-fmd-widefield-v1-4-finite-sample-uncertainty.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing frozen evidence: {missing}")

    biosr_rows = vf.read_jsonl(paths["biosr_rows"])
    biosr_receipt = vf.read_json(paths["biosr_receipt"])
    development_rows = vf.read_jsonl(paths["v13_development"])
    confirmation_rows = vf.read_jsonl(paths["v13_confirmation"])
    v13_audit = vf.read_json(paths["v13_audit"])
    conditional_development = vf.read_json(paths["conditional_development"])
    conditional_rows = vf.read_jsonl(paths["conditional_scored"])
    conditional_audit = vf.read_json(paths["conditional_audit"])
    finite_sample = vf.read_json(paths["finite_sample"])

    biosr = vf.load_biosr_example(args.data_root, biosr_rows)
    fmd_archive = args.data_root / "fmd" / "WideField_BPAE_R.tar"
    fmd = vf.load_fmd_images(fmd_archive, conditional_rows, (1, 5, 14, 20))

    outputs = {
        "figure_1": figure1(biosr, biosr_rows, fmd, conditional_development),
        "figure_2": figure2(biosr, biosr_rows, biosr_receipt),
        "figure_3": figure3(fmd, development_rows, confirmation_rows, v13_audit),
        "figure_4": figure4(fmd, conditional_rows, conditional_development, conditional_audit, finite_sample),
        "toc": build_toc_render(fmd, conditional_development),
    }
    toc_drawio = build_toc_drawio(fmd, conditional_development)
    manifest = build_manifest(
        outputs,
        list(paths.values()),
        [biosr["archive"], fmd_archive],
        toc_drawio,
    )
    print(json.dumps({"status": "complete", "outputs": outputs, "toc_drawio": str(toc_drawio), "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
