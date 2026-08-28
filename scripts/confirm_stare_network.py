"""Execute the untouched STARE network confirmation."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.stats import spearmanr
from skimage.morphology import skeletonize

from nostos.features.response_modules import erosion_survival_response


PROTOCOL = "nostos-stare-network-confirmation/1.0"
HASHES = {
    "labels-ah.tar": "ebf2f1e17ca955f24579d9edd990e2dae79a5c82def69f0985d8e24f826ddd2f",
    "labels-vk.tar": "47474a701536b0cfdb369fdce012be36141e9f44d80387f0179446b5cb0f5576",
    "stare-images.tar": "5f7b509b6067cad4f1be84933145d783de9ec087b3eaaf4db0103dd0144dd433",
}


def _load_mask(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as stream:
        with Image.open(stream) as opened:
            return np.asarray(opened.convert("L")) > 0


def _downsample(mask: np.ndarray) -> np.ndarray:
    height = mask.shape[0] - mask.shape[0] % 2
    width = mask.shape[1] - mask.shape[1] % 2
    occupancy = mask[:height, :width].reshape(height // 2, 2, width // 2, 2).mean(axis=(1, 3))
    return occupancy >= 0.25


def _length(mask: np.ndarray, spacing: float) -> float:
    skeleton = skeletonize(mask)
    straight = int(np.sum(skeleton[:, 1:] & skeleton[:, :-1]) + np.sum(skeleton[1:, :] & skeleton[:-1, :]))
    diagonal = int(np.sum(skeleton[1:, 1:] & skeleton[:-1, :-1]) + np.sum(skeleton[1:, :-1] & skeleton[:-1, 1:]))
    return float(spacing * (straight + np.sqrt(2.0) * diagonal))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(root: Path, output: Path) -> dict:
    import skimage

    observed_hashes = {name: _sha256(root / name) for name in HASHES}
    thresholds = (0.0, 2.0, 4.0, 8.0)
    rows = []
    for ah_path in sorted((root / "labels-ah").glob("*.ah.ppm.gz")):
        case = ah_path.name.split(".", 1)[0]
        vk_path = root / "labels-vk" / f"{case}.vk.ppm.gz"
        ah = _load_mask(ah_path)
        vk = _load_mask(vk_path)
        reduced = _downsample(ah)
        native = erosion_survival_response(ah, spacing_um=(1.0, 1.0), thresholds_um=thresholds, boundary_corrected=True)
        twofold = erosion_survival_response(reduced, spacing_um=(2.0, 2.0), thresholds_um=thresholds, boundary_corrected=True)
        observer = erosion_survival_response(vk, spacing_um=(1.0, 1.0), thresholds_um=thresholds, boundary_corrected=True)
        rows.append({
            "case": case,
            "ah_native_survival": list(native.surviving_fraction),
            "ah_twofold_survival": list(twofold.surviving_fraction),
            "vk_native_survival": list(observer.surviving_fraction),
            "ah_native_components": list(native.component_count),
            "ah_twofold_components": list(twofold.component_count),
            "ah_native_skeleton_length": _length(ah, 1.0),
            "ah_twofold_skeleton_length": _length(reduced, 2.0),
        })
    native = np.asarray([row["ah_native_survival"] for row in rows])
    twofold = np.asarray([row["ah_twofold_survival"] for row in rows])
    observer = np.asarray([row["vk_native_survival"] for row in rows])
    native_auc = np.trapezoid(native, thresholds, axis=1)
    twofold_auc = np.trapezoid(twofold, thresholds, axis=1)
    observer_auc = np.trapezoid(observer, thresholds, axis=1)
    native_length = np.asarray([row["ah_native_skeleton_length"] for row in rows])
    twofold_length = np.asarray([row["ah_twofold_skeleton_length"] for row in rows])
    difference = np.abs(native - twofold)
    relative_length_error = np.abs(native_length - twofold_length) / np.maximum(native_length, 1e-12)
    survival_rho = float(spearmanr(native_auc, twofold_auc).statistic)
    length_rho = float(spearmanr(native_length, twofold_length).statistic)
    observer_rho = float(spearmanr(native_auc, observer_auc).statistic)
    monotone = bool(np.all(np.diff(native, axis=1) <= 1e-12) and np.all(np.diff(twofold, axis=1) <= 1e-12))
    gates = {
        "all_20_cases_finite_and_monotone": len(rows) == 20 and bool(np.isfinite(native).all()) and monotone,
        "median_survival_difference_each_threshold_at_most_0_05": bool(np.all(np.median(difference[:, 1:], axis=0) <= 0.05)),
        "survival_auc_spearman_at_least_0_85": survival_rho >= 0.85,
        "skeleton_length_spearman_at_least_0_90": length_rho >= 0.90,
        "median_skeleton_length_relative_error_at_most_0_15": float(np.median(relative_length_error)) <= 0.15,
        "observer_survival_auc_spearman_at_least_0_80": observer_rho >= 0.80,
        "provenance_complete": observed_hashes == HASHES and skimage.__version__ == "0.25.2",
    }
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "source": {"name": "STARE vessel labels", "url": "https://cecas.clemson.edu/~ahoover/stare/probing/", "archive_sha256": observed_hashes},
        "method": {"boundary_distance_correction": "subtract_half_minimum_spacing", "twofold_occupancy_cutoff": 0.25},
        "comparator": {"implementation": "scikit-image skeletonize", "version": skimage.__version__},
        "summary": {
            "case_count": len(rows), "median_absolute_survival_difference": np.median(difference, axis=0).tolist(),
            "survival_auc_spearman": survival_rho, "skeleton_length_spearman": length_rho,
            "median_skeleton_length_relative_error": float(np.median(relative_length_error)),
            "ah_vk_survival_auc_spearman": observer_rho,
        },
        "gates": gates, "cases": rows,
        "interpretation": "Untouched external confirmation of reference-mask sampling stability only.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "stare_network_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.data.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
