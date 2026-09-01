"""Prospectively frozen BBBC007 confirmation of bright-object Hessian localization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from sklearn.metrics import average_precision_score, roc_auc_score

from nostos.features.response_modules import hessian_morphology_maps


DATASET = "BBBC007v1"
SOURCE = "https://bbbc.broadinstitute.org/BBBC007"
PROTOCOL_SHA256 = "eab07b4a474200e56fd0bca27b01733cf226a230cb2d1e49ca9810d71aef9356"
ARCHIVE_HASHES = {
    "images.zip": "b7009e2fce0a3152a5c9adda916eaa699d09696f4bd02a7d05d12d041e30c6d1",
    "outlines.zip": "6a5246f9a9d743d22eafdb409fae638a8461af97e9ff9c4a92f25eba236224d3",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_dna_channel(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith("d.tif") or name.endswith("_d_1ul.tif") or name.endswith("d0.tif")


def _normalize(values: np.ndarray) -> np.ndarray:
    low, high = np.percentile(values, (1, 99.8))
    return np.clip((values - low) / max(high - low, np.finfo(float).eps), 0, 1)


def _filled_outline(values: np.ndarray) -> np.ndarray:
    """Convert BBBC007's white-background, black closed outlines into foreground."""
    return ndimage.binary_fill_holes(~values.astype(bool))


def _load_pair(image_path: Path, outline_path: Path, maximum: int = 256) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(image_path) as opened:
        grayscale = opened.convert("I")
        scale = min(1.0, maximum / max(grayscale.size))
        size = tuple(max(32, int(round(value * scale))) for value in grayscale.size)
        image = np.asarray(grayscale.resize(size, Image.Resampling.BILINEAR), dtype=float)
    with Image.open(outline_path) as opened:
        filled = _filled_outline(np.asarray(opened))
        mask_image = Image.fromarray(filled.astype(np.uint8) * 255)
        mask = np.asarray(mask_image.resize(size, Image.Resampling.NEAREST), dtype=bool)
    return _normalize(image), mask


def _interval(values: np.ndarray, seed: int = 7007, draws: int = 10000) -> list[float]:
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
    return [float(value) for value in np.quantile(sampled, (.025, .975))]


def _success_gates(rows: list[dict]) -> dict:
    auc = np.asarray([row["nostos_blob_roc_auc"] for row in rows])
    ap_chance = np.asarray([row["nostos_blob_average_precision"] - row["foreground_fraction"] for row in rows])
    auc_log = np.asarray([row["nostos_blob_roc_auc"] - row["multiscale_log_roc_auc"] for row in rows])
    return {
        "mean_auc_gt_0.75": {"value": float(auc.mean()), "pass": bool(auc.mean() > .75)},
        "ap_above_prevalence_ci_lower_gt_0": {"ci95_mean": _interval(ap_chance), "pass": bool(_interval(ap_chance)[0] > 0)},
        "auc_above_log_ci_lower_gt_0": {"ci95_mean": _interval(auc_log), "pass": bool(_interval(auc_log)[0] > 0)},
    }


def validate_nuclei_confirmatory(data_root: Path, output: Path) -> dict:
    for name, expected in ARCHIVE_HASHES.items():
        path = data_root / name
        if not path.is_file() or _sha256(path).lower() != expected:
            raise ValueError(f"Missing or checksum-mismatched official archive: {name}")
    image_root = data_root / "images" / "BBBC007_v1_images"
    outline_root = data_root / "outlines" / "BBBC007_v1_outlines"
    image_paths = sorted(path for path in image_root.rglob("*.tif") if _is_dna_channel(path))
    if len(image_paths) != 16:
        raise ValueError(f"Expected 16 DNA fields from the locked naming rule, found {len(image_paths)}")

    rows = []
    for image_path in image_paths:
        relative = image_path.relative_to(image_root)
        outline_path = outline_root / relative
        if not outline_path.is_file():
            raise FileNotFoundError(f"Missing matching BBBC007 outline: {relative}")
        image, mask = _load_pair(image_path, outline_path)
        spacing = 1.0 / max(image.shape)
        scales = tuple(spacing * value for value in (2, 4, 8))
        fields = hessian_morphology_maps(image, spacing_um=(spacing, spacing), scales_um=scales, polarity="bright")
        blob = np.max(np.stack(fields["blob"]), axis=0)
        log = np.max(np.stack([np.abs(ndimage.gaussian_laplace(image, sigma=s)) * s**2 for s in (2, 4, 8)]), axis=0)
        truth = mask.ravel().astype(int)
        row = {"case": relative.as_posix(), "foreground_fraction": float(mask.mean())}
        for name, score in {"nostos_blob": blob, "intensity": image, "multiscale_log": log}.items():
            row[f"{name}_average_precision"] = float(average_precision_score(truth, score.ravel()))
            row[f"{name}_roc_auc"] = float(roc_auc_score(truth, score.ravel()))
        rows.append(row)

    summary = {}
    for metric in ("average_precision", "roc_auc"):
        for method in ("nostos_blob", "intensity", "multiscale_log"):
            values = np.asarray([row[f"{method}_{metric}"] for row in rows])
            summary[f"{method}_{metric}"] = {"mean": float(values.mean()), "median": float(np.median(values)), "ci95_mean": _interval(values)}
        for baseline in ("intensity", "multiscale_log"):
            difference = np.asarray([row[f"nostos_blob_{metric}"] - row[f"{baseline}_{metric}"] for row in rows])
            summary[f"nostos_minus_{baseline}_{metric}"] = {"mean": float(difference.mean()), "ci95_mean": _interval(difference)}
    gates = _success_gates(rows)
    status = "pass" if all(gate["pass"] for gate in gates.values()) else "fail"
    payload = {
        "protocol_version": "nostos-external-nuclei-confirmatory/1.0",
        "protocol_sha256": PROTOCOL_SHA256,
        "dataset": DATASET, "source": SOURCE, "license": "CC0",
        "design": "prospectively frozen transfer from BBBC039 to all 16 BBBC007 DNA fields; no fitting, threshold selection, case exclusion, or BBBC007-informed method choice",
        "input_archives": ARCHIVE_HASHES,
        "method": {"resize_maximum_pixels": 256, "dimensionless_scales_pixels": [2, 4, 8], "polarity": "bright", "aggregation": "maximum across scales"},
        "validity": {"status": status, "physical_scale": "abstain: pixel spacing not provided", "interpretation": "Foreground localization against filled manual nuclear outlines; not instance segmentation, counting, or phenotype prediction."},
        "success_gates": gates, "case_count": len(rows), "summary": summary, "cases": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "external_nuclei_confirmatory.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
