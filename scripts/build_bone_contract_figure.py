"""Build the evidence-linked NOSTOS-0 bone contract supplementary megafigure."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import tifffile
from matplotlib.colors import ListedColormap
from matplotlib.collections import LineCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image
from scipy.ndimage import gaussian_filter, label
from skimage.measure import marching_cubes


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "nostos0"
INK = "#20262E"
BLUE = "#0F4D92"
TEAL = "#168A8A"
AMBER = "#E2A72E"
RED = "#B64342"
PALE = "#E8EDF1"
MID = "#737B83"
VIOLET = "#7A3E8E"

mpl.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.size": 6.5,
        "axes.linewidth": 0.65,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "svg.hashsalt": "nostos-bone-contract-figure-v1",
        "pdf.fonttype": 42,
    }
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalise(array: np.ndarray, lower: float = 1, upper: float = 99.5) -> np.ndarray:
    values = np.asarray(array, dtype=np.float32)
    lo, hi = np.percentile(values, (lower, upper))
    return np.clip((values - lo) / max(float(hi - lo), np.finfo(np.float32).eps), 0, 1)


def _panel(ax, letter: str) -> None:
    text_method = ax.text2D if hasattr(ax, "text2D") else ax.text
    text_method(
        -0.055,
        1.015,
        letter,
        transform=ax.transAxes,
        fontsize=9.5,
        fontweight="bold",
        va="bottom",
        ha="left",
        clip_on=False,
        color=INK,
    )


def _image_axis(ax, title: str | None = None) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if title:
        ax.set_title(title, fontsize=6.7, pad=1.5, color=INK)


def _crop_center(volume: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    starts = tuple((current - target) // 2 for current, target in zip(volume.shape, shape))
    slices = tuple(slice(start, start + target) for start, target in zip(starts, shape))
    return np.asarray(volume[slices])


def _risk_curve(rows: list[dict], score: str) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(rows, key=lambda row: (row["scores"][score], row["case_id"]))
    coverage = np.arange(1, len(ordered) + 1) / len(ordered)
    risk = np.cumsum([bool(row["invalid"]) for row in ordered]) / np.arange(1, len(ordered) + 1)
    return coverage, risk


def _composite_orthoslices(cube: np.ndarray) -> np.ndarray:
    data = _normalise(cube)
    z, y, x = (value // 2 for value in data.shape)
    xy = data[z]
    xz = data[:, y]
    yz = data[:, :, x]
    minimum_projection = _normalise(np.min(cube, axis=0), 1, 99)
    vertical = np.ones((xy.shape[0], 3), dtype=float)
    horizontal = np.ones((3, xy.shape[1] * 2 + 3), dtype=float)
    top = np.concatenate((xy, vertical, xz), axis=1)
    bottom = np.concatenate((yz, vertical, minimum_projection), axis=1)
    return np.concatenate((top, horizontal, bottom), axis=0)


def _select_human_cube(raw_root: Path) -> tuple[Path, tuple[int, int, int], np.ndarray, dict]:
    """Select a display cube by a frozen dispersion criterion, not appearance."""

    candidates = []
    structure = np.ones((3, 3, 3), dtype=np.uint8)
    for path in sorted(raw_root.glob("*.raw")):
        volume = np.memmap(path, dtype="<u2", mode="r", shape=(1024, 1024, 1024))
        for center in ((z, y, x) for z in (384, 640) for y in (384, 640) for x in (384, 640)):
            slices = tuple(slice(value - 48, value + 48) for value in center)
            cube = np.asarray(volume[slices])
            low = cube < np.percentile(cube, 10)
            components, count = label(low, structure=structure)
            sizes = np.bincount(components.ravel())[1:] if count else np.asarray([], dtype=int)
            largest_fraction = float(sizes.max() / max(1, low.sum())) if sizes.size else 1.0
            candidates.append((largest_fraction, path.name, center, path, cube.copy()))
    largest_fraction, _, center, path, cube = min(candidates, key=lambda item: item[:3])
    criterion = {
        "name": "minimum_largest_component_fraction_within_lowest_intensity_decile",
        "candidate_cubes": len(candidates),
        "largest_component_fraction": largest_fraction,
        "center_zyx": list(center),
    }
    return path, center, cube, criterion


def _internal_low_density_mask(cube: np.ndarray) -> np.ndarray:
    low = np.asarray(cube < np.percentile(cube, 10))
    structure = np.ones((3, 3, 3), dtype=np.uint8)
    components, count = label(low, structure=structure)
    if not count:
        return low
    boundary = np.zeros(low.shape, dtype=bool)
    boundary[[0, -1], :, :] = True
    boundary[:, [0, -1], :] = True
    boundary[:, :, [0, -1]] = True
    boundary_labels = np.unique(components[boundary])
    sizes = np.bincount(components.ravel())
    keep = np.ones(count + 1, dtype=bool)
    keep[0] = False
    keep[boundary_labels] = False
    keep[sizes < 20] = False
    return keep[components]


def _archive_sha(integrity: dict, dataset: str, filename: str) -> str:
    for row in integrity["rows"]:
        if row["dataset"] == dataset and row["file"] == filename:
            return row["sha256"]
    raise KeyError(f"Missing integrity row for {dataset}/{filename}")


def _orientation_segments(image: np.ndarray, sigma: float = 4.0, step: int = 28):
    smooth = gaussian_filter(np.asarray(image, dtype=np.float32), sigma=sigma)
    gy, gx = np.gradient(smooth)
    jxx = gaussian_filter(gx * gx, sigma=sigma)
    jyy = gaussian_filter(gy * gy, sigma=sigma)
    jxy = gaussian_filter(gx * gy, sigma=sigma)
    angle = (0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2) % np.pi
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy**2) / np.maximum(
        jxx + jyy, np.finfo(np.float32).eps
    )
    threshold = np.percentile(coherence, 62)
    segments = []
    colours = []
    alphas = []
    half = step * 0.43
    for y in range(step // 2, image.shape[0], step):
        for x in range(step // 2, image.shape[1], step):
            if coherence[y, x] < threshold:
                continue
            dx = math.cos(float(angle[y, x])) * half
            dy = math.sin(float(angle[y, x])) * half
            segments.append(((x - dx, y - dy), (x + dx, y + dy)))
            colours.append(float(angle[y, x]))
            alphas.append(float(np.clip(0.35 + 0.65 * coherence[y, x], 0.35, 1)))
    rgba = mpl.colormaps["twilight"](np.asarray(colours) / np.pi)
    rgba[:, 3] = np.asarray(alphas)
    return segments, rgba


def build(data_root: Path) -> dict:
    integrity_path = ROOT / "outputs/nostos0-bone-download-integrity/integrity_verification.json"
    network_path = ROOT / "outputs/nostos0-bone-network-3d-v2/case_rows.json"
    nano_scale_path = ROOT / "outputs/nostos0-human-nanoct-scale-response-v2/case_rows.json"
    nano_summary_path = ROOT / (
        "outputs/nostos0-human-nanoct-scale-response-v2/human_nanoct_scale_response.json"
    )
    uv_rows_path = ROOT / "outputs/nostos0-uvpam-abstention/case_rows.json"
    program_path = ROOT / "outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json"
    integrity = _load_json(integrity_path)
    network_rows = _load_json(network_path)
    nano_rows = _load_json(nano_scale_path)
    nano_summary = _load_json(nano_summary_path)
    uv_rows = _load_json(uv_rows_path)

    shg_relative = Path(
        "Mouse27_wt/LTibiaUpperPart/180719_10-28-10/image_0044.png"
    )
    shg_image_path = data_root / "zenodo-3355937/extracted/images/shg-ce-de" / shg_relative
    shg_mask_path = data_root / "zenodo-3355937/extracted/masks/shg-masks" / shg_relative
    shg_rgb = np.asarray(Image.open(shg_image_path).convert("RGB"))
    shg = _normalise(np.mean(shg_rgb, axis=2))
    mask_rgb = np.asarray(Image.open(shg_mask_path).convert("RGB"))
    overlay = np.zeros((*mask_rgb.shape[:2], 4), dtype=float)
    label_rules = [
        ((mask_rgb[..., 1] > 150) & (mask_rgb[..., 0] < 100), TEAL),
        ((mask_rgb[..., 0] > 150) & (mask_rgb[..., 1] < 100), RED),
        ((mask_rgb[..., 2] > 150) & (mask_rgb[..., 0] < 100), BLUE),
    ]
    for region, colour in label_rules:
        overlay[region, :3] = mpl.colors.to_rgb(colour)
        overlay[region, 3] = 0.60

    rat_root = data_root / "zenodo-11061868/files"
    rat_image_path = rat_root / "CT13-endosteum_img.tif"
    rat_seg_path = rat_root / "CT13-endosteum_seg.tif"
    rat_image = _crop_center(tifffile.memmap(rat_image_path), (96, 384, 384))
    rat_seg = _crop_center(tifffile.memmap(rat_seg_path), (96, 384, 384))
    rat_mip = _normalise(np.max(rat_image, axis=0), 2, 99.7)
    rat_slice = _normalise(rat_image[rat_image.shape[0] // 2], 2, 99.7)
    segmentation_slice = rat_seg[rat_seg.shape[0] // 2]

    human_raw_root = data_root / "zenodo-17909733/extracted/raw"
    human_raw_path, human_center, human_cube, human_selection = _select_human_cube(human_raw_root)
    human_display = _composite_orthoslices(human_cube)

    uv_archive_path = data_root / "zenodo-6345772/files/cycleGAN-UVPAM.zip"
    uv_row = uv_rows[len(uv_rows) // 2]
    with zipfile.ZipFile(uv_archive_path) as archive:
        uv_image = np.asarray(Image.open(io.BytesIO(archive.read(uv_row["file"]))).convert("L"))
    uv_display = _normalise(uv_image)
    uv_fft = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(uv_display - uv_display.mean()))))
    uv_fft = _normalise(uv_fft, 2, 99.8)

    fig = plt.figure(figsize=(7.25, 7.05), facecolor="white")
    grid = fig.add_gridspec(
        3,
        4,
        left=0.035,
        right=0.985,
        bottom=0.035,
        top=0.985,
        wspace=0.20,
        hspace=0.20,
        height_ratios=(1, 1.05, 1),
    )

    ax = fig.add_subplot(grid[0, 0])
    ax.imshow(shg, cmap="gray", vmin=0, vmax=1)
    _image_axis(ax, "mouse SHG")
    _panel(ax, "a")

    ax = fig.add_subplot(grid[0, 1])
    ax.imshow(shg, cmap="gray", vmin=0, vmax=1)
    ax.imshow(overlay)
    _image_axis(ax, "coarse compatibility")
    _panel(ax, "b")

    ax = fig.add_subplot(grid[0, 2])
    ax.imshow(rat_mip, cmap="gray", vmin=0, vmax=1)
    _image_axis(ax, "rat confocal MIP")
    _panel(ax, "c")

    ax = fig.add_subplot(grid[0, 3])
    ax.imshow(rat_slice, cmap="gray", vmin=0, vmax=1, alpha=0.64)
    classes = np.ma.masked_where(segmentation_slice == 0, segmentation_slice)
    ax.imshow(
        classes,
        cmap=ListedColormap([TEAL, AMBER, VIOLET]),
        vmin=1,
        vmax=3,
        interpolation="nearest",
        alpha=0.88,
    )
    _image_axis(ax, "imported 3D labels")
    _panel(ax, "d")

    ax = fig.add_subplot(grid[1, 0], projection="3d")
    terrain = rat_mip[::4, ::4]
    yy, xx = np.mgrid[0 : terrain.shape[0], 0 : terrain.shape[1]]
    surface = ax.plot_surface(
        xx,
        yy,
        terrain * 34,
        cmap="inferno",
        linewidth=0,
        antialiased=True,
        rcount=96,
        ccount=96,
    )
    surface.set_rasterized(True)
    ax.view_init(elev=38, azim=-59)
    ax.set_axis_off()
    ax.set_facecolor("#06070A")
    ax.set_title("intensity terrain", fontsize=6.7, pad=-2, color=INK)
    _panel(ax, "e")

    ax = fig.add_subplot(grid[1, 1])
    for score, colour, label, width in (
        ("endpoint_qc", MID, "endpoint QC", 1.0),
        ("topology_qc", TEAL, "topology", 1.15),
        ("full_contract", BLUE, "full", 1.65),
    ):
        coverage, risk = _risk_curve(network_rows, score)
        ax.plot(coverage, risk, color=colour, lw=width, label=label)
    ax.scatter([1, 0.538], [0.50, 0.25], color=[RED, BLUE], s=16, zorder=5, edgecolor="white", linewidth=0.4)
    ax.set(xlim=(0, 1.02), ylim=(-0.01, 0.66), xlabel="coverage", ylabel="silent-invalid risk")
    ax.set_xticks([0, 0.5, 1])
    ax.set_yticks([0, 0.25, 0.5])
    ax.legend(loc="upper left", fontsize=5.4, handlelength=1.3, borderaxespad=0.2)
    ax.axvline(0.8, color=PALE, lw=0.8, zorder=0)
    _panel(ax, "f")

    ax = fig.add_subplot(grid[1, 2])
    ax.imshow(human_display, cmap="bone", vmin=0, vmax=1)
    _image_axis(ax, "human nanoCT · 0.10 µm")
    _panel(ax, "g")

    ax = fig.add_subplot(grid[1, 3], projection="3d")
    internal_voids = _internal_low_density_mask(human_cube)
    vertices, faces, _, _ = marching_cubes(internal_voids.astype(np.float32), level=0.5, step_size=1)
    mesh = Poly3DCollection(vertices[faces], linewidth=0, alpha=0.82)
    mesh.set_array(vertices[faces].mean(axis=1)[:, 2])
    mesh.set_cmap("plasma")
    mesh.set_clim(float(vertices[:, 2].min()), float(vertices[:, 2].max()))
    mesh.set_edgecolor("none")
    mesh.set_rasterized(True)
    ax.add_collection3d(mesh)
    margins = np.maximum(np.ptp(vertices, axis=0) * 0.03, 1)
    ax.set_xlim(vertices[:, 0].min() - margins[0], vertices[:, 0].max() + margins[0])
    ax.set_ylim(vertices[:, 1].min() - margins[1], vertices[:, 1].max() + margins[1])
    ax.set_zlim(vertices[:, 2].min() - margins[2], vertices[:, 2].max() + margins[2])
    ax.view_init(elev=22, azim=38)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()
    ax.set_facecolor("white")
    ax.set_title("internal low-density isosurfaces", fontsize=6.7, pad=-2, color=INK)
    _panel(ax, "h")

    ax = fig.add_subplot(grid[2, 0])
    ax.imshow(shg, cmap="gray", vmin=0, vmax=1, alpha=0.78)
    segments, colours = _orientation_segments(shg)
    collection = LineCollection(segments, colors=colours, linewidths=0.72)
    ax.add_collection(collection)
    _image_axis(ax, "local orientation field")
    _panel(ax, "i")

    ax = fig.add_subplot(grid[2, 1])
    scales = [0.2, 0.4, 0.8]
    full_coverage = [nano_summary["summary_by_scale_um"][str(scale)]["full_contract"]["coverage"] for scale in scales]
    always_risk = [nano_summary["summary_by_scale_um"][str(scale)]["always_emit"]["silent_invalid_risk"] for scale in scales]
    full_risk = [nano_summary["summary_by_scale_um"][str(scale)]["full_contract"]["silent_invalid_risk"] for scale in scales]
    x = np.arange(len(scales))
    ax.bar(x, full_coverage, width=0.62, color=[PALE, "#A9D7CF", TEAL], edgecolor="white", linewidth=0.4)
    risk_ax = ax.twinx()
    risk_ax.plot(x, always_risk, "o--", color=RED, lw=1.0, ms=3)
    valid = np.isfinite(np.asarray([np.nan if value is None else value for value in full_risk], dtype=float))
    risk_ax.plot(x[valid], np.asarray(full_risk, dtype=object)[valid].astype(float), "o-", color=BLUE, lw=1.5, ms=3)
    ax.axhline(0.8, color=MID, lw=0.7, ls=":")
    ax.set_xticks(x, ["0.2", "0.4", "0.8"])
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0, 0.4, 0.8])
    risk_ax.set_ylim(0, 0.13)
    risk_ax.set_yticks([0, 0.05, 0.10])
    ax.set_xlabel("physical scale (µm)")
    ax.set_ylabel("coverage")
    risk_ax.set_ylabel("risk", color=RED, labelpad=1)
    risk_ax.tick_params(axis="y", colors=RED, labelsize=5.2, pad=1)
    risk_ax.spines["top"].set_visible(False)
    risk_ax.spines["right"].set_color(RED)
    _panel(ax, "j")

    ax = fig.add_subplot(grid[2, 2])
    ax.imshow(uv_display, cmap="gray", vmin=0, vmax=1)
    _image_axis(ax, "UV-PAM · no pixel calibration")
    _panel(ax, "k")

    ax = fig.add_subplot(grid[2, 3])
    ax.imshow(uv_fft, cmap="magma", vmin=0, vmax=1)
    _image_axis(ax, "pixel-domain spectrum")
    ax.text(0.05, 0.10, "px", transform=ax.transAxes, fontsize=9, color="white", fontweight="bold")
    ax.text(0.77, 0.10, "µm", transform=ax.transAxes, fontsize=9, color="white", fontweight="bold")
    ax.plot([0.75, 0.93], [0.08, 0.20], transform=ax.transAxes, color=RED, lw=2.0, solid_capstyle="round")
    _panel(ax, "l")

    OUT.mkdir(parents=True, exist_ok=True)
    stem = "supplementary_figure_1_bone_contract_stress"
    png_path = OUT / f"{stem}.png"
    svg_path = OUT / f"{stem}.svg"
    fig.savefig(
        png_path,
        dpi=600,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.035,
        metadata={"Software": "NOSTOS bone contract figure 1.0"},
    )
    fig.savefig(
        svg_path,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.035,
        metadata={"Creator": "NOSTOS bone contract figure 1.0", "Date": None},
    )
    plt.close(fig)

    manifest = {
        "protocol_version": "nostos-bone-contract-figure/1.0",
        "status": "complete",
        "figure": stem,
        "scientific_image_policy": "real public source data and frozen receipts only; no generative imagery",
        "selected_sources": {
            "mouse_shg_archive": {
                "doi": "10.5281/zenodo.3355937",
                "archive_sha256": _archive_sha(integrity, "zenodo-3355937", "shg-ce-de.zip"),
                "image_member": shg_relative.as_posix(),
                "mask_member": shg_relative.as_posix(),
            },
            "rat_confocal": {
                "doi": "10.5281/zenodo.11061868",
                "image": rat_image_path.name,
                "image_sha256": _archive_sha(integrity, "zenodo-11061868", rat_image_path.name),
                "segmentation": rat_seg_path.name,
                "segmentation_sha256": _archive_sha(integrity, "zenodo-11061868", rat_seg_path.name),
            },
            "human_nanoct": {
                "doi": "10.5281/zenodo.17909733",
                "archive_sha256": _archive_sha(integrity, "zenodo-17909733", "raw_data_bin2_uint16.zip"),
                "raw_member": human_raw_path.name,
                "public_spacing_um": [0.10, 0.10, 0.10],
                "display_selection": human_selection,
                "isosurface": "lowest intensity decile; boundary-connected and <20-voxel components excluded",
            },
            "uvpam": {
                "doi": "10.5281/zenodo.6345772",
                "archive_sha256": _archive_sha(integrity, "zenodo-6345772", "cycleGAN-UVPAM.zip"),
                "archive_member": uv_row["file"],
            },
        },
        "receipt_sha256": {
            path.relative_to(ROOT).as_posix(): _sha256(path)
            for path in (integrity_path, network_path, nano_scale_path, nano_summary_path, uv_rows_path, program_path)
        },
        "script_sha256": _sha256(Path(__file__)),
        "computed_visuals": {
            "panel_e": "rat confocal maximum-intensity projection rendered as a height field",
            "panel_h": "human nanoCT internal low-density isosurfaces under the declared display rule",
            "panel_i": "sigma-4-pixel local structure-tensor orientation segments on the selected SHG section",
            "panel_l": "log-magnitude 2D Fourier spectrum of the selected UV-PAM tile",
        },
        "outputs": {
            png_path.name: {"bytes": png_path.stat().st_size, "sha256": _sha256(png_path)},
            svg_path.name: {"bytes": svg_path.stat().st_size, "sha256": _sha256(svg_path)},
        },
        "claim_boundary": (
            "Visualises stress-test and abstention behavior. The figure does not validate automatic "
            "segmentation, bone biology, diagnosis, mechanics or clinical use."
        ),
    }
    manifest_path = OUT / f"{stem}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(r"<DATA_ROOT>\data\public\bone-contract-benchmark"),
    )
    args = parser.parse_args()
    print(json.dumps(build(args.data_root), indent=2))


if __name__ == "__main__":
    main()
