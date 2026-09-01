"""Cartilage boundary, void, purity, geometry and optical-density ablations."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes, binary_propagation, distance_transform_edt

from nostos.app.batch_cpu import select_records
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.segmentation.weak_labels import propose_semantic_mask


PROTOCOL = "nostos-cartilage-ablations/1.1"


def ablation_masks(semantic: np.ndarray, pixel_size_um: float, image: np.ndarray | None = None) -> dict[str, np.ndarray]:
    cartilage = semantic == 1
    if not cartilage.any():
        return {name: cartilage.copy() for name in (
            "baseline_072", "strict_095", "eroded_100um", "eroded_250um",
            "surface_excluded_100um", "surface_excluded_250um", "void_excluded_100um",
            "internal_hole_excluded_100um", "extreme_dark_object_excluded_25um",
        )}
    external_candidate = (semantic == 0) | (semantic == 5)
    seed = np.zeros_like(cartilage)
    seed[0, :] = external_candidate[0, :]
    seed[-1, :] = external_candidate[-1, :]
    seed[:, 0] |= external_candidate[:, 0]
    seed[:, -1] |= external_candidate[:, -1]
    external_background = binary_propagation(seed, mask=external_candidate)
    surface_boundary = cartilage & binary_dilation(external_background, iterations=1)
    distance_to_surface = distance_transform_edt(~surface_boundary, sampling=pixel_size_um) if surface_boundary.any() else np.full(cartilage.shape, np.inf)
    distance_inside = distance_transform_edt(cartilage, sampling=pixel_size_um)
    void = semantic == 4
    distance_to_void = distance_transform_edt(~void, sampling=pixel_size_um) if void.any() else np.full(cartilage.shape, np.inf)
    internal_holes = binary_fill_holes(cartilage) & ~cartilage
    distance_to_hole = distance_transform_edt(~internal_holes, sampling=pixel_size_um) if internal_holes.any() else np.full(cartilage.shape, np.inf)
    if image is not None:
        rgb = np.asarray(image, dtype=float)
        luminance = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255.0
        dark_threshold = float(np.quantile(luminance[cartilage], 0.01))
        extreme_dark = cartilage & (luminance <= dark_threshold)
        distance_to_dark = distance_transform_edt(~extreme_dark, sampling=pixel_size_um)
    else:
        distance_to_dark = np.full(cartilage.shape, np.inf)
    return {
        "baseline_072": cartilage,
        "strict_095": cartilage,
        "eroded_100um": cartilage & (distance_inside > 100.0),
        "eroded_250um": cartilage & (distance_inside > 250.0),
        "surface_excluded_100um": cartilage & (distance_to_surface > 100.0),
        "surface_excluded_250um": cartilage & (distance_to_surface > 250.0),
        "void_excluded_100um": cartilage & (distance_to_void > 100.0),
        "internal_hole_excluded_100um": cartilage & (distance_to_hole > 100.0),
        "extreme_dark_object_excluded_25um": cartilage & (distance_to_dark > 25.0),
    }


def _fft_tile_metrics(image: np.ndarray, eligible: np.ndarray, pixel_size_um: float, minimum_fraction: float) -> list[dict]:
    tile_size = min(256, image.shape[0], image.shape[1])
    tile_size -= tile_size % 2
    stride = max(32, tile_size // 2)
    rows = []
    for top in range(0, max(1, image.shape[0] - tile_size + 1), stride):
        for left in range(0, max(1, image.shape[1] - tile_size + 1), stride):
            region = eligible[top:top + tile_size, left:left + tile_size]
            if float(np.mean(region)) < minimum_fraction:
                continue
            tile = image[top:top + tile_size, left:left + tile_size]
            try:
                result = extract_spatial_fft(tile, pixel_size_um=pixel_size_um)
            except ValueError:
                continue
            rows.append({"angular_entropy": result.angular_entropy, "anisotropy": result.anisotropy,
                         "characteristic_frequency_cycles_per_mm": result.characteristic_frequency_cycles_per_mm})
    return rows


def _geometry_and_intensity(image: np.ndarray, semantic: np.ndarray, pixel_size_um: float) -> dict[str, float]:
    cartilage = semantic == 1
    if not cartilage.any():
        return {name: float("nan") for name in (
            "cartilage_area_mm2", "cartilage_perimeter_area_ratio_per_mm", "void_fraction_near_cartilage",
            "od_red_median", "od_green_median", "od_blue_median", "luminance_median", "luminance_iqr",
        )}
    area_mm2 = float(cartilage.sum() * pixel_size_um**2 / 1e6)
    perimeter = cartilage ^ binary_erosion(cartilage)
    perimeter_mm = float(perimeter.sum() * pixel_size_um / 1000)
    near_cartilage = binary_dilation(cartilage, iterations=max(1, int(round(100 / pixel_size_um))))
    void_fraction = float(np.mean(semantic[near_cartilage] == 4))
    rgb = image.astype(float)
    od = -np.log((rgb + 1.0) / 256.0)
    selected_od = od[cartilage]
    luminance = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255.0
    selected_luminance = luminance[cartilage]
    return {
        "cartilage_area_mm2": area_mm2,
        "cartilage_perimeter_area_ratio_per_mm": perimeter_mm / max(area_mm2, np.finfo(float).eps),
        "void_fraction_near_cartilage": void_fraction,
        "od_red_median": float(np.median(selected_od[:, 0])),
        "od_green_median": float(np.median(selected_od[:, 1])),
        "od_blue_median": float(np.median(selected_od[:, 2])),
        "luminance_median": float(np.median(selected_luminance)),
        "luminance_iqr": float(np.quantile(selected_luminance, .75) - np.quantile(selected_luminance, .25)),
    }


def analyze_ablation_record(record: dict) -> dict:
    try:
        path = Path(record["absolute_path"])
        with Image.open(path) as opened:
            image = np.asarray(opened.convert("RGB"))
        pixel_size = float(record["pixel_size_um_x"])
        semantic = propose_semantic_mask(image, str(record["modality"]))
        output: dict[str, object] = {
            "participant_id": record["participant_id"], "site": record["site"], "stain": record["modality"],
            "relative_path": record["relative_path"], "pixel_size_um": pixel_size, "success": True,
            **_geometry_and_intensity(image, semantic, pixel_size),
        }
        masks = ablation_masks(semantic, pixel_size, image)
        for variant, eligible in masks.items():
            threshold = 0.95 if variant == "strict_095" else 0.72
            tiles = _fft_tile_metrics(image, eligible, pixel_size, threshold)
            output[f"{variant}_tiles"] = len(tiles)
            output[f"{variant}_eligible_fraction"] = float(np.mean(eligible))
            for metric in ("angular_entropy", "anisotropy", "characteristic_frequency_cycles_per_mm"):
                values = np.asarray([tile[metric] for tile in tiles], dtype=float)
                output[f"{variant}_{metric}_median"] = float(np.median(values)) if values.size else np.nan
        return output
    except Exception as exc:
        return {"participant_id": record.get("participant_id"), "site": record.get("site"),
                "stain": record.get("modality"), "relative_path": record.get("relative_path"),
                "success": False, "error": f"{type(exc).__name__}: {exc}"}


def run_ablation_batch(manifest: dict, stain: str, site: str, output: Path, workers: int = 4) -> dict:
    records = select_records(manifest, stain, site, section_rank=1)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(analyze_ablation_record, record) for record in records]
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            rows.append(row)
            print(json.dumps({"completed": index, "total": len(records), "participant_id": row.get("participant_id"), "success": row.get("success")}), flush=True)
    frame = pd.DataFrame(rows).sort_values("participant_id")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    receipt = {"protocol_version": PROTOCOL, "stain": stain, "site": site, "sections": len(frame),
               "successes": int(frame["success"].fillna(False).sum()), "output": str(output),
               "validity": "exploratory_weak_semantic_proposals",
               "surface_definition": "class-1 boundary adjacent to border-connected class-0/5 external background",
               "proxy_definitions": {"internal_hole": "binary holes enclosed by the class-1 proposal",
                                     "extreme_dark_object": "darkest 1% of class-1 luminance, excluded within 25 micrometers"},
               "claim_boundary": "Ablations test sensitivity to proposal-derived compartments; they do not validate those compartments."}
    output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--stain", choices=["HE", "SafO", "PLM"], default="SafO")
    parser.add_argument("--site", choices=["Medial", "Lateral"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    receipt = run_ablation_batch(json.loads(args.manifest.read_text(encoding="utf-8")), args.stain, args.site, args.output, args.workers)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
