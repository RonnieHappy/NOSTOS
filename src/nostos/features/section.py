from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from nostos.segmentation.annotations import AnnotationRecord, read_annotation_manifest, validate_annotation_manifest

from .baselines import as_grayscale_float
from .depth import cartilage_depth_coordinate
from .spatial_fft import extract_spatial_fft
from .zsd import extract_zsd_tiles, summarize_zsd_tiles


def _global_fft_preview(image: np.ndarray, pixel_size_um: float, maximum_side: int = 2048) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    scale = min(1.0, maximum_side / max(height, width))
    if scale == 1.0:
        return image, pixel_size_um
    preview = Image.fromarray(np.asarray(image).astype(np.uint8)).resize(
        (max(32, round(width * scale)), max(32, round(height * scale))), Image.Resampling.BOX
    )
    return np.asarray(preview), pixel_size_um / scale


def extract_section_features(
    record: AnnotationRecord,
    *,
    pixel_size_um: float,
    tile_size: int = 512,
    overlap_fraction: float = 0.5,
    minimum_cartilage_fraction: float = 0.8,
    boundary_exclusion_um: float = 100.0,
) -> dict[str, float | str | bool]:
    with Image.open(record.image_path) as opened:
        image = np.asarray(opened.convert("RGB"))
    with Image.open(record.mask_path) as opened:
        labels = np.asarray(opened.convert("L"))
    if image.shape[:2] != labels.shape:
        raise ValueError("image and reviewed mask dimensions differ")
    tiles = extract_zsd_tiles(
        image,
        labels,
        pixel_size_um=pixel_size_um,
        tile_size=tile_size,
        overlap_fraction=overlap_fraction,
        minimum_cartilage_fraction=minimum_cartilage_fraction,
        boundary_exclusion_um=boundary_exclusion_um,
    )
    if not tiles:
        raise ValueError("no eligible cartilage tiles")
    row: dict[str, float | str | bool] = {
        "participant_id": record.participant_id,
        "specimen_id": record.specimen_id,
        "site": record.site,
        "stain": record.stain,
        "split": record.split,
        "image_path": str(record.image_path),
        "mask_path": str(record.mask_path),
        "pixel_size_um": pixel_size_um,
        "feature_success": True,
    }
    row.update({f"zsd_{name}": value for name, value in summarize_zsd_tiles(tiles).items()})
    for prefix in ("tensor_", "glcm_"):
        names = sorted(name for name in tiles[0] if name.startswith(prefix))
        for name in names:
            row[f"texture_{name}_mean"] = float(np.mean([float(tile[name]) for tile in tiles]))
    cartilage = labels == 1
    grayscale = as_grayscale_float(image)
    coordinate = cartilage_depth_coordinate(
        labels, pixel_size_um=pixel_size_um, boundary_exclusion_um=boundary_exclusion_um
    )
    surface_length_um = float(coordinate.surface_boundary.sum() * pixel_size_um)
    area_um2 = float(cartilage.sum() * pixel_size_um**2)
    row["intensity_cartilage_mean"] = float(np.mean(grayscale[cartilage]))
    row["morphology_cartilage_area_mm2"] = area_um2 / 1_000_000.0
    row["morphology_mean_thickness_um"] = area_um2 / surface_length_um if surface_length_um else float("nan")
    preview, preview_pixel_size = _global_fft_preview(image, pixel_size_um)
    global_fft = extract_spatial_fft(preview, pixel_size_um=preview_pixel_size)
    row.update({f"global_fft_{name}": value for name, value in asdict(global_fft).items()})
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract frozen section-level NOSTOS features.")
    parser.add_argument("annotation_manifest", type=Path)
    parser.add_argument("--pixel-sizes", type=Path, required=True, help="JSON stain-to-micrometers/pixel map")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=512)
    args = parser.parse_args()
    records = read_annotation_manifest(args.annotation_manifest)
    errors = validate_annotation_manifest(records)
    if errors:
        raise ValueError("Invalid annotation manifest:\n" + "\n".join(errors))
    scales = json.loads(args.pixel_sizes.read_text(encoding="utf-8"))
    rows = []
    for record in records:
        try:
            rows.append(extract_section_features(record, pixel_size_um=float(scales[record.stain]), tile_size=args.tile_size))
        except (ValueError, OSError, FloatingPointError) as error:
            rows.append({"participant_id": record.participant_id, "specimen_id": record.specimen_id, "site": record.site, "stain": record.stain, "split": record.split, "image_path": str(record.image_path), "mask_path": str(record.mask_path), "feature_success": False, "feature_error": f"{type(error).__name__}: {error}"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(json.dumps({"sections": len(rows), "successes": sum(bool(row["feature_success"]) for row in rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
