from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D

from nostos.validation.local_orientation import _axial_errors, _tensor_fields
from nostos.validation.tlt_pshg_xrd_audit import _select_nearest_ties
from nostos.validation.tlt_pshg_xrd_transfer import (
    PIXEL_SPACING_UM,
    _input_support,
    _transform,
    load_region_file,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(r"<DATA_ROOT>\public\tlt_pshg_xrd_v1")
RESULT_ROOT = ROOT / "outputs" / "nostos0-tlt-pshg-xrd-v1-confirmation"
OUTPUT_ROOT = ROOT / "figures" / "nostos0_tlt_pshg_xrd_transfer"

BLUE = "#0F4D92"
TEAL = "#2B8C8E"
ORANGE = "#D97935"
RED = "#B64342"
INK = "#171717"
GRAY = "#8A8A8A"
LIGHT = "#D9DEE4"
ZONE_COLORS = {"NM": "#65717C", "EM": "#D99A3D", "LM": "#8A4F8D"}
SAMPLE_MARKERS = {"Sample2": "o", "Sample4": "s"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.size": 9,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def panel_letter(ax: plt.Axes, letter: str) -> None:
    ax.text(
        -0.07,
        1.045,
        letter,
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="bottom",
        ha="right",
        color=INK,
    )


def image_panel(
    ax: plt.Axes,
    image: np.ndarray,
    *,
    cmap: str,
    vmin: float | None = None,
    vmax: float | None = None,
    label: str,
    colorbar: bool = False,
) -> None:
    artist = ax.imshow(image, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(label, loc="left", pad=2.5, fontsize=8, fontweight="bold", color=INK)
    if colorbar:
        cbar = plt.colorbar(artist, ax=ax, fraction=0.045, pad=0.018)
        cbar.ax.tick_params(labelsize=7, length=2)
        cbar.outline.set_linewidth(0.5)


def risk_curve(rows: list[dict], policy: str) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(rows, key=lambda row: (row["scores"][policy], row["case_id"]))
    coverage = [0.0]
    risk = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        score = ordered[index]["scores"][policy]
        end = index
        while end < len(ordered) and ordered[end]["scores"][policy] == score:
            invalid += int(ordered[end]["invalid"])
            end += 1
        coverage.append(end / len(ordered))
        risk.append(invalid / end)
        index = end
    return np.asarray(coverage), np.asarray(risk)


def main() -> None:
    style()
    result_path = RESULT_ROOT / "confirmation.json"
    rows_path = RESULT_ROOT / "confirmation_rows.jsonl"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]

    representative_file = DATA_ROOT / "Sample2NM.mat"
    representative = load_region_file(representative_file)[7]
    image = _transform(representative["shg"], "log1p")
    angles, coherence, _ = _tensor_fields(
        image,
        scales=(12.0 / PIXEL_SPACING_UM, 6.0 / PIXEL_SPACING_UM),
    )
    support = _input_support(image, 16)
    phi2 = np.mod(representative["phi2_reference"], 180.0)
    i2 = representative["i2_reference"]
    reference_mask = np.isfinite(phi2)
    orientation = np.where(support, angles[0], np.nan)
    reference = np.where(reference_mask, phi2, np.nan)
    error = np.full(phi2.shape, np.nan)
    common = support & reference_mask
    error[common] = _axial_errors(angles[0][common], phi2[common])
    coherence_map = np.where(support, coherence[0], np.nan)
    i2_map = np.where(np.isfinite(i2), i2, np.nan)

    fig = plt.figure(figsize=(7.08, 6.38), facecolor="white")
    outer = fig.add_gridspec(
        2,
        2,
        width_ratios=(1.82, 1.0),
        height_ratios=(1, 1),
        wspace=0.22,
        hspace=0.18,
        left=0.050,
        right=0.985,
        bottom=0.075,
        top=0.965,
    )
    maps = outer[:, 0].subgridspec(3, 2, wspace=0.10, hspace=0.16)
    axes = [fig.add_subplot(maps[row, column]) for row in range(3) for column in range(2)]

    display = np.log1p(representative["shg"])
    image_panel(
        axes[0],
        display,
        cmap="gray",
        vmin=float(np.percentile(display, 1)),
        vmax=float(np.percentile(display, 99.7)),
        label="SHG",
    )
    panel_letter(axes[0], "a")
    bar_px = 100.0 / PIXEL_SPACING_UM
    axes[0].plot([28, 28 + bar_px], [480, 480], color="white", lw=3.0, solid_capstyle="butt")
    axes[0].text(28 + bar_px / 2, 462, "100 µm", color="white", ha="center", va="bottom", fontsize=7)

    image_panel(axes[1], orientation, cmap="twilight_shifted", vmin=0, vmax=180, label="NOSTOS θ", colorbar=False)
    panel_letter(axes[1], "b")
    image_panel(axes[2], reference, cmap="twilight_shifted", vmin=0, vmax=180, label="pSHG φ₂", colorbar=True)
    panel_letter(axes[2], "c")
    image_panel(axes[3], error, cmap="magma", vmin=0, vmax=45, label="|Δθ|", colorbar=True)
    panel_letter(axes[3], "d")
    image_panel(axes[4], coherence_map, cmap="viridis", vmin=0, vmax=1, label="NOSTOS C", colorbar=True)
    panel_letter(axes[4], "e")
    finite_i2 = i2_map[np.isfinite(i2_map)]
    image_panel(
        axes[5],
        i2_map,
        cmap="viridis",
        vmin=float(np.percentile(finite_i2, 2)),
        vmax=float(np.percentile(finite_i2, 98)),
        label="pSHG I₂",
        colorbar=True,
    )
    panel_letter(axes[5], "f")

    right = outer[:, 1].subgridspec(3, 1, height_ratios=(1.15, 0.78, 1.0), hspace=0.46)
    scatter_ax = fig.add_subplot(right[0, 0])
    clean = [row for row in rows if row["condition"] == "clean"]
    for sample in ("Sample2", "Sample4"):
        for zone in ("NM", "EM", "LM"):
            subset = [row for row in clean if row["sample"] == sample and row["zone"] == zone]
            scatter_ax.scatter(
                [row["organization_reference_mean_i2"] for row in subset],
                [row["diagnostics"]["median_coherence"] for row in subset],
                s=24,
                marker=SAMPLE_MARKERS[sample],
                facecolor=ZONE_COLORS[zone],
                edgecolor="white",
                linewidth=0.65,
                alpha=0.92,
                zorder=3,
            )
    scatter_ax.set_xlabel("pSHG I₂")
    scatter_ax.set_ylabel("NOSTOS coherence")
    scatter_ax.set_xlim(0.14, 0.43)
    scatter_ax.set_ylim(0.16, 0.88)
    scatter_ax.text(
        0.04,
        0.93,
        "ρ = 0.891",
        transform=scatter_ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color=INK,
    )
    scatter_ax.grid(color="#E8E8E8", lw=0.6, zorder=0)
    zone_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ZONE_COLORS[z], markeredgecolor="none", label=z, markersize=6)
        for z in ("NM", "EM", "LM")
    ]
    sample_handles = [
        Line2D([0], [0], marker=SAMPLE_MARKERS[s], color=GRAY, markerfacecolor="none", label=s.replace("Sample", "S"), markersize=6, linestyle="none")
        for s in ("Sample2", "Sample4")
    ]
    scatter_ax.legend(handles=zone_handles + sample_handles, ncol=5, loc="lower right", fontsize=6.2, handletextpad=0.2, columnspacing=0.55)
    panel_letter(scatter_ax, "g")

    dot_ax = fig.add_subplot(right[1, 0])
    target = result["summary"]["matched_coverage"]["full_contract"]["accepted"]
    policies = ("acquisition_qc", "endpoint_qc", "full_contract")
    labels = ("Acq.", "Endpoint", "NOSTOS")
    selected_sets: list[list[dict]] = []
    for policy in policies[:-1]:
        candidates = [{**row, "score": row["scores"][policy]} for row in rows]
        selected_sets.append(list(_select_nearest_ties(candidates, target, "score")))
    selected_sets.append([row for row in rows if row["scores"]["full_contract"] <= 0.4])
    columns = 46
    for row_index, (selected, label) in enumerate(zip(selected_sets, labels, strict=True)):
        invalid = [row for row in selected if row["invalid"]]
        valid = [row for row in selected if not row["invalid"]]
        ordered = valid + invalid
        x = np.arange(len(ordered)) % columns
        y = -(np.arange(len(ordered)) // columns) - row_index * 6.2
        colors = [LIGHT] * len(valid) + [RED] * len(invalid)
        dot_ax.scatter(x, y, s=5.2, c=colors, edgecolors="none")
        dot_ax.text(-2.0, -row_index * 6.2 - 2.0, label, ha="right", va="center", fontsize=8)
        dot_ax.text(columns + 0.6, -row_index * 6.2 - 2.0, str(len(invalid)), ha="left", va="center", fontsize=10, color=RED, fontweight="bold")
    dot_ax.set_xlim(-8, columns + 6)
    dot_ax.set_ylim(-17.2, 1.2)
    dot_ax.set_axis_off()
    panel_letter(dot_ax, "h")

    curve_ax = fig.add_subplot(right[2, 0])
    for policy, label, color, width in (
        ("acquisition_qc", "Acq.", GRAY, 1.8),
        ("endpoint_qc", "Endpoint", ORANGE, 2.0),
        ("full_contract", "NOSTOS", BLUE, 2.6),
    ):
        coverage, risk = risk_curve(rows, policy)
        curve_ax.plot(coverage, risk, color=color, lw=width, label=label)
    curve_ax.axvline(target / len(rows), color="#B8B8B8", lw=0.8, ls=(0, (2, 2)))
    curve_ax.set_xlim(0, 1)
    curve_ax.set_ylim(0, 0.58)
    curve_ax.set_xlabel("Coverage")
    curve_ax.set_ylabel("Silent-invalid risk")
    curve_ax.grid(color="#E8E8E8", lw=0.6)
    curve_ax.legend(loc="upper left", ncol=3, fontsize=8, handlelength=1.8, columnspacing=1.0)
    panel_letter(curve_ax, "i")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    base = OUTPUT_ROOT / "figure_tlt_pshg_xrd_transfer"
    fig.savefig(base.with_suffix(".png"), dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.035)
    fig.savefig(base.with_suffix(".pdf"), dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.035)
    fig.savefig(base.with_suffix(".svg"), dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)

    manifest = {
        "schema_version": "nostos.figure.tlt_pshg_xrd_transfer.v1",
        "representative_selection": "SHA-256-first confirmation field under salt nostos_tlt_figure_v1; Sample2-NM-07, not outcome selected",
        "representative_field_id": "Sample2-NM-07",
        "representative_selection_sha256": "04efec23542d52cce23d7b4d2b724b86799638b2f89851fa05099ddef8e936f5",
        "representative_source": str(representative_file),
        "representative_source_md5": hashlib.md5(representative_file.read_bytes()).hexdigest(),
        "result_path": result_path.relative_to(ROOT).as_posix(),
        "result_sha256": sha256(result_path),
        "rows_path": rows_path.relative_to(ROOT).as_posix(),
        "rows_sha256": sha256(rows_path),
        "panels": {
            "a": "deposited mean SHG intensity",
            "b": "NOSTOS 12-um local orientation",
            "c": "withheld deposited pSHG Phi2 orientation",
            "d": "pixelwise axial error on common support",
            "e": "NOSTOS local tensor coherence",
            "f": "withheld deposited pSHG I2 organization",
            "g": "37 clean fields; field-level single-image coherence versus pSHG I2",
            "h": "complete tied-score selections nearest to 229 accepted cases; red marks invalid outputs",
            "i": "tied-score risk-coverage curves over all 592 programmed cases",
        },
        "claim_boundary": "Qualified second-acquisition-family evidence; preregistered overall status remains fail because coverage and clean-preservation gates were missed.",
    }
    manifest_path = base.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for suffix in (".png", ".pdf", ".svg", ".manifest.json"):
        path = base.with_suffix(suffix)
        print(path, path.stat().st_size, sha256(path))


if __name__ == "__main__":
    main()
