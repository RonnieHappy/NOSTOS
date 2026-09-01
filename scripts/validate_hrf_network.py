"""Execute the frozen HRF network-module protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.stats import spearmanr
from skimage.filters import frangi, threshold_otsu
from skimage.morphology import skeletonize

from nostos.features.response_modules import erosion_survival_response


PROTOCOL = "nostos-hrf-network/1.0"
ARCHIVE_SHA256 = "a914d02cda161b7f33f25d0397c276d50e9a6cbc705e9b364a54f0adafed57e4"


def _pool_max(mask: np.ndarray) -> np.ndarray:
    height = mask.shape[0] - mask.shape[0] % 2
    width = mask.shape[1] - mask.shape[1] % 2
    return mask[:height, :width].reshape(height // 2, 2, width // 2, 2).max(axis=(1, 3))


def _skeleton_metrics(mask: np.ndarray, spacing: float) -> dict[str, float]:
    skeleton = skeletonize(mask)
    neighbors = ndimage.convolve(skeleton.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), mode="constant") - skeleton
    vertices = int(skeleton.sum())
    endpoints = int(np.sum(skeleton & (neighbors == 1)))
    junctions = int(np.sum(skeleton & (neighbors >= 3)))
    components = int(ndimage.label(skeleton, structure=np.ones((3, 3), dtype=np.uint8))[1])
    horizontal_vertical = int(np.sum(skeleton[:, 1:] & skeleton[:, :-1]) + np.sum(skeleton[1:, :] & skeleton[:-1, :]))
    diagonals = int(np.sum(skeleton[1:, 1:] & skeleton[:-1, :-1]) + np.sum(skeleton[1:, :-1] & skeleton[:-1, 1:]))
    edges = horizontal_vertical + diagonals
    length = spacing * (horizontal_vertical + np.sqrt(2.0) * diagonals)
    return {
        "skeleton_pixels": float(vertices), "length_relative": float(length),
        "endpoints": float(endpoints), "junction_pixels": float(junctions),
        "components": float(components), "cycle_rank": float(max(0, edges - vertices + components)),
    }


def _image_proposal(image: np.ndarray, fov: np.ndarray) -> np.ndarray:
    green = image[..., 1].astype(float) / 255.0
    reduced = green[::2, ::2]
    reduced_fov = _pool_max(fov)
    response = frangi(1.0 - reduced, sigmas=(1, 2, 3), black_ridges=False)
    eligible = response[reduced_fov]
    cutoff = threshold_otsu(eligible) if eligible.size else 1.0
    return (response >= cutoff) & reduced_fov


def run(root: Path, output: Path) -> dict:
    import skimage

    manual_dir, image_dir, fov_dir = root / "manual1", root / "images", root / "mask"
    masks = sorted(manual_dir.glob("*.tif"))
    rows = []
    thresholds = (0.0, 2.0, 4.0, 8.0)
    for mask_path in masks:
        case = mask_path.stem
        reference = np.asarray(Image.open(mask_path)) > 0
        down = _pool_max(reference)
        native_response = erosion_survival_response(reference, spacing_um=(1.0, 1.0), thresholds_um=thresholds)
        down_response = erosion_survival_response(down, spacing_um=(2.0, 2.0), thresholds_um=thresholds)
        native_skeleton = _skeleton_metrics(reference, 1.0)
        down_skeleton = _skeleton_metrics(down, 2.0)
        image_path = next(image_dir.glob(case + ".*"))
        fov_path = fov_dir / f"{case}_mask.tif"
        image = np.asarray(Image.open(image_path).convert("RGB"))
        fov = np.asarray(Image.open(fov_path).convert("L")) > 0
        proposal = _image_proposal(image, fov)
        reference_down = _pool_max(reference)
        intersection = int(np.sum(proposal & reference_down))
        dice = float(2 * intersection / max(1, int(proposal.sum() + reference_down.sum())))
        rows.append({
            "case": case,
            "native_survival": list(native_response.surviving_fraction),
            "twofold_survival": list(down_response.surviving_fraction),
            "native_components": list(native_response.component_count),
            "twofold_components": list(down_response.component_count),
            "native_skeleton": native_skeleton, "twofold_skeleton": down_skeleton,
            "image_derived_dice": dice,
        })
    native = np.asarray([row["native_survival"] for row in rows])
    down = np.asarray([row["twofold_survival"] for row in rows])
    differences = np.abs(native - down)
    native_auc = np.trapezoid(native, thresholds, axis=1)
    down_auc = np.trapezoid(down, thresholds, axis=1)
    native_length = np.asarray([row["native_skeleton"]["length_relative"] for row in rows])
    down_length = np.asarray([row["twofold_skeleton"]["length_relative"] for row in rows])
    length_relative_error = np.abs(down_length - native_length) / np.maximum(native_length, 1e-12)
    survival_monotone = all(np.all(np.diff(np.asarray(row["native_survival"])) <= 1e-12) and np.all(np.diff(np.asarray(row["twofold_survival"])) <= 1e-12) for row in rows)
    survival_rho = float(spearmanr(native_auc, down_auc).statistic)
    length_rho = float(spearmanr(native_length, down_length).statistic)
    gates = {
        "all_45_cases_processed": len(rows) == 45,
        "finite_and_monotone": bool(np.isfinite(native).all() and np.isfinite(down).all() and survival_monotone),
        "median_survival_difference_each_threshold_at_most_0_05": bool(np.all(np.median(differences[:, 1:], axis=0) <= 0.05)),
        "survival_auc_spearman_at_least_0_85": survival_rho >= 0.85,
        "skeleton_length_spearman_at_least_0_90": length_rho >= 0.90,
        "median_skeleton_length_relative_error_at_most_0_15": float(np.median(length_relative_error)) <= 0.15,
        "provenance_recorded": skimage.__version__ == "0.25.2" and (root.parent / "all.zip").is_file(),
    }
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "source": {
            "name": "High-Resolution Fundus Image Database", "case_count": len(rows),
            "archive_sha256": ARCHIVE_SHA256, "license": "CC BY 4.0",
            "url": "https://www5.informatik.uni-erlangen.de/indexbbb3.html?L=&id=1531&type=98",
        },
        "comparator": {"implementation": "scikit-image skeletonize", "version": skimage.__version__},
        "summary": {
            "median_absolute_survival_difference": np.median(differences, axis=0).tolist(),
            "survival_auc_spearman": survival_rho,
            "skeleton_length_spearman": length_rho,
            "median_skeleton_length_relative_error": float(np.median(length_relative_error)),
            "median_image_derived_dice": float(np.median([row["image_derived_dice"] for row in rows])),
        },
        "gates": gates, "cases": rows,
        "interpretation": "Reference-mask network stability only; image-derived segmentation and clinical utility are not validated.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "hrf_network_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.data.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
