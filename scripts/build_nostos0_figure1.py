"""Build Figure 1 entirely from public source data and NOSTOS computations.

No generative imagery or manually drawn scientific output is used. The script
writes an editable SVG, a print-resolution PNG and a hash-locked panel manifest.
"""
from __future__ import annotations

import argparse
import os
import hashlib
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import tifffile
from matplotlib.colors import Normalize
from scipy import ndimage

from nostos.features.response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    maximal_sphere_local_thickness,
    structure_tensor_response,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def robust01(array: np.ndarray) -> np.ndarray:
    data = np.asarray(array, dtype=float)
    lo, hi = np.percentile(data[np.isfinite(data)], (1, 99.5))
    return np.clip((data - lo) / max(hi - lo, np.finfo(float).eps), 0, 1)


def central_crop(image: np.ndarray, height: int, width: int) -> np.ndarray:
    y0 = max(0, (image.shape[0] - height) // 2)
    x0 = max(0, (image.shape[1] - width) // 2)
    return image[y0 : y0 + height, x0 : x0 + width]


def local_orientation(image: np.ndarray, sigma: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    gy, gx = np.gradient(np.asarray(image, dtype=float))
    jxx = ndimage.gaussian_filter(gx * gx, sigma)
    jyy = ndimage.gaussian_filter(gy * gy, sigma)
    jxy = ndimage.gaussian_filter(gx * gy, sigma)
    angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy**2) / np.maximum(jxx + jyy, np.finfo(float).eps)
    return np.mod(angle, np.pi), coherence


def panel_label(ax: mpl.axes.Axes, label: str) -> None:
    ax.text(-0.05, 1.04, label, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def clean(ax: mpl.axes.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=7, width=0.6, length=3)


def build(data_root: Path) -> dict[str, object]:
    histology_path = data_root / "human-knee-cartilage-histopathology/raw/files/P031/Medial/SafO/SafO 58 section 2.tif"
    pshg_dir = data_root / "PSHG-TISS/breast-unstained-fshg/breast_9"
    pshg_paths = [pshg_dir / f"breast_9_FSHG_p{angle}.tif" for angle in range(0, 181, 20)]
    bone_path = data_root / "trabecular-bone-zenodo-11061947/BMLPL_001_REF_17_SEG_SUB.nii"
    perturbation_path = ROOT / "outputs/nostos0-module-perturbations-v1/module_perturbation_matrix.json"
    required = [histology_path, bone_path, perturbation_path, *pshg_paths]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required Figure 1 sources:\n" + "\n".join(missing))

    histology_raw = tifffile.imread(histology_path)
    if histology_raw.ndim > 3:
        histology_raw = histology_raw[0]
    if histology_raw.ndim == 2:
        histology_raw = np.repeat(histology_raw[..., None], 3, axis=2)
    histology = central_crop(histology_raw, min(1800, histology_raw.shape[0]), min(2800, histology_raw.shape[1]))
    histology = histology[::4, ::4, :3]

    pshg_stack = np.stack([np.asarray(tifffile.imread(path), dtype=float) for path in pshg_paths])
    pshg = robust01(np.mean(pshg_stack, axis=0))
    pshg = central_crop(pshg, min(512, pshg.shape[0]), min(512, pshg.shape[1]))
    pshg_small = ndimage.zoom(pshg, (256 / pshg.shape[0], 256 / pshg.shape[1]), order=1)

    bone_img = nib.load(str(bone_path))
    bone = np.asarray(bone_img.dataobj) > 0
    spacing_mm = tuple(float(v) for v in bone_img.header.get_zooms()[:3])
    bone_slice_index = bone.shape[2] // 2
    slab_half_width = 6
    slab = slice(bone_slice_index - slab_half_width, bone_slice_index + slab_half_width)
    bone_slice = np.mean(bone[:, :, slab], axis=2)

    scales = (2.0, 4.0, 8.0, 16.0)
    tensor = structure_tensor_response(pshg_small, spacing_um=(1.0, 1.0), scales_um=scales)
    hessian = hessian_morphology_response(pshg_small, spacing_um=(1.0, 1.0), scales_um=scales)
    variogram = directional_variogram(pshg_small, spacing_um=(1.0, 1.0), separations_um=(2, 4, 8, 16, 32, 48))
    thresholds_mm = (0.0, 0.02, 0.04, 0.08, 0.12)
    survival = erosion_survival_response(bone, spacing_um=spacing_mm, thresholds_um=thresholds_mm, boundary_corrected=True)
    thickness = maximal_sphere_local_thickness(bone, spacing_um=spacing_mm)
    thickness_slice = np.max(thickness[:, :, slab], axis=2)

    with perturbation_path.open(encoding="utf-8") as handle:
        perturbation = json.load(handle)
    modules = ["tensor", "hessian", "geometry", "network", "spatial"]
    kinds = ["rotation", "resampling", "blur", "noise", "contrast", "mask_error"]
    matrix = np.full((len(modules), len(kinds)), np.nan)
    for result in perturbation["results"]:
        module = result["module"]
        kind = result["perturbation"]["kind"]
        if module in modules and kind in kinds:
            value = 1.0 if result["passed"] else 0.0
            i, j = modules.index(module), kinds.index(kind)
            matrix[i, j] = value if np.isnan(matrix[i, j]) else min(matrix[i, j], value)

    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 8,
        "axes.linewidth": 0.7,
        "svg.fonttype": "none",
    })
    fig = plt.figure(figsize=(11.8, 6.2), constrained_layout=False)
    outer = fig.add_gridspec(2, 2, left=0.045, right=0.985, bottom=0.08, top=0.95, wspace=0.18, hspace=0.30)

    # a | Traceable public inputs.
    grid_a = outer[0, 0].subgridspec(1, 3, wspace=0.06)
    axes_a = [fig.add_subplot(grid_a[0, i]) for i in range(3)]
    axes_a[0].imshow(histology)
    axes_a[1].imshow(pshg, cmap="gray", vmin=0, vmax=1)
    axes_a[2].imshow(bone_slice, cmap="gray_r", vmin=0, vmax=1)
    for ax, title in zip(axes_a, ("cartilage histology", "polarization SHG", "trabecular micro-CT"), strict=True):
        ax.set_title(title, fontsize=8, pad=4)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_linewidth(0.5); spine.set_color("0.65")
    panel_label(axes_a[0], "a")

    # b | Scale-indexed response curves computed from those inputs.
    grid_b = outer[0, 1].subgridspec(1, 3, wspace=0.35)
    ax_b1, ax_b2, ax_b3 = [fig.add_subplot(grid_b[0, i]) for i in range(3)]
    ax_b1.plot(scales, tensor.coherency, "o-", color="#176D7A", lw=1.5, ms=3)
    ax_b1.set(xlabel="scale (pixels)", ylabel="tensor coherence", ylim=(0, 1))
    clean(ax_b1); panel_label(ax_b1, "b")
    denom = max(max(hessian.blob), max(hessian.tube), np.finfo(float).eps)
    ax_b2.plot(scales, np.asarray(hessian.blob) / denom, "o-", label="blob", color="#C94C4C", lw=1.3, ms=3)
    ax_b2.plot(scales, np.asarray(hessian.tube) / denom, "o-", label="tube", color="#335C99", lw=1.3, ms=3)
    ax_b2.set(xlabel="scale (pixels)", ylabel="normalized response", ylim=(0, 1.05))
    ax_b2.legend(frameon=False, fontsize=6, handlelength=1.4)
    clean(ax_b2)
    ax_b3.plot(np.asarray(thresholds_mm) * 1000, survival.surviving_fraction, "o-", color="#D28A22", lw=1.5, ms=3)
    ax_b3.set(xlabel="erosion (µm)", ylabel="surviving fraction", ylim=(0, 1.05))
    clean(ax_b3)

    # c | Prespecified perturbation coverage from the frozen receipt.
    ax_c = fig.add_subplot(outer[1, 0])
    cmap = mpl.colors.ListedColormap(["#C84A4A", "#238B57"])
    masked = np.ma.masked_invalid(matrix)
    ax_c.imshow(masked, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax_c.set_xticks(range(len(kinds)), [k.replace("_", " ") for k in kinds], rotation=35, ha="right", fontsize=7)
    ax_c.set_yticks(range(len(modules)), modules, fontsize=7)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if np.isnan(matrix[i, j]):
                ax_c.add_patch(mpl.patches.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor="#EEEEEA", edgecolor="white", lw=1))
            else:
                symbol = mpl.patches.Circle((j, i), radius=0.09, facecolor="white" if matrix[i, j] else "none", edgecolor="white", lw=1.0)
                ax_c.add_patch(symbol)
    ax_c.set_title("frozen module × perturbation tests", fontsize=9, pad=7)
    ax_c.tick_params(length=0)
    for spine in ax_c.spines.values(): spine.set_visible(False)
    panel_label(ax_c, "c")

    # d | Spatially resolved outputs computed from the displayed SHG and bone inputs.
    grid_d = outer[1, 1].subgridspec(1, 2, wspace=0.16)
    ax_d1, ax_d2 = [fig.add_subplot(grid_d[0, i]) for i in range(2)]
    angle, coherence = local_orientation(pshg_small)
    ax_d1.imshow(pshg_small, cmap="gray", vmin=0, vmax=1)
    step = 12
    yy, xx = np.mgrid[step // 2 : pshg_small.shape[0] : step, step // 2 : pshg_small.shape[1] : step]
    aa = angle[yy, xx]; cc = coherence[yy, xx]
    keep = cc >= np.quantile(cc, 0.45)
    length = 5.0
    for x, y, a in zip(xx[keep], yy[keep], aa[keep], strict=True):
        ax_d1.plot([x - length * np.cos(a), x + length * np.cos(a)], [y - length * np.sin(a), y + length * np.sin(a)], color="#00A6A6", lw=0.65, alpha=0.85)
    ax_d1.set_title("local direction", fontsize=8, pad=4)
    ax_d1.set_xticks([]); ax_d1.set_yticks([])
    panel_label(ax_d1, "d")
    shown = np.ma.masked_where(bone_slice <= 0, thickness_slice)
    ax_d2.imshow(bone_slice, cmap="gray_r", vmin=0, vmax=1)
    im = ax_d2.imshow(shown, cmap="magma", norm=Normalize(vmin=float(thickness[bone].min()), vmax=float(np.percentile(thickness[bone], 99))))
    ax_d2.set_title("local thickness", fontsize=8, pad=4)
    ax_d2.set_xticks([]); ax_d2.set_yticks([])
    cbar = fig.colorbar(im, ax=ax_d2, fraction=0.046, pad=0.03)
    cbar.set_label("mm", fontsize=7); cbar.ax.tick_params(labelsize=6, length=2)

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "figure_1_response_geometry_reference.png"
    svg = OUT / "figure_1_response_geometry_reference.svg"
    fig.savefig(png, dpi=400, facecolor="white")
    fig.savefig(svg, facecolor="white")
    plt.close(fig)

    sources = [histology_path, bone_path, perturbation_path, *pshg_paths]
    manifest = {
        "protocol_version": "nostos0-figure1/2.0",
        "status": "generated_from_traceable_sources",
        "generative_imagery": False,
        "generator": "scripts/build_nostos0_figure1.py",
        "command": "python scripts/build_nostos0_figure1.py --data-root <DATA_ROOT>",
        "panels": {
            "a": "Public cartilage histology, polarization-SHG and trabecular-bone inputs.",
            "b": "NOSTOS tensor, Hessian and erosion-survival responses computed from panel-a inputs.",
            "c": "Frozen module-by-perturbation outcomes read from the versioned validation receipt.",
            "d": "Spatial local-direction and local-thickness fields computed from panel-a inputs.",
        },
        "sources": [
            {"logical_path": str(path.relative_to(data_root)).replace("\\", "/") if path.is_relative_to(data_root) else str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for path in sources
        ],
        "outputs": {
            "png": {"path": str(png.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(png)},
            "svg": {"path": str(svg.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(svg)},
        },
        "notes": [
            "PSHG panel uses the arithmetic mean of ten raw polarization-angle frames from breast_9.",
            "Cartilage panel is a central crop downsampled fourfold for display only.",
            "No displayed microscopy or spatial measurement was generated by an image model.",
        ],
    }
    manifest_path = OUT / "figure_1_response_geometry_reference.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()
    data_root = args.data_root or (Path(os.environ["NOSTOS_DATA_ROOT"]) if "NOSTOS_DATA_ROOT" in os.environ else None)
    if data_root is None:
        parser.error("provide --data-root or set NOSTOS_DATA_ROOT")
    print(json.dumps(build(data_root.resolve()), indent=2))
