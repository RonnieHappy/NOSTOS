"""Render the publication-style NOSTOS BioSR small-pilot audit figure."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from nostos.validation.paired_acquisition_support import read_mrc_bytes, risk_coverage_curve, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PALETTE = {
    "blue": "#0F4D92",
    "blue_2": "#3775BA",
    "green": "#4F9D69",
    "red": "#B64342",
    "red_light": "#F6CFCB",
    "gray": "#CFCECE",
    "dark": "#272727",
    "teal": "#42949E",
    "violet": "#9A4D8E",
}


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _representative_image(archive: Path, index_path: Path, cell: str, level: int) -> tuple[np.ndarray, np.ndarray, float, float]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    record = next(
        item
        for item in index["records"]
        if item["cell_id"] == cell and int(item["signal_level"]) == level
    )
    with zipfile.ZipFile(archive) as opened:
        raw = read_mrc_bytes(opened.read(record["input_member"]))
        reference = read_mrc_bytes(opened.read(record["reference_member"]))
    return (
        np.mean(raw.astype(np.float64), axis=0),
        np.asarray(reference, dtype=float),
        float(record["input_grid_spacing_um"]),
        float(record["reference_spacing_um"]),
    )


def _unit_image(image: np.ndarray) -> np.ndarray:
    low, high = np.quantile(image, [0.01, 0.995])
    return np.clip((image - low) / max(high - low, np.finfo(float).eps), 0, 1)


def _spectrum(image: np.ndarray) -> np.ndarray:
    normalized = _unit_image(image)
    window = np.outer(np.hanning(image.shape[0]), np.hanning(image.shape[1]))
    power = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2((normalized - normalized.mean()) * window))))
    return _unit_image(power)


def _center_crop(image: np.ndarray, fraction: float = 0.62) -> np.ndarray:
    height, width = image.shape
    crop_height, crop_width = int(height * fraction), int(width * fraction)
    y0, x0 = (height - crop_height) // 2, (width - crop_width) // 2
    return image[y0 : y0 + crop_height, x0 : x0 + crop_width]


def _image_panel(ax: plt.Axes, image: np.ndarray, spacing_um: float, title: str) -> None:
    crop = _center_crop(image)
    ax.imshow(_unit_image(crop), cmap="gray", interpolation="nearest")
    ax.set_title(title, loc="left", fontsize=10, fontweight="bold", pad=4)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    bar_um = 5.0
    bar_pixels = bar_um / spacing_um
    x0 = crop.shape[1] * 0.06
    x1 = x0 + bar_pixels
    y = crop.shape[0] * 0.91
    ax.plot([x0, x1], [y, y], color="white", linewidth=3, solid_capstyle="butt")
    ax.text((x0 + x1) / 2, y - crop.shape[0] * 0.035, "5 µm", color="white", fontsize=7, ha="center", va="bottom")
    inset = ax.inset_axes([0.70, 0.04, 0.26, 0.26])
    inset.imshow(_spectrum(crop), cmap="magma", interpolation="nearest")
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_edgecolor("white")
        spine.set_linewidth(0.7)


def _endpoint_matrix(ax: plt.Axes, rows: list[dict[str, Any]], profile: dict[str, Any]) -> None:
    endpoint_order = [
        "hessian_blob_curve",
        "hessian_tube_curve",
        "spectral_anisotropy",
        "spectral_entropy",
        "tensor_coherence",
        "tensor_orientation",
        "variogram_horizontal_curve",
        "variogram_vertical_curve",
        "variogram_range_horizontal",
        "variogram_range_vertical",
        "hessian_blob_scale",
        "hessian_tube_scale",
        "spectral_scale",
    ]
    labels = [
        "Blob curve",
        "Tube curve",
        "Anisotropy",
        "Entropy",
        "Coherence",
        "Orientation",
        "Variogram H",
        "Variogram V",
        "Range H",
        "Range V",
        "Blob scale",
        "Tube scale",
        "Spectral scale",
    ]
    structures = ["CCPs", "ER"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for structure in structures:
        for endpoint in endpoint_order:
            grouped[(structure, endpoint)] = [
                row for row in rows if row["structure"] == structure and row["endpoint"] == endpoint
            ]
    cmap = LinearSegmentedColormap.from_list("validity", ["#E7F2FA", "#F5B4AD", PALETTE["red"]])
    ax.set_xlim(0, 2)
    ax.set_ylim(0, len(endpoint_order))
    for y_index, endpoint in enumerate(endpoint_order):
        y = len(endpoint_order) - 1 - y_index
        for x, structure in enumerate(structures):
            subset = grouped[(structure, endpoint)]
            registered = [row for row in subset if row["pair_registration_eligible"]]
            eligible = [row for row in registered if row["reference_eligible"]]
            disabled = endpoint in profile["disabled_for_this_acquisition_profile"]
            if disabled:
                patch = Rectangle((x, y), 1, 1, facecolor="#ECECEC", edgecolor="white", hatch="////", linewidth=1)
                ax.add_patch(patch)
                annotation = "OFF"
                color = PALETTE["dark"]
            elif not eligible:
                patch = Rectangle((x, y), 1, 1, facecolor="#E5E5E5", edgecolor="white", linewidth=1)
                ax.add_patch(patch)
                annotation = "—"
                color = "#767676"
            else:
                invalid_fraction = np.mean([bool(row["invalid"]) for row in eligible])
                patch = Rectangle((x, y), 1, 1, facecolor=cmap(min(1.0, invalid_fraction)), edgecolor="white", linewidth=1)
                ax.add_patch(patch)
                annotation = "0%" if invalid_fraction == 0 else f"{100 * invalid_fraction:.0f}%"
                color = PALETTE["blue"] if invalid_fraction == 0 else PALETTE["dark"]
            ax.text(x + 0.5, y + 0.5, annotation, ha="center", va="center", fontsize=8, color=color, fontweight="bold")
    ax.set_xticks([0.5, 1.5], structures, fontsize=9, fontweight="bold")
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(endpoint_order)) + 0.5, labels[::-1], fontsize=7.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Endpoint audit", loc="left", fontsize=10, fontweight="bold", pad=8)


def _risk_panel(ax: plt.Axes, claim_rows: list[dict[str, Any]]) -> None:
    conditions = [
        ("full_contract", "NOSTOS contract", PALETTE["blue"], 2.5),
        ("conventional_acquisition_qc", "Acquisition QC", PALETTE["red"], 1.7),
        ("perturbation_stability_only", "Perturbation only", PALETTE["green"], 1.7),
    ]
    for condition, label, color, width in conditions:
        curve = risk_coverage_curve(claim_rows, condition)
        x = [0.0, *[float(point["coverage"]) for point in curve]]
        y = [0.0, *[float(point["risk"]) for point in curve]]
        ax.step(x, y, where="post", color=color, linewidth=width, label=label)
    baseline = np.mean([bool(row["invalid"]) for row in claim_rows if row["pair_registration_eligible"] and row["reference_eligible"]])
    ax.axhline(baseline, color="#767676", linewidth=1.3, linestyle=(0, (4, 3)), label="Always emit")
    ax.axhline(0.10, color=PALETTE["dark"], linewidth=0.8, linestyle=":")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 0.13)
    ax.set_xlabel("Coverage", fontsize=9)
    ax.set_ylabel("Invalid among accepted", fontsize=9)
    ax.set_title("Risk–coverage", loc="left", fontsize=10, fontweight="bold")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncol=2)
    ax.tick_params(labelsize=8, width=1)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7)


def _coherence_panel(ax: plt.Axes, rows: list[dict[str, Any]]) -> None:
    subset = [
        row
        for row in rows
        if row["structure"] == "ER"
        and row["endpoint"] == "tensor_coherence"
        and row["pair_registration_eligible"]
        and row["reference_eligible"]
    ]
    rng = np.random.default_rng(26082801)
    for level in range(1, 7):
        values = [float(row["error"]) for row in subset if int(row["metadata"]["signal_level_ordinal"]) == level]
        jitter = rng.uniform(-0.18, 0.18, len(values))
        colors = [PALETTE["red"] if value > 0.15 else PALETTE["blue_2"] for value in values]
        ax.scatter(level + jitter, values, s=10, c=colors, alpha=0.55, linewidths=0)
        ax.plot([level - 0.22, level + 0.22], [np.median(values)] * 2, color=PALETTE["dark"], linewidth=2)
    ax.axhline(0.15, color=PALETTE["red"], linestyle=(0, (4, 3)), linewidth=1.2)
    ax.set_xlim(0.5, 6.5)
    ax.set_ylim(0, max(0.36, ax.get_ylim()[1]))
    ax.set_xticks(range(1, 7))
    ax.set_xlabel("Signal level", fontsize=9)
    ax.set_ylabel("Absolute coherence error", fontsize=9)
    ax.set_title("ER coherence is signal-dependent", loc="left", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=8, width=1)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7)


def _curve_panel(ax: plt.Axes, rows: list[dict[str, Any]], scales: list[float]) -> None:
    selected = [
        row
        for row in rows
        if row["structure"] == "CCPs"
        and row["metadata"]["cell_id"] == "Cell_001"
        and int(row["metadata"]["signal_level_ordinal"]) == 9
        and row["endpoint"] in {"hessian_blob_curve", "hessian_tube_curve"}
    ]
    colors = {"hessian_blob_curve": PALETTE["violet"], "hessian_tube_curve": PALETTE["teal"]}
    for row in selected:
        label = "Blob" if row["endpoint"] == "hessian_blob_curve" else "Tube"
        color = colors[row["endpoint"]]
        ax.plot(scales, row["reference_measurement"], color=color, linewidth=2.2, label=f"{label} · reference")
        ax.plot(scales, row["input_measurement"], color=color, linewidth=1.6, linestyle="--", alpha=0.8, label=f"{label} · input")
    ax.set_xscale("log", base=2)
    ax.set_xticks(scales, [f"{value:.2f}" for value in scales])
    ax.set_xlabel("Physical scale (µm)", fontsize=9)
    ax.set_ylabel("Normalized response", fontsize=9)
    ax.set_ylim(-0.03, 1.05)
    ax.set_title("Curves survive; boundary scalars do not", loc="left", fontsize=10, fontweight="bold")
    ax.legend(frameon=False, fontsize=7.2, ncol=2, loc="upper right")
    ax.tick_params(labelsize=8, width=1)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7)


def _panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.08, 1.05, label, transform=ax.transAxes, fontsize=12, fontweight="bold", va="top")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ccp-archive", type=Path, required=True)
    parser.add_argument("--er-archive", type=Path, required=True)
    parser.add_argument("--ccp-index", type=Path, default=PROJECT_ROOT / "outputs" / "nostos0-biosr-ccp-small-pilot-v5" / "pair_index.json")
    parser.add_argument("--er-index", type=Path, default=PROJECT_ROOT / "outputs" / "nostos0-biosr-er-small-pilot-v5" / "pair_index.json")
    parser.add_argument("--ccp-rows", type=Path, default=PROJECT_ROOT / "outputs" / "nostos0-biosr-ccp-small-pilot-v5" / "endpoint_cases.jsonl")
    parser.add_argument("--er-rows", type=Path, default=PROJECT_ROOT / "outputs" / "nostos0-biosr-er-small-pilot-v5" / "endpoint_cases.jsonl")
    parser.add_argument("--profile", type=Path, default=PROJECT_ROOT / "configs" / "biosr_widefield_measurement_profile_v1.locked.json")
    parser.add_argument("--audit", type=Path, default=PROJECT_ROOT / "outputs" / "nostos0-biosr-small-pilot-v5-audit" / "pilot_audit.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "figures" / "nostos0" / "figure_small_pilot_v5_audit")
    args = parser.parse_args()

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 9,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 1.2,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    rows = _read_rows(args.ccp_rows) + _read_rows(args.er_rows)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    claim_endpoints = set(profile["eligible_for_threshold_calibration"])
    claim_rows = [row for row in rows if row["endpoint"] in claim_endpoints]
    ccp_raw, ccp_ref, ccp_spacing, ccp_ref_spacing = _representative_image(
        args.ccp_archive, args.ccp_index, "Cell_001", 9
    )
    er_raw, er_ref, er_spacing, er_ref_spacing = _representative_image(
        args.er_archive, args.er_index, "Cell_002", 6
    )

    fig = plt.figure(figsize=(13.6, 10.2), facecolor="white")
    grid = fig.add_gridspec(3, 4, height_ratios=(0.82, 1.08, 1.0), hspace=0.52, wspace=0.42)
    axes = [fig.add_subplot(grid[0, index]) for index in range(4)]
    _image_panel(axes[0], ccp_raw, ccp_spacing, "CCP · input")
    _image_panel(axes[1], ccp_ref, ccp_ref_spacing, "CCP · reference")
    _image_panel(axes[2], er_raw, er_spacing, "ER · input")
    _image_panel(axes[3], er_ref, er_ref_spacing, "ER · reference")
    for axis, label in zip(axes, "abcd", strict=True):
        _panel_label(axis, label)

    matrix_ax = fig.add_subplot(grid[1, :2])
    risk_ax = fig.add_subplot(grid[1, 2:])
    coherence_ax = fig.add_subplot(grid[2, :2])
    curve_ax = fig.add_subplot(grid[2, 2:])
    _endpoint_matrix(matrix_ax, rows, profile)
    _risk_panel(risk_ax, claim_rows)
    _coherence_panel(coherence_ax, rows)
    _curve_panel(curve_ax, rows, [float(value) for value in json.loads((PROJECT_ROOT / "configs" / "paired_acquisition_support_v5.locked.json").read_text())["physical_scales_um"]])
    for axis, label in zip((matrix_ax, risk_ax, coherence_ax, curve_ax), "efgh", strict=True):
        _panel_label(axis, label)

    fig.suptitle(
        "NOSTOS-0 small-pilot audit · 12 fields · 90 paired acquisitions",
        x=0.055,
        y=0.995,
        ha="left",
        fontsize=15,
        fontweight="bold",
        color=PALETTE["dark"],
    )
    fig.text(
        0.945,
        0.987,
        f"claim AURC {audit['claim_endpoint_summary']['aurc']['full_contract']:.4f}",
        ha="right",
        va="top",
        fontsize=8.5,
        color=PALETTE["blue"],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix in (".png", ".svg", ".pdf"):
        destination = args.output.with_suffix(suffix)
        fig.savefig(destination, dpi=300, bbox_inches="tight", pad_inches=0.06, facecolor="white")
        outputs.append(destination)
    plt.close(fig)

    manifest = {
        "schema_version": "nostos-figure-provenance/1.0",
        "figure": "small_pilot_v5_audit",
        "generator": str(Path(__file__).relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "generator_sha256": sha256_file(Path(__file__)),
        "inputs": [
            {"path": str(path), "sha256": sha256_file(path)}
            for path in (args.ccp_index, args.er_index, args.ccp_rows, args.er_rows, args.profile, args.audit)
        ],
        "representatives": {"CCPs": "Cell_001 level_09", "ER": "Cell_002 level_06"},
        "outputs": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in outputs
        ],
        "claim_boundary": "Developmental visualization of the receipted twelve-field pilot; not confirmation or clinical validation.",
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outputs": [str(path) for path in outputs], "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
