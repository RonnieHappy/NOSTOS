"""Build the verified PSHG acquisition-shift megafigure.

All microscopy pixels and quantitative summaries are deterministic products of
the hash-locked PSHG-TISS archive and frozen NOSTOS receipts. BioRender is used
only for the explicitly illustrative, text-free workflow panel.
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
import tifffile
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.font_manager import findfont
from PIL import Image

from nostos.validation.local_orientation import _tensor_fields
from nostos.validation.pshg_acquisition_shift import apply_condition


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0_pshg_acquisition_shift"
BIORENDER = ROOT / "figures" / "nostos0_biorender" / "biorender_pshg_acquisition_shift_v33_textfree.png"
CONFIG = ROOT / "configs" / "pshg_acquisition_shift_v1.locked.json"
PROFILE = ROOT / "outputs" / "nostos0-pshg-acquisition-shift-v1-development" / "validity_profile.json"
RESULT = ROOT / "outputs" / "nostos0-pshg-acquisition-shift-v1-confirmation" / "confirmation.json"
ROWS = ROOT / "outputs" / "nostos0-pshg-acquisition-shift-v1-confirmation" / "confirmation_rows.jsonl"
LOCK = ROOT / "manifests" / "pshg_acquisition_shift_v1_confirmation.lock.json"
AUDIT = ROOT / "outputs" / "nostos0-pshg-acquisition-shift-v1-audit" / "audit.json"

INK = "#17212B"
MID = "#66727E"
LIGHT = "#D7DEE5"
PALE = "#EEF2F5"
TEAL = "#087F8C"
TEAL_LIGHT = "#A5DCDA"
CORAL = "#D96355"
CORAL_DARK = "#9E2E3E"
WHITE = "#FFFFFF"
RISK_CMAP = LinearSegmentedColormap.from_list(
    "nostos_risk", ["#E5F4F2", TEAL_LIGHT, "#F4D5C8", CORAL, CORAL_DARK]
)
POLICIES = ("acquisition_qc", "endpoint_qc", "full_contract")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_times() -> str:
    return findfont("Times New Roman", fallback_to_default=False)


TIMES_PATH = require_times()
mpl.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "font.size": 7.8,
        "axes.labelsize": 7.8,
        "axes.titlesize": 8.1,
        "axes.linewidth": 0.65,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 6.8,
        "ytick.labelsize": 6.8,
        "legend.fontsize": 6.8,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "svg.hashsalt": "nostos-pshg-acquisition-shift-v1",
        "savefig.facecolor": "white",
    }
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def panel(ax: mpl.axes.Axes, letter: str, *, x: float = -0.035, y: float = 1.03) -> None:
    ax.text(
        x,
        y,
        letter,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=11.5,
        fontweight="bold",
        color=INK,
        clip_on=False,
        zorder=100,
    )


def _crop_art(path: Path, padding: int = 10) -> np.ndarray:
    with Image.open(path) as source:
        rgb = np.asarray(source.convert("RGB"))
    content = np.any(rgb < 244, axis=2)
    yy, xx = np.where(content)
    if not len(xx):
        raise RuntimeError(f"No visible BioRender content in {path}.")
    x0, x1 = max(0, int(xx.min()) - padding), min(rgb.shape[1], int(xx.max()) + padding + 1)
    y0, y1 = max(0, int(yy.min()) - padding), min(rgb.shape[0], int(yy.max()) + padding + 1)
    return rgb[y0:y1, x0:x1]


def draw_workflow(ax: mpl.axes.Axes) -> None:
    art = _crop_art(BIORENDER)
    ax.imshow(art, interpolation="lanczos")
    ax.axis("off")
    labels = ((0.08, "PSHG"), (0.275, "10 frames"), (0.475, "shift"), (0.655, "orientation"), (0.835, "support"), (0.955, "decision"))
    for x, label in labels:
        ax.text(x, -0.025, label, transform=ax.transAxes, ha="center", va="top", fontsize=7.3, color=INK)
    panel(ax, "a", x=-0.012, y=0.98)


def _normalize(image: np.ndarray) -> np.ndarray:
    finite = image[np.isfinite(image)]
    low, high = np.percentile(finite, (1.0, 99.5))
    return np.clip((image - low) / max(high - low, np.finfo(float).eps), 0.0, 1.0)


def _orientation_rgb(angle: np.ndarray, support: np.ndarray) -> np.ndarray:
    hue = np.mod(angle, 180.0) / 180.0
    rgba = mpl.colormaps["twilight_shifted"](hue)
    rgba[..., 3] = np.where(support, 1.0, 0.0)
    rgba[~support, :3] = 1.0
    return rgba


def _segments(angle: np.ndarray, support: np.ndarray, step: int = 18, length: float = 11.0) -> LineCollection:
    ys = np.arange(step // 2, angle.shape[0], step)
    xs = np.arange(step // 2, angle.shape[1], step)
    segments = []
    colors = []
    for y in ys:
        for x in xs:
            if not support[y, x] or not np.isfinite(angle[y, x]):
                continue
            theta = np.deg2rad(angle[y, x])
            dx = 0.5 * length * np.cos(theta)
            dy = 0.5 * length * np.sin(theta)
            segments.append(((x - dx, y - dy), (x + dx, y + dy)))
            colors.append(mpl.colormaps["twilight_shifted"]((angle[y, x] % 180.0) / 180.0))
    return LineCollection(segments, colors=colors, linewidths=0.75, alpha=0.95)


def _load_pshg(dataset: Path, roi: str, config: Mapping[str, Any]) -> dict[str, np.ndarray]:
    root = dataset / roi
    frame_paths = sorted(root.glob("*_FSHG_p*.tif"), key=lambda path: int(path.stem.rsplit("p", 1)[1]))
    frames = np.stack([tifffile.imread(path).astype(np.float64) for path in frame_paths])
    fi = tifffile.imread(root / "FI.tif").astype(np.float64)
    r2 = tifffile.imread(root / "R2.tif").astype(np.float64)
    snr = tifffile.imread(root / "SNR.tif").astype(np.float64)
    clean = np.mean(frames, axis=0)
    edge = int(config["measurement"]["edge_exclusion_pixels"])
    support = np.isfinite(fi) & np.isfinite(r2) & np.isfinite(snr)
    support &= r2 >= float(config["measurement"]["minimum_reference_r2"])
    support &= snr >= float(config["measurement"]["minimum_reference_snr_db"])
    support &= clean > 0
    support[:edge] = False
    support[-edge:] = False
    support[:, :edge] = False
    support[:, -edge:] = False
    severe_cfg = next(item for item in config["conditions"] if item["id"] == "compound_severe")
    severe_frames = apply_condition(frames, severe_cfg, roi_name=roi, seed=int(config["calibration"]["seed"]))
    severe = np.mean(severe_frames, axis=0)
    clean_angle = _tensor_fields(clean, scales=(float(config["measurement"]["integration_sigma_pixels"]),))[0][0]
    severe_angle = _tensor_fields(severe, scales=(float(config["measurement"]["integration_sigma_pixels"]),))[0][0]
    reference = np.mod(fi + float(config["measurement"]["reference_offset_degrees"]), 180.0)
    return {
        "clean": clean,
        "severe": severe,
        "clean_angle": clean_angle,
        "severe_angle": severe_angle,
        "reference": reference,
        "support": support,
    }


def draw_microscopy(row_axes: Sequence[mpl.axes.Axes], data: Mapping[str, np.ndarray], roi: str) -> None:
    clean, severe, support = data["clean"], data["severe"], data["support"]
    items = (
        (row_axes[0], _normalize(clean), "clean FSHG", "gray"),
        (row_axes[1], _normalize(severe), "severe shift", "gray"),
        (row_axes[2], _orientation_rgb(data["severe_angle"], support), "NOSTOS", None),
        (row_axes[3], _orientation_rgb(data["reference"], support), "polarization reference", None),
    )
    for ax, image, label, cmap in items:
        ax.imshow(image, cmap=cmap, interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(label, pad=3.0, fontweight="bold")
    row_axes[2].add_collection(_segments(data["severe_angle"], support))
    row_axes[3].add_collection(_segments(data["reference"], support))
    panel(row_axes[0], "a", x=-0.05, y=1.08)
    row_axes[0].text(0.02, 0.04, roi, transform=row_axes[0].transAxes, color=WHITE, fontsize=6.8, fontweight="bold")


def _annotate(rows: Sequence[Mapping[str, Any]], profile: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for policy in POLICIES:
        risk_map = profile["risk_maps"][policy]
        x = np.asarray(risk_map["x_thresholds"], dtype=float)
        y = np.asarray(risk_map["y_thresholds"], dtype=float)
        annotated = []
        for row in rows:
            clone = dict(row)
            clone["calibrated_risk"] = float(np.interp(float(row["scores"][policy]), x, y, left=y[0], right=y[-1]))
            annotated.append(clone)
        output[policy] = annotated
    return output


def draw_condition_matrix(ax: mpl.axes.Axes, policy_rows: Mapping[str, Sequence[Mapping[str, Any]]], threshold: float, conditions: Sequence[str]) -> None:
    short = {
        "clean": "clean", "blur_sigma_1": "b1", "blur_sigma_2": "b2", "blur_sigma_4": "b4",
        "noise_snr_20": "n20", "noise_snr_10": "n10", "noise_snr_5": "n5",
        "motion_radius_1": "m1", "motion_radius_2": "m2", "motion_radius_4": "m4",
        "resample_factor_2": "r2", "resample_factor_4": "r4", "contrast_factor_0_25": "c.25",
        "compound_moderate": "mix", "compound_severe": "severe",
    }
    for iy, policy in enumerate(POLICIES):
        for ix, condition in enumerate(conditions):
            subset = [row for row in policy_rows[policy] if row["condition"] == condition]
            accepted = [row for row in subset if float(row["calibrated_risk"]) <= threshold]
            coverage = len(accepted) / len(subset)
            risk = np.mean([bool(row["invalid"]) for row in accepted]) if accepted else np.nan
            if accepted:
                ax.scatter(ix, iy, s=18 + 180 * coverage, c=[RISK_CMAP(min(float(risk) / 0.45, 1.0))], edgecolors=INK, linewidths=0.45)
            else:
                ax.scatter(ix, iy, s=42, marker="x", c=MID, linewidths=0.9)
    ax.set_xlim(-0.7, len(conditions) - 0.3)
    ax.set_ylim(len(POLICIES) - 0.45, -0.55)
    ax.set_xticks(range(len(conditions)), [short[name] for name in conditions], rotation=55, ha="right")
    ax.set_yticks(range(len(POLICIES)), ["acquisition QC", "endpoint QC", "NOSTOS"])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(color=PALE, linewidth=0.55)
    panel(ax, "b", x=-0.02, y=1.04)
    norm = Normalize(0.0, 0.45)
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=RISK_CMAP)
    cbar = ax.figure.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.08, pad=0.22, aspect=35)
    cbar.set_label("invalid among accepted")
    cbar.outline.set_visible(False)
    cbar.set_ticks([0.0, 0.15, 0.30, 0.45], labels=["0", "0.15", "0.30", "≥0.45"])
    ax.text(1.0, 1.025, "area = coverage", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.6, color=MID)


def _curve(rows: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(rows, key=lambda row: (float(row["calibrated_risk"]), str(row["case_id"])))
    coverage = [0.0]
    risk = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        score = float(ordered[index]["calibrated_risk"])
        end = index
        while end < len(ordered) and float(ordered[end]["calibrated_risk"]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage.append(end / len(ordered))
        risk.append(invalid / end)
        index = end
    return np.asarray(coverage), np.asarray(risk)


def draw_risk_coverage(ax: mpl.axes.Axes, policy_rows: Mapping[str, Sequence[Mapping[str, Any]]], result: Mapping[str, Any]) -> None:
    style = {
        "acquisition_qc": (MID, "--", "acquisition QC"),
        "endpoint_qc": (CORAL, "-.", "endpoint QC"),
        "full_contract": (TEAL, "-", "NOSTOS"),
    }
    for policy in POLICIES:
        coverage, risk = _curve(policy_rows[policy])
        color, linestyle, label = style[policy]
        ax.plot(coverage, risk, color=color, linestyle=linestyle, linewidth=1.8, marker="o", markersize=2.8, label=label)
    full = result["summary"]["operating"]["full_contract"]
    ax.scatter(full["coverage"], full["risk"], s=45, facecolor=TEAL, edgecolor=WHITE, linewidth=0.8, zorder=10)
    ax.axhline(0.15, color=LIGHT, linewidth=0.8, linestyle=":")
    ax.set(xlim=(0, 1.02), ylim=(0, 0.24), xlabel="coverage", ylabel="silent-invalid risk")
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_yticks([0, 0.1, 0.2])
    ax.grid(color=PALE, linewidth=0.65)
    ax.spines["left"].set_color(LIGHT)
    ax.spines["bottom"].set_color(LIGHT)
    ax.legend(loc="upper left")
    panel(ax, "c", x=-0.10, y=1.04)


def draw_matched_dots(ax: mpl.axes.Axes, matched: Mapping[str, Any]) -> None:
    methods = (("acquisition QC", "acquisition_qc"), ("endpoint QC", "endpoint_qc"), ("NOSTOS", "full_contract"))
    columns = 23
    rows_per = 10
    for group, (label, key) in enumerate(methods):
        invalid = int(matched[key]["invalid"])
        total = int(matched[key]["accepted"])
        index = np.arange(total)
        xx = index % columns
        yy = group * (rows_per + 2) + index // columns
        colors = np.where(index < invalid, CORAL, TEAL_LIGHT)
        ax.scatter(xx, -yy, s=9.5, c=colors, edgecolors="none")
        y_mid = -(group * (rows_per + 2) + 4.5)
        ax.text(-1.7, y_mid, label, ha="right", va="center", fontsize=7.2, color=INK)
        ax.text(columns + 0.4, y_mid, f"{invalid}/230", ha="left", va="center", fontsize=8.6, fontweight="bold", color=CORAL_DARK if invalid else TEAL)
    ax.set_xlim(-8.0, columns + 5.5)
    ax.set_ylim(-(len(methods) * (rows_per + 2) - 2), 1)
    ax.axis("off")
    ax.text(0.0, 1.01, "matched 63.9% coverage", transform=ax.transAxes, ha="left", va="bottom", fontsize=7.6, color=INK)
    ax.scatter([], [], s=12, c=CORAL, label="invalid")
    ax.scatter([], [], s=12, c=TEAL_LIGHT, label="valid")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, -0.08), ncol=2, handletextpad=0.25, columnspacing=0.8)
    panel(ax, "d", x=-0.01, y=1.04)


def draw_intervals(ax: mpl.axes.Axes, bootstrap: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    entries = (
        ("risk: acquisition QC", float(summary["risk_reductions"]["acquisition_qc"]), bootstrap["matched_risk_difference_95"]["acquisition_qc"]),
        ("risk: endpoint QC", float(summary["risk_reductions"]["endpoint_qc"]), bootstrap["matched_risk_difference_95"]["endpoint_qc"]),
        ("AURC: acquisition QC", float(summary["aurc_differences"]["acquisition_qc"]), bootstrap["aurc_difference_95"]["acquisition_qc"]),
        ("AURC: endpoint QC", float(summary["aurc_differences"]["endpoint_qc"]), bootstrap["aurc_difference_95"]["endpoint_qc"]),
    )
    yy = np.arange(len(entries))[::-1]
    for y, (label, value, interval) in zip(yy, entries, strict=True):
        color = TEAL if "NOSTOS" not in label else CORAL
        ax.plot(interval, [y, y], color=color, linewidth=2.2, solid_capstyle="round")
        ax.scatter(value, y, s=28, facecolor=WHITE, edgecolor=color, linewidth=1.3, zorder=3)
    ax.axvline(0, color=LIGHT, linewidth=0.8)
    ax.set_yticks(yy, [item[0] for item in entries])
    ax.set_xlim(-0.005, 0.265)
    ax.set_xlabel("comparator minus NOSTOS")
    ax.grid(axis="x", color=PALE, linewidth=0.65)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    ax.tick_params(axis="y", length=0)
    panel(ax, "e", x=-0.06, y=1.04)
    ax.text(0.995, 0.02, "ROI bootstrap, 5,000", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.6, color=MID)


def save(fig: plt.Figure, stem: str) -> dict[str, dict[str, Any]]:
    OUT.mkdir(parents=True, exist_ok=True)
    output: dict[str, dict[str, Any]] = {}
    for suffix, kwargs in (
        ("png", {"dpi": 600, "metadata": {"Software": "NOSTOS"}}),
        ("pdf", {"metadata": {"Creator": "NOSTOS", "Producer": "Matplotlib", "CreationDate": None, "ModDate": None}}),
        ("svg", {"metadata": {"Creator": "NOSTOS", "Date": None}}),
    ):
        path = OUT / f"{stem}.{suffix}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.035, **kwargs)
        output[suffix] = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
    plt.close(fig)
    return output


def build(dataset: Path) -> dict[str, Any]:
    config, profile, result, lock, audit = _json(CONFIG), _json(PROFILE), _json(RESULT), _json(LOCK), _json(AUDIT)
    if result["status"] != "pass" or audit["status"] != "verified_pass":
        raise RuntimeError("The PSHG confirmation and independent audit must both pass before figure generation.")
    rows = _jsonl(ROWS)
    policy_rows = _annotate(rows, profile)
    conditions = [str(item["id"]) for item in config["conditions"]]
    roi = str(lock["split"]["confirmation"][0])
    pshg = _load_pshg(dataset, roi, config)

    fig = plt.figure(figsize=(7.08, 6.42), constrained_layout=False)
    outer = fig.add_gridspec(3, 1, height_ratios=[1.48, 2.30, 1.78], hspace=0.34)
    image_grid = outer[0].subgridspec(1, 4, wspace=0.035)
    image_axes = [fig.add_subplot(image_grid[0, index]) for index in range(4)]
    draw_microscopy(image_axes, pshg, roi)
    mid = outer[1].subgridspec(1, 2, width_ratios=[1.58, 1.0], wspace=0.34)
    ax_c, ax_d = fig.add_subplot(mid[0]), fig.add_subplot(mid[1])
    draw_condition_matrix(ax_c, policy_rows, float(profile["maximum_predicted_risk"]), conditions)
    draw_risk_coverage(ax_d, policy_rows, result)
    bottom = outer[2].subgridspec(1, 2, width_ratios=[1.28, 1.0], wspace=0.32)
    ax_e, ax_f = fig.add_subplot(bottom[0]), fig.add_subplot(bottom[1])
    draw_matched_dots(ax_e, result["summary"]["matched_coverage"])
    draw_intervals(ax_f, result["bootstrap"], result["summary"])
    fig.subplots_adjust(left=0.075, right=0.985, top=0.985, bottom=0.055)
    outputs = save(fig, "figure_pshg_acquisition_shift")
    manifest = {
        "schema_version": "nostos-pshg-acquisition-shift-figure/1.0",
        "declaration": "Every panel is a deterministic product of the checksum-locked PSHG-TISS archive and frozen NOSTOS receipts; no generated biological image or decorative workflow art is included.",
        "representative_roi_rule": "first confirmation ROI in the frozen lock; outcome independent",
        "representative_roi": roi,
        "font": {"family": "Times New Roman", "path": TIMES_PATH},
        "inputs": {
            path.relative_to(ROOT).as_posix(): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in (CONFIG, PROFILE, RESULT, ROWS, LOCK, AUDIT)
        },
        "source_manifest_sha256": audit["audited_artifacts"]["source_manifest_sha256"],
        "outputs": outputs,
    }
    manifest_path = OUT / "figure_pshg_acquisition_shift.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.dataset), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
