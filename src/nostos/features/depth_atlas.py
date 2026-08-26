from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from PIL import Image

from nostos.app.batch_cpu import select_records
from nostos.features.baselines import structure_tensor_features
from nostos.features.depth import cartilage_depth_coordinate
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.segmentation.weak_labels import propose_semantic_mask


METHOD_VERSION = "nostos-depth-atlas-1.0.0"


@dataclass(frozen=True)
class AtlasConfig:
    tile_size_um: float = 440.0
    stride_fraction: float = 0.5
    minimum_cartilage_fraction: float = 0.72
    boundary_exclusion_um: float = 50.0
    depth_edges: tuple[float, ...] = (0.0, 0.10, 0.30, 0.70, 1.0)
    minimum_tiles_per_band: int = 3
    angular_bins: int = 36
    low_frequency_fraction: float = 0.02
    high_frequency_fraction: float = 0.90

    @classmethod
    def from_json(cls, path: Path) -> "AtlasConfig":
        values = json.loads(path.read_text(encoding="utf-8"))
        if "depth_edges" in values:
            values["depth_edges"] = tuple(float(value) for value in values["depth_edges"])
        config = cls(**values)
        config.validate()
        return config

    def validate(self) -> None:
        if self.tile_size_um <= 0 or not 0 < self.stride_fraction <= 1:
            raise ValueError("tile size and stride fraction must be positive")
        if not 0 < self.minimum_cartilage_fraction <= 1:
            raise ValueError("minimum_cartilage_fraction must lie in (0, 1]")
        if self.boundary_exclusion_um < 0 or self.minimum_tiles_per_band < 1:
            raise ValueError("boundary exclusion and minimum tile count are invalid")
        if len(self.depth_edges) < 3 or self.depth_edges[0] != 0 or self.depth_edges[-1] != 1:
            raise ValueError("depth_edges must span 0 to 1")
        if any(right <= left for left, right in zip(self.depth_edges, self.depth_edges[1:])):
            raise ValueError("depth_edges must be strictly increasing")


def axial_difference_degrees(first: float, second: float) -> float:
    """Smallest unsigned difference between two axial orientations."""
    difference = abs(float(first) - float(second)) % 180.0
    return float(min(difference, 180.0 - difference))


def local_tangent_degrees(depth: np.ndarray, y: int, x: int, radius: int) -> float:
    """Estimate the local surface tangent from the normalized-depth gradient."""
    y0, y1 = max(0, y - radius), min(depth.shape[0], y + radius + 1)
    x0, x1 = max(0, x - radius), min(depth.shape[1], x + radius + 1)
    patch = np.asarray(depth[y0:y1, x0:x1], dtype=float)
    valid = np.isfinite(patch)
    if valid.sum() < 16:
        return float("nan")
    filled = patch.copy()
    filled[~valid] = float(np.nanmedian(patch))
    gradient_y, gradient_x = np.gradient(filled)
    normal_x = float(np.median(gradient_x[valid]))
    normal_y = float(np.median(gradient_y[valid]))
    if np.hypot(normal_x, normal_y) <= np.finfo(float).eps:
        return float("nan")
    return float(np.mod(np.degrees(np.arctan2(normal_y, normal_x)) + 90.0, 180.0))


def extract_depth_atlas(
    image: np.ndarray,
    labels: np.ndarray,
    *,
    pixel_size_um: float,
    config: AtlasConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Extract depth-stratified spectral and orientation measurements.

    The depth coordinate is the relative distance between independently detected
    articular-surface and deep cartilage boundaries. Tile orientation is expressed
    both in image coordinates and relative to the local depth-isoline tangent.
    """
    config.validate()
    image = np.asarray(image)
    labels = np.asarray(labels)
    if image.shape[:2] != labels.shape:
        raise ValueError("image and label dimensions differ")
    coordinate = cartilage_depth_coordinate(
        labels,
        pixel_size_um=pixel_size_um,
        boundary_exclusion_um=config.boundary_exclusion_um,
    )
    tile_size = max(32, int(round(config.tile_size_um / pixel_size_um)))
    tile_size = min(tile_size, image.shape[0], image.shape[1])
    tile_size -= tile_size % 2
    stride = max(1, int(round(tile_size * config.stride_fraction)))
    cartilage = labels == 1
    rows: list[dict[str, float | int | str]] = []
    for y in range(0, max(1, image.shape[0] - tile_size + 1), stride):
        for x in range(0, max(1, image.shape[1] - tile_size + 1), stride):
            region = cartilage[y:y + tile_size, x:x + tile_size]
            eligible = coordinate.eligible_cartilage[y:y + tile_size, x:x + tile_size]
            if float(region.mean()) < config.minimum_cartilage_fraction or not eligible.any():
                continue
            tile_depth = coordinate.normalized_depth[y:y + tile_size, x:x + tile_size]
            representative_depth = float(np.nanmedian(tile_depth[eligible]))
            center_y, center_x = y + tile_size // 2, x + tile_size // 2
            tangent = local_tangent_degrees(coordinate.normalized_depth, center_y, center_x, tile_size // 2)
            try:
                fft = extract_spatial_fft(
                    image[y:y + tile_size, x:x + tile_size],
                    pixel_size_um=pixel_size_um,
                    angular_bins=config.angular_bins,
                    low_frequency_fraction=config.low_frequency_fraction,
                    high_frequency_fraction=config.high_frequency_fraction,
                )
                tensor = structure_tensor_features(image[y:y + tile_size, x:x + tile_size])
            except ValueError:
                continue
            rows.append({
                "x_px": x,
                "y_px": y,
                "x_mm": x * pixel_size_um / 1000.0,
                "y_mm": y * pixel_size_um / 1000.0,
                "normalized_depth": representative_depth,
                "cartilage_fraction": float(region.mean()),
                "eligible_fraction": float(eligible.mean()),
                "local_tangent_degrees": tangent,
                **asdict(fft),
                "fft_tangent_deviation_degrees": axial_difference_degrees(fft.orientation_degrees, tangent) if np.isfinite(tangent) else float("nan"),
                "tensor_orientation_degrees": tensor.orientation_degrees,
                "tensor_coherence": tensor.coherence,
                "tensor_gradient_energy": tensor.gradient_energy,
                "tensor_tangent_deviation_degrees": axial_difference_degrees(tensor.orientation_degrees, tangent) if np.isfinite(tangent) else float("nan"),
                "fft_tensor_disagreement_degrees": axial_difference_degrees(fft.orientation_degrees, tensor.orientation_degrees),
            })
    tiles = pd.DataFrame(rows)
    if tiles.empty:
        raise ValueError("no depth-atlas tiles passed quality control")
    metrics = [
        "angular_entropy", "anisotropy", "spectral_slope",
        "characteristic_frequency_cycles_per_mm", "fft_tangent_deviation_degrees",
        "tensor_coherence", "tensor_tangent_deviation_degrees",
        "fft_tensor_disagreement_degrees",
    ]
    bands: list[dict[str, float | int | str | bool]] = []
    for index, (lower, upper) in enumerate(zip(config.depth_edges, config.depth_edges[1:])):
        selected = (tiles.normalized_depth >= lower) & (
            tiles.normalized_depth <= upper if upper == 1 else tiles.normalized_depth < upper
        )
        subset = tiles[selected]
        row: dict[str, float | int | str | bool] = {
            "band_index": index,
            "depth_lower": lower,
            "depth_upper": upper,
            "tile_count": len(subset),
            "band_qc_pass": len(subset) >= config.minimum_tiles_per_band,
        }
        for metric in metrics:
            values = subset[metric].to_numpy(dtype=float) if len(subset) else np.asarray([])
            values = values[np.isfinite(values)]
            row[f"{metric}_median"] = float(np.median(values)) if values.size else float("nan")
            row[f"{metric}_iqr"] = float(np.quantile(values, .75) - np.quantile(values, .25)) if values.size else float("nan")
        bands.append(row)
    profile = pd.DataFrame(bands)
    qc = {
        "method_version": METHOD_VERSION,
        "tile_size_pixels": tile_size,
        "stride_pixels": stride,
        "tile_count": len(tiles),
        "bands_passing": int(profile.band_qc_pass.sum()),
        "bands_total": len(profile),
        "section_qc_pass": bool(profile.band_qc_pass.all()),
        "median_fft_tensor_disagreement_degrees": float(tiles.fft_tensor_disagreement_degrees.median()),
        "surface_boundary_pixels": int(coordinate.surface_boundary.sum()),
        "deep_boundary_pixels": int(coordinate.deep_boundary.sum()),
    }
    return tiles, profile, qc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a depth-normalized NOSTOS osteochondral atlas")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stain", choices=["HE", "SafO", "PLM"], default="SafO")
    parser.add_argument("--site", choices=["Medial", "Lateral"], default="Medial")
    parser.add_argument("--section-rank", type=int, default=1)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    config = AtlasConfig.from_json(args.config)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = select_records(manifest, args.stain, args.site, args.section_rank)
    if args.limit:
        records = records[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    section_rows: list[dict[str, object]] = []
    for record in records:
        image_path = Path(record["absolute_path"])
        identifier = f"P{record['participant_id']}_{record['site']}_{record['modality']}_r{args.section_rank}"
        try:
            with Image.open(image_path) as opened:
                image = np.asarray(opened.convert("RGB"))
            labels = propose_semantic_mask(image, str(record["modality"]))
            tiles, profile, qc = extract_depth_atlas(
                image, labels, pixel_size_um=float(record["pixel_size_um_x"]), config=config
            )
            tiles.insert(0, "section_id", identifier)
            profile.insert(0, "section_id", identifier)
            tiles.to_csv(args.output / f"{identifier}_tiles.csv", index=False)
            profile.to_csv(args.output / f"{identifier}_profile.csv", index=False)
            section_rows.append({"section_id": identifier, "participant_id": record["participant_id"], "site": record["site"], "stain": record["modality"], "relative_path": record["relative_path"], "success": True, **qc})
        except Exception as error:
            section_rows.append({"section_id": identifier, "participant_id": record["participant_id"], "site": record["site"], "stain": record["modality"], "relative_path": record["relative_path"], "success": False, "error": f"{type(error).__name__}: {error}"})
    sections = pd.DataFrame(section_rows)
    sections.to_csv(args.output / "sections.csv", index=False)
    receipt = {
        "method_version": METHOD_VERSION,
        "command": " ".join(sys.argv),
        "configuration": asdict(config),
        "manifest_sha256": _sha256(args.manifest),
        "config_sha256": _sha256(args.config),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "sections_requested": len(records),
        "sections_succeeded": int(sections.success.fillna(False).sum()),
        "segmentation_supervision": "unreviewed stain-aware proposal; research analysis only",
        "output": str(args.output.resolve()),
    }
    (args.output / "run_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
