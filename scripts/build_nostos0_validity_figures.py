"""Build the evidence-linked NOSTOS-0 computational-methods figure set.

Every microscopy panel is decoded from a cited public archive. Every summary
panel is recomputed from frozen NOSTOS evidence rows. No generative imagery is
used. The script emits editable SVG/PDF files, 600-dpi PNG files and a source
manifest suitable for release auditing.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize, hsv_to_rgb
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle, Wedge
from PIL import Image

from nostos.intraop.label_free import local_orientation_field
from nostos.validation.controlled_degradation_v8 import apply_controlled_degradation
from nostos.validation.family_risk_calibration import risk_coverage_auc
from nostos.validation.paired_acquisition_support import read_mrc_bytes
from nostos.validation.tensor_support_v7 import policy_accepts


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0"

INK = "#17212B"
MID = "#66727E"
LIGHT = "#D7DEE5"
PALE = "#EEF2F5"
TEAL = "#087F8C"
TEAL_LIGHT = "#9CD8D6"
BLUE = "#2667A5"
BLUE_LIGHT = "#A9C9E8"
RED = "#C43D4E"
RED_DARK = "#8F2333"
AMBER = "#D59620"
VIOLET = "#6457A6"
WHITE = "#FFFFFF"

RISK_CMAP = LinearSegmentedColormap.from_list(
    "nostos_risk", ["#F3F6F7", "#F6D28A", "#E87958", "#9E263C"]
)


mpl.use("Agg")
mpl.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 8.4,
        "axes.titlesize": 9.0,
        "axes.labelsize": 8.2,
        "axes.linewidth": 0.65,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "legend.fontsize": 7.2,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "svg.hashsalt": "nostos0-validity-figures-v1",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def robust_unit(image: np.ndarray, low: float = 1.0, high: float = 99.7) -> np.ndarray:
    data = np.asarray(image, dtype=np.float64)
    lo, hi = np.percentile(data[np.isfinite(data)], (low, high))
    return np.clip((data - lo) / max(float(hi - lo), np.finfo(float).eps), 0.0, 1.0)


def center_crop(image: np.ndarray, size: int | tuple[int, int]) -> np.ndarray:
    if isinstance(size, int):
        size = (size, size)
    height, width = image.shape[:2]
    crop_h, crop_w = min(size[0], height), min(size[1], width)
    y0 = max(0, (height - crop_h) // 2)
    x0 = max(0, (width - crop_w) // 2)
    return image[y0 : y0 + crop_h, x0 : x0 + crop_w]


def orientation_rgb(image: np.ndarray, sigma: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    unit = robust_unit(image)
    orientation, coherence, energy = local_orientation_field(unit, sigma_pixels=sigma)
    energy_unit = robust_unit(np.log1p(energy), 2, 99.5)
    hsv = np.zeros((*unit.shape, 3), dtype=float)
    hsv[..., 0] = orientation / 180.0
    hsv[..., 1] = np.clip(0.20 + 0.80 * coherence, 0.0, 1.0)
    hsv[..., 2] = np.clip(0.18 + 0.82 * np.maximum(unit, energy_unit), 0.0, 1.0)
    return hsv_to_rgb(hsv), coherence


def fft_power(image: np.ndarray) -> np.ndarray:
    data = robust_unit(image)
    window = np.outer(np.hanning(data.shape[0]), np.hanning(data.shape[1]))
    spectrum = np.fft.fftshift(np.fft.fft2((data - np.mean(data)) * window))
    return np.log1p(np.abs(spectrum) ** 2)


def panel_label(ax: mpl.axes.Axes, letter: str, *, color: str = INK) -> None:
    writer = getattr(ax, "text2D", ax.text)
    writer(
        -0.045,
        1.035,
        letter,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=12.2,
        fontweight="bold",
        color=color,
        clip_on=False,
        zorder=20,
    )


def image_panel(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    title: str,
    *,
    cmap: str | mpl.colors.Colormap | None = "gray",
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    ax.imshow(image, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_title(title, pad=3.0, fontweight="bold")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def add_scale_bar(
    ax: mpl.axes.Axes,
    *,
    pixels: float,
    label: str,
    color: str = WHITE,
) -> None:
    x0, x1 = 0.07, 0.07 + pixels
    ax.plot([x0, x1], [0.08, 0.08], transform=ax.transAxes, color=color, lw=2.2, solid_capstyle="butt")
    ax.text((x0 + x1) / 2, 0.105, label, transform=ax.transAxes, color=color,
            ha="center", va="bottom", fontsize=6.6, fontweight="bold")


def minimal_axes(ax: mpl.axes.Axes) -> None:
    ax.grid(axis="y", color=PALE, linewidth=0.7, zorder=0)
    ax.tick_params(length=2.5, color=LIGHT)
    ax.spines["left"].set_color(LIGHT)
    ax.spines["bottom"].set_color(LIGHT)


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
        fig.savefig(path, bbox_inches="tight", pad_inches=0.045, **kwargs)
        outputs[suffix] = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    plt.close(fig)
    return outputs


def tied_risk_curve(rows: Sequence[Mapping[str, Any]], score_key: str) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(rows, key=lambda row: (float(row[score_key]), str(row["case_id"])))
    coverage = [0.0]
    risk = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        score = float(ordered[index][score_key])
        end = index
        while end < len(ordered) and float(ordered[end][score_key]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage.append(end / len(ordered))
        risk.append(invalid / end)
        index = end
    return np.asarray(coverage), np.asarray(risk)


def biosr_eligible(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if row["endpoint_family"] == "tensor_coherence"
        and bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
    ]


def biosr_accept(row: Mapping[str, Any], condition: str) -> bool:
    return bool(policy_accepts(row, condition))


def biosr_curve_rows(rows: Sequence[Mapping[str, Any]], condition: str) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "invalid": row["invalid"],
            "score": float(row["scores"][condition]),
        }
        for row in rows
    ]


def load_biosr_example(
    data_root: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    group = "F-actin_linear|Cell_024"
    selected = [
        row
        for row in rows
        if row["reference_group_id"] == group
        and "level_01" in str(row["pair_id"])
        and row["endpoint_family"] == "tensor_coherence"
    ]
    if not selected:
        raise RuntimeError("Locked BioSR display field is absent from the evidence rows.")
    representative = next(row for row in selected if row["metadata"]["degradation_id"] == "clean")
    archive = data_root / "biosr" / "archives" / "F-actin.zip"
    with zipfile.ZipFile(archive) as opened:
        raw_stack = read_mrc_bytes(opened.read(representative["metadata"]["input_member"]))
        reference = read_mrc_bytes(opened.read(representative["metadata"]["reference_member"]))
    clean = np.mean(np.asarray(raw_stack, dtype=np.float64), axis=0)

    degraded: dict[str, np.ndarray] = {}
    degradation_rows: dict[str, Mapping[str, Any]] = {}
    for identifier in ("anisotropic_y_0_5_x_3", "blur_4px", "blur_8px"):
        row = next(row for row in selected if row["metadata"]["degradation_id"] == identifier)
        degraded[identifier] = apply_controlled_degradation(
            clean,
            row["metadata"]["degradation_specification"],
            seed=int(row["metadata"]["condition_seed"]),
        )
        degradation_rows[identifier] = row
    return {
        "archive": archive,
        "clean": clean,
        "reference": np.asarray(reference, dtype=np.float64),
        "degraded": degraded,
        "degradation_rows": degradation_rows,
        "selected_rows": selected,
    }


def read_tar_image(opened: tarfile.TarFile, member: str) -> np.ndarray:
    extracted = opened.extractfile(member)
    if extracted is None:
        raise FileNotFoundError(member)
    with Image.open(io.BytesIO(extracted.read())) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def fmd_example_members(rows: Sequence[Mapping[str, Any]], field: int) -> tuple[str, str]:
    row = next(
        row
        for row in rows
        if int(row["metadata"]["field_of_view"]) == field
        and row["metadata"]["acquisition_level"] == "avg16"
    )
    return str(row["metadata"]["input_member"]), str(row["metadata"]["reference_member"])


def load_fmd_images(
    archive: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[int],
) -> dict[str, Any]:
    output: dict[str, Any] = {"archive": archive, "fields": {}, "ladder": {}}
    with tarfile.open(archive, mode="r:") as opened:
        for field in fields:
            input_member, reference_member = fmd_example_members(rows, field)
            output["fields"][field] = {
                "avg16": read_tar_image(opened, input_member),
                "reference": read_tar_image(opened, reference_member),
                "input_member": input_member,
                "reference_member": reference_member,
            }
        ladder_field = 14
        input_member, reference_member = fmd_example_members(rows, ladder_field)
        parts = PurePosixPath(input_member).parts
        filename = parts[-1]
        for level in ("raw", "avg2", "avg4", "avg8", "avg16"):
            member = PurePosixPath(parts[0], level, str(ladder_field), filename).as_posix()
            output["ladder"][level] = read_tar_image(opened, member)
        output["ladder"]["avg50"] = read_tar_image(opened, reference_member)
    return output


def conditional_accept(row: Mapping[str, Any], threshold: float) -> bool:
    return not bool(row["candidate_hard_abstention"]) and float(row["calibrated_risk"]) <= threshold


def v13_accept(
    row: Mapping[str, Any],
    threshold: float,
    *,
    development: bool,
    score_key: str = "declared_capture_stability_contract",
) -> bool:
    if development:
        hard = bool(row["candidate_hard_abstention"][score_key])
        risk = float(row["cross_fitted_calibrated_risk"][score_key])
    else:
        hard_value = row["candidate_hard_abstention"]
        risk_value = row["calibrated_risk"]
        hard = bool(hard_value[score_key] if isinstance(hard_value, Mapping) else hard_value)
        risk = float(risk_value[score_key] if isinstance(risk_value, Mapping) else risk_value)
    return not hard and risk <= threshold


def cell_matrix(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    acceptance: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    coverage = np.zeros((len(acquisitions), len(scales)), dtype=float)
    risk = np.full_like(coverage, np.nan)
    invalid = np.zeros_like(coverage, dtype=int)
    for i, acquisition in enumerate(acquisitions):
        for j, scale in enumerate(scales):
            subset = [
                row
                for row in rows
                if row["endpoint_family"] == "tensor_coherence"
                and row["metadata"]["acquisition_level"] == acquisition
                and float(row["requested_scale_value"]) == scale
                and bool(row["pair_registration_eligible"])
                and bool(row["reference_eligible"])
            ]
            accepted = [row for row in subset if acceptance(row, threshold)]
            coverage[i, j] = len(accepted) / len(subset) if subset else 0.0
            invalid[i, j] = sum(bool(row["invalid"]) for row in accepted)
            risk[i, j] = (
                float(np.mean([bool(row["invalid"]) for row in accepted]))
                if accepted
                else np.nan
            )
    return coverage, risk, invalid


def draw_contract_pipeline(ax: mpl.axes.Axes) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    labels = ["image", "response", "diagnostics", "calibration", "decision"]
    colors = [INK, VIOLET, BLUE, AMBER, TEAL]
    centers = np.linspace(0.08, 0.92, len(labels))
    for index, (center, label, color) in enumerate(zip(centers, labels, colors, strict=True)):
        width = 0.145
        box = FancyBboxPatch(
            (center - width / 2, 0.32),
            width,
            0.36,
            boxstyle="round,pad=0.012,rounding_size=0.028",
            facecolor=color if index in {0, 4} else WHITE,
            edgecolor=color,
            linewidth=1.25,
        )
        ax.add_patch(box)
        ax.text(
            center,
            0.50,
            label,
            ha="center",
            va="center",
            fontsize=8.2,
            fontweight="bold",
            color=WHITE if index in {0, 4} else color,
        )
        if index < len(labels) - 1:
            arrow = FancyArrowPatch(
                (center + width / 2 + 0.006, 0.50),
                (centers[index + 1] - width / 2 - 0.006, 0.50),
                arrowstyle="-|>",
                mutation_scale=10,
                linewidth=0.9,
                color=MID,
            )
            ax.add_patch(arrow)
    ax.text(0.92, 0.18, "emit", color=TEAL, ha="center", fontweight="bold", fontsize=7.5)
    ax.text(0.92, 0.82, "abstain", color=RED, ha="center", fontweight="bold", fontsize=7.5)
    ax.annotate("", xy=(0.92, 0.72), xytext=(0.92, 0.68), arrowprops={"arrowstyle": "-|>", "color": RED})
    ax.annotate("", xy=(0.92, 0.28), xytext=(0.92, 0.32), arrowprops={"arrowstyle": "-|>", "color": TEAL})


def draw_diagnostic_radar(
    ax: mpl.axes.Axes,
    safe_row: Mapping[str, Any],
    unsupported_row: Mapping[str, Any],
) -> None:
    labels = ["QC", "stability", "sampling", "identity", "cell"]
    def values(row: Mapping[str, Any]) -> list[float]:
        return [
            min(float(row["scores"]["conventional_acquisition_qc"]), 1.05),
            min(float(row["scores"]["perturbation_stability_only"]), 1.05),
            min(float(row["scores"]["scale_sampling_only"]), 1.05),
            1.0 if bool(row.get("hard_abstention", False)) else 0.0,
            0.0 if bool(row.get("conditional_cell_supported", False)) else 1.0,
        ]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    closed_angles = np.r_[angles, angles[0]]
    for row, color, label in ((safe_row, TEAL, "supported"), (unsupported_row, RED, "unsupported")):
        row_values = values(row)
        closed_values = np.r_[row_values, row_values[0]]
        ax.plot(closed_angles, closed_values, color=color, lw=1.5, label=label)
        ax.fill(closed_angles, closed_values, color=color, alpha=0.12)
    ax.plot(np.linspace(0, 2 * np.pi, 200), np.ones(200), color=RED, lw=0.8, ls=":")
    ax.set_ylim(0, 1.08)
    ax.set_xticks(angles, labels, fontsize=6.8)
    ax.set_yticks([0.5, 1.0], ["", "limit"], fontsize=5.8)
    ax.grid(color=LIGHT, linewidth=0.55)
    ax.spines["polar"].set_color(LIGHT)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=6.2)


def figure1(
    biosr: Mapping[str, Any],
    biosr_rows: Sequence[Mapping[str, Any]],
    fmd: Mapping[str, Any],
    fmd_rows: Sequence[Mapping[str, Any]],
    conditional_development: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    fig = plt.figure(figsize=(8.15, 6.85))
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.075, top=0.955, hspace=0.50, wspace=0.72)
    gs = fig.add_gridspec(3, 12, height_ratios=[0.62, 0.55, 1.18])

    bio_clean = center_crop(biosr["clean"], 430)
    bio_ref = center_crop(biosr["reference"], 860)
    bio_rgb, bio_coherence = orientation_rgb(bio_clean, sigma=3.0)
    fmd_input = fmd["fields"][14]["avg16"]
    fmd_rgb, fmd_coherence = orientation_rgb(fmd_input, sigma=2.5)
    spectrum = fft_power(fmd_input)
    images = [
        (robust_unit(bio_clean), "BioSR input", "gray"),
        (robust_unit(bio_ref), "paired reference", "gray"),
        (bio_rgb, "orientation field", None),
        (robust_unit(fmd_input), "FMD input", "gray"),
        (fmd_rgb, "orientation field", None),
        (spectrum, "Fourier power", "magma"),
    ]
    for index, (image, title, cmap) in enumerate(images):
        ax = fig.add_subplot(gs[0, index * 2 : (index + 1) * 2])
        image_panel(ax, image, title, cmap=cmap)
        if index == 0:
            panel_label(ax, "a")
            add_scale_bar(ax, pixels=5.0 / (0.0626 * bio_clean.shape[1]), label="5 µm")

    ax = fig.add_subplot(gs[1, :])
    panel_label(ax, "b")
    draw_contract_pipeline(ax)

    ax = fig.add_subplot(gs[2, :4])
    panel_label(ax, "c")
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
    scales = np.asarray([row["requested_scale_um"] for row in clean_rows])
    estimate = np.asarray([row["estimate"] for row in clean_rows])
    reference = np.asarray([row["reference"] for row in clean_rows])
    ax.plot(scales, reference, "o-", color=INK, lw=1.4, ms=3.6, label="reference")
    ax.plot(scales, estimate, "o-", color=TEAL, lw=1.7, ms=3.6, label="measurement")
    ax.fill_between(scales, reference, estimate, color=TEAL_LIGHT, alpha=0.38)
    ax.set(xlabel="physical scale (µm)", ylabel="tensor coherence", ylim=(0.34, 0.60))
    ax.set_title("Scale-resolved response", fontweight="bold", pad=3)
    ax.legend(loc="lower right")
    minimal_axes(ax)

    radar_row = next(
        row
        for row in fmd_rows
        if row["metadata"]["field_of_view"] == 14
        and row["metadata"]["acquisition_level"] == "avg16"
        and row["endpoint_family"] == "tensor_coherence"
        and float(row["requested_scale_value"]) == 16.0
    )
    unsupported_row = next(
        row
        for row in fmd_rows
        if row["metadata"]["field_of_view"] == 14
        and row["metadata"]["acquisition_level"] == "avg8"
        and row["endpoint_family"] == "tensor_coherence"
        and float(row["requested_scale_value"]) == 8.0
    )
    ax = fig.add_subplot(gs[2, 4:8], projection="polar")
    panel_label(ax, "d")
    draw_diagnostic_radar(ax, radar_row, unsupported_row)
    ax.set_title("Input-only validity fingerprint", fontweight="bold", pad=12)

    ax = fig.add_subplot(gs[2, 9:])
    panel_label(ax, "e")
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales_px = [4.0, 8.0, 16.0]
    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in conditional_development["supported_cells"]
    }
    matrix = np.asarray(
        [[1.0 if (acquisition, scale) in supported else 0.0 for scale in scales_px] for acquisition in acquisitions]
    )
    cmap = mpl.colors.ListedColormap(["#E4E9ED", TEAL])
    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(3), ["4", "8", "16"])
    ax.set_yticks(range(5), ["raw", "2", "4", "8", "16"])
    ax.set_xlabel("requested scale (px)")
    ax.set_ylabel("averaged captures")
    ax.set_title("Declared support lattice", fontweight="bold", pad=3)
    for i in range(5):
        for j in range(3):
            ax.text(j, i, "●" if matrix[i, j] else "×", ha="center", va="center",
                    color=WHITE if matrix[i, j] else MID, fontsize=10, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    return save_figure(fig, "figure_1_validity_contract_atlas")


def donut(ax: mpl.axes.Axes, values: Sequence[int], colors: Sequence[str], label: str) -> None:
    total = max(sum(values), 1)
    angle = 90.0
    for value, color in zip(values, colors, strict=True):
        extent = 360.0 * value / total
        ax.add_patch(Wedge((0, 0), 1.0, angle, angle + extent, width=0.42,
                           facecolor=color, edgecolor=WHITE, linewidth=0.45))
        angle += extent
    ax.add_patch(Circle((0, 0), 0.55, facecolor=WHITE, edgecolor="none"))
    ax.text(0, 0, f"{100 * (values[0] + values[1]) / total:.0f}%", ha="center", va="center",
            fontsize=6.4, fontweight="bold", color=INK)
    ax.set_title(label, fontsize=6.2, pad=1.2)
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.set_aspect("equal")
    ax.axis("off")


def figure2(
    biosr: Mapping[str, Any],
    biosr_rows: Sequence[Mapping[str, Any]],
    receipt: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = biosr_eligible(biosr_rows)
    evaluation = receipt["confirmation_evaluation"]
    full = evaluation["full_contract"]
    qc = evaluation["conventional_acquisition_qc"]
    assert (len(rows), full["accepted"], full["invalid"]) == (980, 931, 36)

    clean = center_crop(biosr["clean"], 430)
    reference = center_crop(biosr["reference"], 860)
    blur = center_crop(biosr["degraded"]["blur_4px"], 430)
    clean_rgb, clean_coh = orientation_rgb(clean, sigma=3.0)
    blur_rgb, blur_coh = orientation_rgb(blur, sigma=3.0)

    fig = plt.figure(figsize=(8.15, 8.05))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.075, top=0.96, hspace=0.42, wspace=0.65)
    gs = fig.add_gridspec(3, 14, height_ratios=[1.00, 0.93, 1.28])
    displays = [
        (robust_unit(reference), "reference", "gray"),
        (robust_unit(clean), "input", "gray"),
        (clean_rgb, "clean field", None),
        (robust_unit(blur), "blurred input", "gray"),
        (blur_rgb, "blurred field", None),
    ]
    image_grid = gs[0, :].subgridspec(1, 5, wspace=0.045)
    for index, (display, title, cmap) in enumerate(displays):
        ax = fig.add_subplot(image_grid[0, index])
        image_panel(ax, display, title, cmap=cmap)
        if index == 0:
            panel_label(ax, "a")

    condition_order = [
        "clean", "gamma_0_5", "gamma_2_0", "blur_1px", "blur_2px", "blur_4px", "blur_8px",
        "anisotropic_y_0_5_x_3", "anisotropic_y_3_x_0_5", "noise_0_03", "noise_0_08",
        "noise_0_15", "resample_2x", "resample_4x",
    ]
    short_names = {
        "clean": "clean", "gamma_0_5": "γ 0.5", "gamma_2_0": "γ 2",
        "blur_1px": "blur 1", "blur_2px": "blur 2", "blur_4px": "blur 4", "blur_8px": "blur 8",
        "anisotropic_y_0_5_x_3": "aniso x", "anisotropic_y_3_x_0_5": "aniso y",
        "noise_0_03": "noise .03", "noise_0_08": "noise .08", "noise_0_15": "noise .15",
        "resample_2x": "resize 2", "resample_4x": "resize 4",
    }
    donut_grid = gs[1, :].subgridspec(2, 7, hspace=0.06, wspace=0.06)
    for index, condition in enumerate(condition_order):
        ax = fig.add_subplot(donut_grid[index // 7, index % 7])
        subset = [row for row in rows if row["metadata"]["degradation_id"] == condition]
        valid_emitted = sum(biosr_accept(row, "full_contract") and not row["invalid"] for row in subset)
        invalid_emitted = sum(biosr_accept(row, "full_contract") and row["invalid"] for row in subset)
        abstained = len(subset) - valid_emitted - invalid_emitted
        donut(ax, [valid_emitted, invalid_emitted, abstained], [TEAL, RED, LIGHT], short_names[condition])
        if index == 0:
            panel_label(ax, "b")

    ax = fig.add_subplot(gs[2, :5])
    panel_label(ax, "c")
    groups = sorted({row["reference_group_id"] for row in rows})
    for index, group in enumerate(groups):
        group_rows = [row for row in rows if row["reference_group_id"] == group]
        full_rows = [row for row in group_rows if biosr_accept(row, "full_contract")]
        qc_rows = [row for row in group_rows if biosr_accept(row, "conventional_acquisition_qc")]
        full_risk = np.mean([row["invalid"] for row in full_rows])
        qc_risk = np.mean([row["invalid"] for row in qc_rows])
        ax.plot([0, 1], [qc_risk, full_risk], color=LIGHT, lw=1.0, zorder=1)
        ax.scatter(0, qc_risk, color=BLUE, s=28, edgecolor=WHITE, linewidth=0.5, zorder=3)
        ax.scatter(1, full_risk, color=TEAL, s=28, edgecolor=WHITE, linewidth=0.5, zorder=3)
    ax.set_xticks([0, 1], ["QC", "NOSTOS"])
    ax.set_ylabel("invalid emitted fraction")
    ax.set_ylim(-0.008, 0.19)
    ax.set_title("Eight untouched fields", fontweight="bold", pad=3)
    minimal_axes(ax)

    ax = fig.add_subplot(gs[2, 5:10])
    panel_label(ax, "d")
    full_curve_rows = biosr_curve_rows(rows, "full_contract")
    qc_curve_rows = biosr_curve_rows(rows, "conventional_acquisition_qc")
    x_full, y_full = tied_risk_curve(full_curve_rows, "score")
    x_qc, y_qc = tied_risk_curve(qc_curve_rows, "score")
    ax.plot(x_qc, y_qc, color=BLUE, lw=1.6, label="acquisition QC")
    ax.plot(x_full, y_full, color=TEAL, lw=1.9, label="NOSTOS")
    ax.scatter([full["coverage"]], [full["risk"]], color=TEAL, edgecolor=WHITE, linewidth=0.7, s=42, zorder=4)
    ax.scatter([qc["coverage"]], [qc["risk"]], color=BLUE, edgecolor=WHITE, linewidth=0.7, s=42, zorder=4)
    ax.set(xlabel="coverage", ylabel="selective risk", xlim=(0, 1.015), ylim=(-0.004, 0.105))
    ax.set_title("Risk–coverage", fontweight="bold", pad=3)
    ax.legend(loc="upper left")
    minimal_axes(ax)

    ax = fig.add_subplot(gs[2, 10:])
    panel_label(ax, "e")
    ax.set_xlim(-0.5, 6.5)
    ax.set_ylim(-0.5, 6.5)
    for index in range(49):
        x, y = index % 7, 6 - index // 7
        color = RED if index < 36 else TEAL_LIGHT
        ax.add_patch(Circle((x, y), 0.34, facecolor=color, edgecolor=WHITE, linewidth=0.5))
    ax.text(3.0, -0.70, "49 NOSTOS-only rejections", ha="center", va="top", fontsize=6.7, color=MID)
    ax.text(3.0, 7.03, "36 invalid", ha="center", va="bottom", fontsize=9.0, color=RED, fontweight="bold")
    ax.text(3.0, 6.55, "10× enrichment", ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_aspect("equal")
    ax.axis("off")

    return save_figure(fig, "figure_2_biosr_selective_validity")


def draw_fmd_ladder(fig: plt.Figure, slot: Any, ladder: Mapping[str, np.ndarray]) -> None:
    grid = slot.subgridspec(1, 6, wspace=0.035)
    for index, level in enumerate(("raw", "avg2", "avg4", "avg8", "avg16", "avg50")):
        ax = fig.add_subplot(grid[0, index])
        image_panel(ax, robust_unit(ladder[level], 1, 99.5), level, cmap="gray")
        if index == 0:
            panel_label(ax, "a")


def draw_v13_risk_terrain(
    ax: mpl.axes.Axes,
    coverage: np.ndarray,
    risk: np.ndarray,
) -> None:
    acquisitions = ["raw", "2", "4", "8", "16"]
    scales = ["4", "8", "16"]
    xpos, ypos = np.meshgrid(np.arange(5), np.arange(3), indexing="ij")
    for x, y, cov, value in zip(xpos.ravel(), ypos.ravel(), coverage.ravel(), risk.ravel(), strict=True):
        if cov == 0 or not np.isfinite(value):
            ax.bar3d(x - 0.32, y - 0.32, 0, 0.64, 0.64, 0.008, color="#D8DEE4", shade=False, alpha=0.55)
        else:
            height = max(float(value), 0.018)
            color = RISK_CMAP(float(value))
            ax.bar3d(x - 0.32, y - 0.32, 0, 0.64, 0.64, height, color=color, shade=True, alpha=0.95)
    ax.set_xticks(range(5), acquisitions, fontsize=6.5)
    ax.set_yticks(range(3), scales, fontsize=6.5)
    ax.set_zticks([0, 0.5, 1.0], ["0", ".5", "1"])
    ax.set_xlabel("averaged captures", labelpad=1)
    ax.set_ylabel("scale (px)", labelpad=1)
    ax.set_zlabel("")
    ax.set_zlim(0, 1.03)
    ax.view_init(elev=28, azim=-57)
    ax.grid(False)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.text2D(0.93, 0.53, "risk", transform=ax.transAxes, rotation=90,
              ha="center", va="center", fontsize=7.0, color=MID)


def draw_cell_heatmap(
    ax: mpl.axes.Axes,
    coverage: np.ndarray,
    risk: np.ndarray,
    invalid: np.ndarray,
    title: str,
) -> None:
    display = np.where(np.isfinite(risk), risk, 0.0)
    alpha = np.where(coverage > 0, 1.0, 0.18)
    rgba = RISK_CMAP(display)
    rgba[..., 3] = alpha
    ax.imshow(rgba, aspect="auto")
    ax.set_xticks(range(3), ["4", "8", "16"])
    ax.set_yticks(range(5), ["raw", "2", "4", "8", "16"])
    ax.set_xlabel("requested scale (px)")
    ax.set_ylabel("averaged captures")
    ax.set_title(title, fontweight="bold", pad=3)
    for i in range(5):
        for j in range(3):
            if coverage[i, j] == 0:
                text = "×"
                color = MID
            else:
                text = f"{invalid[i, j]}\n{coverage[i, j]:.0%}"
                color = WHITE if risk[i, j] >= 0.45 else INK
            ax.text(j, i, text, ha="center", va="center", fontsize=6.4, color=color, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def figure3(
    fmd: Mapping[str, Any],
    v13_development_rows: Sequence[Mapping[str, Any]],
    v13_confirmation_rows: Sequence[Mapping[str, Any]],
    v13_audit: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    threshold = float(v13_audit["primary_operating_point"]["predicted_risk_threshold"])
    dev_cov, dev_risk, dev_invalid = cell_matrix(
        v13_development_rows,
        threshold=threshold,
        acceptance=lambda row, value: v13_accept(row, value, development=True),
    )
    con_cov, con_risk, con_invalid = cell_matrix(
        v13_confirmation_rows,
        threshold=threshold,
        acceptance=lambda row, value: v13_accept(row, value, development=False),
    )
    assert int(np.sum(con_invalid)) == 4
    assert np.isclose(con_risk[3, 1], 1.0)

    fig = plt.figure(figsize=(8.15, 8.55))
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.065, top=0.96, hspace=0.56, wspace=0.66)
    gs = fig.add_gridspec(3, 12, height_ratios=[0.82, 1.20, 0.90])
    draw_fmd_ladder(fig, gs[0, :], fmd["ladder"])

    ax = fig.add_subplot(gs[1, :6], projection="3d")
    panel_label(ax, "b")
    draw_v13_risk_terrain(ax, con_cov, con_risk)
    ax.set_title("Pooled profile: hidden conditional failure", fontweight="bold", pad=0)

    ax = fig.add_subplot(gs[1, 7:])
    panel_label(ax, "c")
    draw_cell_heatmap(ax, con_cov, con_risk, con_invalid, "Untouched v1.3 confirmation")
    ax.set_ylabel("")
    ax.add_patch(Rectangle((0.5, 2.5), 1, 1, fill=False, edgecolor=RED_DARK, linewidth=2.1))

    ax = fig.add_subplot(gs[2, :5])
    panel_label(ax, "d")
    draw_cell_heatmap(ax, dev_cov, dev_risk, dev_invalid, "Development localization")
    ax.add_patch(Rectangle((0.5, 2.5), 1, 1, fill=False, edgecolor=RED_DARK, linewidth=2.1))

    ax = fig.add_subplot(gs[2, 6:])
    panel_label(ax, "e")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    centers = [0.11, 0.38, 0.66, 0.91]
    labels = ["pooled", "widefield", "avg8 × 8", "hierarchical"]
    top = ["PASS", "20/48", "4/4 invalid", "REPAIR"]
    colors = [AMBER, RED, RED_DARK, TEAL]
    for index, (center, label, headline, color) in enumerate(zip(centers, labels, top, colors, strict=True)):
        ax.add_patch(Circle((center, 0.55), 0.075, facecolor=color, edgecolor=WHITE, linewidth=1.0))
        ax.text(center, 0.55, str(index + 1), color=WHITE, ha="center", va="center", fontweight="bold", fontsize=9)
        ax.text(center, 0.29, label, ha="center", va="center", color=INK, fontsize=7.1, fontweight="bold")
        ax.text(center, 0.80, headline, ha="center", va="center", color=color, fontsize=7.1, fontweight="bold")
        if index < 3:
            ax.add_patch(FancyArrowPatch((center + 0.085, 0.55), (centers[index + 1] - 0.085, 0.55),
                                         arrowstyle="-|>", mutation_scale=10, color=MID, linewidth=0.9))
    ax.text(0.5, 0.06, "Failures were retained, localized and used to narrow support—not erased.",
            ha="center", va="center", color=MID, fontsize=7.2)

    return save_figure(fig, "figure_3_fmd_hidden_failure")


def draw_outcome_waffle(ax: mpl.axes.Axes, invalid: int, total: int, title: str, color: str) -> None:
    columns = 8
    rows = int(np.ceil(total / columns))
    ax.set_xlim(-0.6, columns - 0.4)
    ax.set_ylim(-0.6, rows - 0.4)
    for index in range(total):
        x, y = index % columns, rows - 1 - index // columns
        face = RED if index < invalid else color
        ax.add_patch(Circle((x, y), 0.34, facecolor=face, edgecolor=WHITE, linewidth=0.45))
    ax.set_title(title, fontweight="bold", pad=3)
    ax.text((columns - 1) / 2, -1.0, f"{invalid}/{total} invalid", ha="center", va="top",
            color=RED if invalid else TEAL, fontsize=7.6, fontweight="bold")
    ax.set_aspect("equal")
    ax.axis("off")


def figure4(
    fmd: Mapping[str, Any],
    scored_rows: Sequence[Mapping[str, Any]],
    development_audit: Mapping[str, Any],
    confirmation_audit: Mapping[str, Any],
    finite_sample: Mapping[str, Any],
    program_audit: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    threshold = float(confirmation_audit["primary_operating_point"]["predicted_risk_threshold"])
    accepted = [row for row in scored_rows if conditional_accept(row, threshold)]
    assert (len(accepted), sum(bool(row["invalid"]) for row in accepted)) == (64, 0)

    fig = plt.figure(figsize=(8.15, 8.75))
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.065, top=0.96, hspace=0.62, wspace=0.72)
    gs = fig.add_gridspec(3, 16, height_ratios=[0.92, 1.00, 1.18])

    for index, field in enumerate((1, 5, 14, 20)):
        ax = fig.add_subplot(gs[0, index * 4 : (index + 1) * 4])
        image_panel(ax, robust_unit(fmd["fields"][field]["avg16"], 1, 99.5), f"field {field}", cmap="gray")
        if index == 0:
            panel_label(ax, "a")

    ax = fig.add_subplot(gs[1, :5])
    panel_label(ax, "b")
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    supported = {
        (str(cell["values"][0]), float(cell["values"][1]))
        for cell in development_audit["supported_cells"]
    }
    matrix = np.asarray([[1 if (acq, scale) in supported else 0 for scale in scales] for acq in acquisitions])
    ax.imshow(matrix, cmap=mpl.colors.ListedColormap(["#E1E6EA", TEAL]), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(3), ["4", "8", "16"])
    ax.set_yticks(range(5), ["raw", "2", "4", "8", "16"])
    ax.set(xlabel="requested scale (px)", ylabel="averaged captures")
    ax.set_title("Frozen support", fontweight="bold", pad=3)
    for i in range(5):
        for j in range(3):
            ax.text(j, i, "●" if matrix[i, j] else "×", ha="center", va="center",
                    color=WHITE if matrix[i, j] else MID, fontweight="bold", fontsize=10)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax = fig.add_subplot(gs[1, 5:10])
    panel_label(ax, "c")
    supported_keys = [cell["key"] for cell in development_audit["supported_cells"]]
    fields = [1, 5, 14, 20]
    emission = np.zeros((4, 4), dtype=int)
    for i, field in enumerate(fields):
        for j, key in enumerate(supported_keys):
            subset = [
                row
                for row in accepted
                if int(row["metadata"]["field_of_view"]) == field
                and str(row["conditional_cell"]["key"]) == key
            ]
            emission[i, j] = len(subset)
    ax.imshow(emission, cmap=mpl.colors.LinearSegmentedColormap.from_list("emit", [PALE, TEAL]), vmin=0, vmax=4, aspect="auto")
    ax.set_xticks(range(4), ["16·16", "16·4", "16·8", "8·16"], rotation=30, ha="right")
    ax.set_yticks(range(4), ["1", "5", "14", "20"])
    ax.set(xlabel="capture · scale", ylabel="field")
    ax.set_title("Prospective emissions", fontweight="bold", pad=3)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, emission[i, j], ha="center", va="center", color=WHITE, fontweight="bold", fontsize=7)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    waffle_grid = gs[1, 10:].subgridspec(1, 2, wspace=0.18)
    ax = fig.add_subplot(waffle_grid[0, 0])
    panel_label(ax, "d")
    draw_outcome_waffle(ax, 31, 64, "acquisition QC", BLUE_LIGHT)
    ax = fig.add_subplot(waffle_grid[0, 1])
    draw_outcome_waffle(ax, 0, 64, "NOSTOS", TEAL_LIGHT)

    ax = fig.add_subplot(gs[2, :6])
    panel_label(ax, "e")
    primary_curve_rows = [
        {"case_id": row["case_id"], "invalid": row["invalid"], "score": float(row["calibrated_risk"])}
        for row in scored_rows
    ]
    qc_curve_rows = [
        {"case_id": row["case_id"], "invalid": row["invalid"], "score": float(row["acquisition_qc_calibrated_risk"])}
        for row in scored_rows
    ]
    px, py = tied_risk_curve(primary_curve_rows, "score")
    qx, qy = tied_risk_curve(qc_curve_rows, "score")
    ax.plot(qx, qy, color=BLUE, lw=1.6, label="acquisition QC")
    ax.plot(px, py, color=TEAL, lw=1.9, label="hierarchical NOSTOS")
    ax.scatter([64 / 240], [0], color=TEAL, edgecolor=WHITE, linewidth=0.7, s=42, zorder=4)
    ax.set(xlabel="coverage", ylabel="selective risk", xlim=(0, 1.015), ylim=(-0.015, 0.82))
    ax.set_title("Risk–coverage", fontweight="bold", pad=3)
    ax.legend(loc="upper left")
    minimal_axes(ax)
    assert np.isclose(risk_coverage_auc(primary_curve_rows, score_key="score"), 0.2627777777777778)

    ax = fig.add_subplot(gs[2, 6:11])
    panel_label(ax, "f")
    bootstrap = confirmation_audit["risk_coverage"]["cluster_bootstrap_aurc_difference"]
    observed = float(bootstrap["observed"])
    low, high = (float(value) for value in bootstrap["bootstrap_ci95"])
    ax.errorbar(observed, 0.68, xerr=[[observed - low], [high - observed]], fmt="o",
                color=TEAL, ecolor=INK, elinewidth=1.4, capsize=4, markersize=6)
    ax.axvline(0, color=RED, lw=0.9, ls=":")
    ax.text(observed, 0.47, "QC − NOSTOS", ha="center", va="top", fontsize=7.1, color=MID)
    ax.text(observed, 0.89, f"{observed:.3f}", ha="center", va="bottom", fontsize=9.2,
            color=TEAL, fontweight="bold")
    ax.set_xlim(-0.05, 0.48)
    ax.set_ylim(0.25, 1.05)
    ax.set_yticks([])
    ax.set_xlabel("AURC difference")
    ax.set_title("Field-bootstrap 95% CI", fontweight="bold", pad=3)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)

    ax = fig.add_subplot(gs[2, 11:])
    panel_label(ax, "g")
    measurement_upper = float(finite_sample["nested_measurement_interval"]["clopper_pearson_95"][1])
    field_upper = float(finite_sample["independent_group_any_failure_interval"]["clopper_pearson_95"][1])
    ax.hlines([1, 0], [0, 0], [measurement_upper, field_upper], color=[TEAL, AMBER], linewidth=6, alpha=0.82)
    ax.scatter([measurement_upper, field_upper], [1, 0], color=[TEAL, AMBER], s=42, zorder=3,
               edgecolor=WHITE, linewidth=0.6)
    ax.text(measurement_upper, 1.18, f"≤ {measurement_upper:.1%}", ha="center", color=TEAL, fontweight="bold")
    ax.text(field_upper, 0.18, f"≤ {field_upper:.1%}", ha="center", color=AMBER, fontweight="bold")
    ax.set_yticks([0, 1], ["4 fields", "64 measures"])
    ax.set_xlim(0, 0.68)
    ax.set_ylim(-0.42, 1.42)
    ax.set_xlabel("exact 95% upper bound")
    ax.set_title("Zero-event uncertainty", fontweight="bold", pad=3)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    ax.tick_params(axis="y", length=0)
    ax.text(0.67, -0.34, f"{sum(program_audit['checks'].values())}/{len(program_audit['checks'])} program checks",
            ha="right", va="bottom", fontsize=6.7, color=MID)

    return save_figure(fig, "figure_4_fmd_hierarchical_confirmation")


def build_manifest(
    *,
    outputs: Mapping[str, Any],
    source_paths: Sequence[Path],
    biosr_archive: Path,
    fmd_archive: Path,
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": "nostos-publication-figure-manifest/1.0",
        "status": "complete",
        "generated_by": "scripts/build_nostos0_validity_figures.py",
        "generated_by_sha256": sha256_file(Path(__file__)),
        "declaration": (
            "All microscopy pixels originate from the cited public BioSR and FMD archives; "
            "all maps are deterministic transforms; all summaries are recomputed from frozen evidence rows; "
            "no generative or synthetic biological imagery is used."
        ),
        "public_datasets": {
            "BioSR": {
                "doi": "10.6084/m9.figshare.13264793",
                "archive": biosr_archive.name,
                "bytes": biosr_archive.stat().st_size,
                "sha256": sha256_file(biosr_archive),
            },
            "FMD": {
                "doi": "10.7274/r0-ed2r-4052",
                "archive": fmd_archive.name,
                "bytes": fmd_archive.stat().st_size,
                "sha256": sha256_file(fmd_archive),
                "calibration_boundary": "No pixel spacing supplied; only pixel-relative endpoints are shown.",
            },
        },
        "frozen_sources": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in source_paths
        ],
        "figures": outputs,
        "rendering": {
            "font": "Times New Roman with Times/DejaVu Serif fallback",
            "raster_dpi": 600,
            "vector_formats": ["PDF", "SVG"],
            "color_semantics": {
                "teal": "valid emission or NOSTOS",
                "blue": "conventional acquisition QC",
                "red": "silent invalidity",
                "grey": "abstention or unsupported cell",
                "amber": "finite-sample uncertainty",
            },
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = OUT / "validity_figures.manifest.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark"),
        help="Root containing biosr/archives and fmd/WideField_BPAE_R.tar.",
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
        "program_audit": ROOT / "outputs/nostos0-fmd-validity-program-final-audit-v1/final_audit.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing frozen evidence: {missing}")

    biosr_rows = read_jsonl(paths["biosr_rows"])
    biosr_receipt = read_json(paths["biosr_receipt"])
    v13_development = read_jsonl(paths["v13_development"])
    v13_confirmation = read_jsonl(paths["v13_confirmation"])
    v13_audit = read_json(paths["v13_audit"])
    conditional_development = read_json(paths["conditional_development"])
    conditional_rows = read_jsonl(paths["conditional_scored"])
    conditional_audit = read_json(paths["conditional_audit"])
    finite_sample = read_json(paths["finite_sample"])
    program_audit = read_json(paths["program_audit"])

    biosr = load_biosr_example(args.data_root, biosr_rows)
    fmd_archive = args.data_root / "fmd" / "WideField_BPAE_R.tar"
    fmd = load_fmd_images(fmd_archive, conditional_rows, (1, 5, 14, 20))

    outputs = {
        "figure_1": figure1(biosr, biosr_rows, fmd, conditional_rows, conditional_development),
        "figure_2": figure2(biosr, biosr_rows, biosr_receipt),
        "figure_3": figure3(fmd, v13_development, v13_confirmation, v13_audit),
        "figure_4": figure4(
            fmd,
            conditional_rows,
            conditional_development,
            conditional_audit,
            finite_sample,
            program_audit,
        ),
    }
    manifest = build_manifest(
        outputs=outputs,
        source_paths=list(paths.values()),
        biosr_archive=biosr["archive"],
        fmd_archive=fmd_archive,
    )
    print(json.dumps({"status": "complete", "figures": outputs, "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
