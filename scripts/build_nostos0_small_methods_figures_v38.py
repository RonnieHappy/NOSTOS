"""Build the final journal-polished NOSTOS Small Methods v38 figure set.

V38 preserves every scientific value and source pixel from v37 while applying
one final publication pass: smaller panel typography, calibrated scale bars
where physical spacing is available, quieter axes, and a deterministic
measurement rail whose visual hierarchy follows the supplied Small Methods
papers.  The BioRender study is retained only as a documented composition
study; no BioRender pixels enter the submitted scientific artwork.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

import build_nostos0_small_methods_figures_v37 as v37


ROOT = v37.ROOT
OUT = ROOT / "figures" / "nostos0_small_methods_v38"
ORIGINAL_IMAGE_PANEL = v37.image_panel
ORIGINAL_CLEAN_AXES = v37.clean_axes


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def panel(ax: mpl.axes.Axes, letter: str, *, inside: bool = False) -> None:
    writer = getattr(ax, "text2D", ax.text)
    writer(
        0.020 if inside else -0.048,
        0.980 if inside else 1.020,
        letter,
        transform=ax.transAxes,
        ha="left" if inside else "right",
        va="top" if inside else "bottom",
        fontsize=8.0,
        fontweight="bold",
        color=v37.WHITE if inside else v37.INK,
        clip_on=False,
        zorder=80,
    )


def _scale_bar(ax: mpl.axes.Axes, *, length_px: float, text: str) -> None:
    image = ax.images[0]
    array = np.asarray(image.get_array())
    height, width = array.shape[:2]
    x1 = width * 0.935
    x0 = x1 - length_px
    y = height * 0.910
    ax.plot([x0, x1], [y, y], color="white", linewidth=1.8, solid_capstyle="butt", zorder=90)
    ax.text(
        (x0 + x1) / 2,
        y - height * 0.035,
        text,
        ha="center",
        va="top",
        fontsize=5.1,
        color="white",
        zorder=91,
    )


def image_panel(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    label: str,
    *,
    cmap: str | mpl.colors.Colormap | None = "gray",
    vmin: float | None = None,
    vmax: float | None = None,
) -> mpl.image.AxesImage:
    result = ORIGINAL_IMAGE_PANEL(ax, image, label, cmap=cmap, vmin=vmin, vmax=vmax)
    # Retune the short object label after the inherited helper creates it.
    if ax.texts:
        ax.texts[-1].set_fontsize(6.2)
        ax.texts[-1].set_fontweight("normal")
    # BioSR reference crops retain the deposited physical field of view.  FMD
    # intentionally receives no scale bar because the archive has no spacing.
    if cmap == "gray" and label in {"paired reference", "reference"}:
        _scale_bar(ax, length_px=10.0 / 0.0313, text="10 µm")
    elif cmap == "gray" and label == "blur 4 px":
        _scale_bar(ax, length_px=10.0 / 0.0626, text="10 µm")
    return result


def clean_axes(ax: mpl.axes.Axes, *, grid: bool = True) -> None:
    ORIGINAL_CLEAN_AXES(ax, grid=False)
    if grid:
        ax.grid(axis="y", color="#E8ECEF", linewidth=0.48, zorder=0)
    ax.tick_params(length=2.0, width=0.55, color=v37.LIGHT, pad=1.55)
    ax.margins(x=0.015)


def support_matrix(
    ax: mpl.axes.Axes,
    supported: set[tuple[str, float]],
    *,
    compact: bool = False,
) -> None:
    acquisitions = ["raw", "avg2", "avg4", "avg8", "avg16"]
    scales = [4.0, 8.0, 16.0]
    matrix = np.array(
        [[1 if (acquisition, scale) in supported else 0 for scale in scales] for acquisition in acquisitions]
    )
    rgba = np.empty((*matrix.shape, 4), dtype=float)
    rgba[matrix == 1] = mpl.colors.to_rgba(v37.TEAL)
    rgba[matrix == 0] = mpl.colors.to_rgba("#F0F2F4")
    ax.imshow(rgba, aspect="auto", interpolation="nearest")
    if compact:
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        ax.set_xticks(range(3), ["4", "8", "16"])
        ax.set_yticks(range(5), ["raw", "2", "4", "8", "16"])
        ax.set_xlabel("scale [px]")
        ax.set_ylabel("captures")
    for row in range(5):
        for column in range(3):
            ax.text(
                column,
                row,
                "•" if matrix[row, column] else "×",
                ha="center",
                va="center",
                color=v37.WHITE if matrix[row, column] else v37.MID,
                fontsize=6.8 if compact else 7.1,
                fontweight="bold",
            )
    ax.tick_params(length=0, pad=1.5)
    for spine in ax.spines.values():
        spine.set_visible(False)


def measurement_rail(
    ax: mpl.axes.Axes,
    image: np.ndarray,
    orientation: np.ndarray,
    supported: set[tuple[str, float]],
) -> None:
    """Authentic image-to-decision rail with no generated scientific content."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for (x, y, width, height), data, cmap in (
        ((0.010, 0.235, 0.205, 0.530), v37.vf.robust_unit(image), "gray"),
        ((0.275, 0.235, 0.205, 0.530), orientation, None),
    ):
        inset = ax.inset_axes([x, y, width, height])
        inset.imshow(data, cmap=cmap, interpolation="nearest")
        inset.set_axis_off()
    lattice = ax.inset_axes([0.565, 0.235, 0.135, 0.530])
    support_matrix(lattice, supported, compact=True)
    for start, end in ((0.215, 0.270), (0.480, 0.558)):
        ax.add_patch(
            FancyArrowPatch(
                (start, 0.50),
                (end, 0.50),
                arrowstyle="-|>",
                mutation_scale=6.5,
                linewidth=0.70,
                color=v37.MID,
            )
        )
    ax.plot([0.700, 0.765], [0.50, 0.50], color=v37.MID, linewidth=0.70)
    ax.plot([0.765, 0.765], [0.34, 0.66], color=v37.MID, linewidth=0.70)
    for y in (0.34, 0.66):
        ax.add_patch(
            FancyArrowPatch(
                (0.765, y),
                (0.815, y),
                arrowstyle="-|>",
                mutation_scale=6.5,
                linewidth=0.70,
                color=v37.MID,
            )
        )
    ax.add_patch(Rectangle((0.825, 0.555), 0.150, 0.205, facecolor=v37.WHITE, edgecolor=v37.TEAL, linewidth=0.90))
    ax.add_patch(Rectangle((0.825, 0.240), 0.150, 0.205, facecolor=v37.WHITE, edgecolor=v37.LIGHT, linewidth=0.90))
    ax.text(0.900, 0.658, "report", ha="center", va="center", color=v37.TEAL, fontsize=5.7)
    ax.text(0.900, 0.342, "abstain", ha="center", va="center", color=v37.MID, fontsize=5.7)


def _patch_v37() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    v37.OUT = OUT
    v37.sm.OUT = OUT
    v37.old.OUT = OUT
    v37.old.sm.OUT = OUT
    v37.old.v35.OUT = OUT
    v37.panel = panel
    v37.image_panel = image_panel
    v37.clean_axes = clean_axes
    v37.support_matrix = support_matrix
    v37.measurement_rail = measurement_rail
    mpl.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.serif": ["Times New Roman"],
            "font.size": 6.9,
            "axes.titlesize": 6.9,
            "axes.labelsize": 6.8,
            "xtick.labelsize": 6.1,
            "ytick.labelsize": 6.1,
            "legend.fontsize": 6.0,
            "axes.linewidth": 0.60,
            "svg.hashsalt": "nostos-small-methods-v38",
        }
    )


def _copy_locked_main_figures() -> None:
    sources = {
        "figure_5_pshg_acquisition_shift": ROOT / "figures" / "nostos0_pshg_acquisition_shift" / "figure_pshg_acquisition_shift",
        "figure_6_tendon_pshg_transfer": ROOT / "figures" / "nostos0_tlt_pshg_xrd_transfer" / "figure_tlt_pshg_xrd_transfer",
    }
    for target_name, source_base in sources.items():
        for suffix in ("png", "pdf", "svg"):
            source = source_base.with_suffix(f".{suffix}")
            if not source.exists():
                raise FileNotFoundError(source)
            shutil.copy2(source, OUT / f"{target_name}.{suffix}")


def _write_v38_manifest() -> Path:
    inherited = OUT / "small_methods_figures_v37.manifest.json"
    payload = json.loads(inherited.read_text(encoding="utf-8"))
    payload["schema_version"] = "nostos-small-methods-figures/1.5"
    payload["generated_by"] = Path(__file__).relative_to(ROOT).as_posix()
    payload["generated_by_sha256"] = sha256(Path(__file__))
    payload["declaration"] = (
        "Every microscopy pixel originates in a cited public archive and every map, plot and numerical label is "
        "deterministic. BioRender session 4b54db0e-388a-4876-b95a-f5af00ac8d56 was used only as a data-free "
        "composition study and was rejected from the submitted artwork; no BioRender pixel is present."
    )
    payload["biorender_composition_study"] = {
        "session_id": "4b54db0e-388a-4876-b95a-f5af00ac8d56",
        "figure_id": "0ee293978041590fabce00da",
        "editor_url": "https://app.biorender.com/illustrations/0ee293978041590fabce00da?slideId=b9c6d13f-eadc-0255-aa64-c26e73e6228f",
        "used_in_submitted_artwork": False,
        "reason": "generic illustrative appearance; the final rail was rebuilt deterministically from authentic FMD evidence",
    }
    payload["copied_locked_outputs"] = {}
    for stem in ("figure_5_pshg_acquisition_shift", "figure_6_tendon_pshg_transfer"):
        payload["copied_locked_outputs"][stem] = {}
        for suffix in ("png", "pdf", "svg"):
            path = OUT / f"{stem}.{suffix}"
            payload["copied_locked_outputs"][stem][suffix] = {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    payload.pop("content_sha256", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    output = OUT / "small_methods_figures_v38.manifest.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> None:
    _patch_v37()
    v37.main()
    _copy_locked_main_figures()
    manifest = _write_v38_manifest()
    print(json.dumps({"status": "complete", "output": str(OUT), "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
