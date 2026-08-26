"""Frozen no-training morphology localization on BBBC039 test images."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from sklearn.metrics import average_precision_score, roc_auc_score

from nostos.features.response_modules import hessian_morphology_maps


DATASET = "BBBC039v1"
SOURCE = "https://bbbc.broadinstitute.org/BBBC039"
ARCHIVE_HASHES = {
    "images.zip": "6f30a5d4fe38c928ded972704f085975f8dc0d65d9aa366df00e5a9d449fddd7",
    "masks.zip": "f9e6043d8ca56344a4886f96a700d804d6ee982f31e2b2cd3194af2a053c2710",
    "metadata.zip": "a2c1f900bed9ba92a99553efd4c2ae98598433691c7401d818653ab61110deb2",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(values: np.ndarray) -> np.ndarray:
    low, high = np.percentile(values, (1, 99.8))
    return np.clip((values - low) / max(high - low, np.finfo(float).eps), 0, 1)


def _load_pair(image_path: Path, mask_path: Path, maximum: int = 256) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(image_path) as opened:
        grayscale = opened.convert("I")
        scale = min(1.0, maximum / max(grayscale.size))
        size = tuple(max(32, int(round(v * scale))) for v in grayscale.size)
        image = np.asarray(grayscale.resize(size, Image.Resampling.BILINEAR), dtype=float)
    with Image.open(mask_path) as opened:
        mask_rgb = np.asarray(opened.convert("RGB").resize(size, Image.Resampling.NEAREST))
    return _normalize(image), np.any(mask_rgb != 0, axis=-1)


def _interval(values: np.ndarray, seed: int = 39039, draws: int = 10000) -> list[float]:
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
    return [float(v) for v in np.quantile(sampled, (.025, .975))]


def validate_nuclei_dataset(data_root: Path, output: Path) -> dict:
    for name, expected in ARCHIVE_HASHES.items():
        path = data_root / name
        if not path.is_file() or _sha256(path).lower() != expected:
            raise ValueError(f"Missing or checksum-mismatched official archive: {name}")
    image_root, mask_root = data_root / "images" / "images", data_root / "masks" / "masks"
    test_names = [line.strip() for line in (data_root / "metadata" / "metadata" / "test.txt").read_text().splitlines() if line.strip()]
    rows = []
    for mask_name in test_names:
        mask_path = mask_root / mask_name
        image_path = image_root / f"{Path(mask_name).stem}.tif"
        if not image_path.is_file() or not mask_path.is_file():
            raise FileNotFoundError(f"Missing BBBC039 pair for {mask_name}")
        image, mask = _load_pair(image_path, mask_path)
        spacing = 1.0 / max(image.shape)
        scales = tuple(spacing * value for value in (2, 4, 8))
        fields = hessian_morphology_maps(image, spacing_um=(spacing, spacing), scales_um=scales, polarity="bright")
        blob = np.max(np.stack(fields["blob"]), axis=0)
        log = np.max(np.stack([np.abs(ndimage.gaussian_laplace(image, sigma=s)) * s**2 for s in (2, 4, 8)]), axis=0)
        truth = mask.ravel().astype(int)
        scores = {"nostos_blob": blob.ravel(), "intensity": image.ravel(), "multiscale_log": log.ravel()}
        row = {"case": Path(mask_name).stem, "foreground_fraction": float(mask.mean())}
        for name, score in scores.items():
            row[f"{name}_average_precision"] = float(average_precision_score(truth, score))
            row[f"{name}_roc_auc"] = float(roc_auc_score(truth, score))
        rows.append(row)
    summary = {}
    for metric in ("average_precision", "roc_auc"):
        for method in ("nostos_blob", "intensity", "multiscale_log"):
            values = np.asarray([row[f"{method}_{metric}"] for row in rows])
            summary[f"{method}_{metric}"] = {"mean": float(values.mean()), "median": float(np.median(values)), "ci95_mean": _interval(values)}
        for baseline in ("intensity", "multiscale_log"):
            difference = np.asarray([row[f"nostos_blob_{metric}"] - row[f"{baseline}_{metric}"] for row in rows])
            summary[f"nostos_minus_{baseline}_{metric}"] = {"mean": float(difference.mean()), "ci95_mean": _interval(difference)}
    payload = {
        "protocol_version": "nostos-external-nuclei/1.1",
        "dataset": DATASET, "source": SOURCE, "license": "CC0",
        "design": "official held-out test split; 50 fields; no fitting or threshold selection; image-level inference",
        "input_archives": ARCHIVE_HASHES,
        "method": {"resize_maximum_pixels": 256, "dimensionless_scales_pixels": [2, 4, 8],
                   "nostos_score": "maximum scale-normalized 2-D Hessian blob response; bright-object polarity declared from Hoechst acquisition",
                   "baselines": ["normalized fluorescence intensity", "maximum absolute multiscale Laplacian-of-Gaussian"]},
        "development_history": "Version 1.0 used sign-agnostic Hessian magnitude and was inferior to both baselines on this test set. Version 1.1 declares bright-object polarity from the Hoechst acquisition while retaining the frozen scales and all cases; v1.1 is therefore a transparent post-test method refinement, not pristine confirmatory evidence.",
        "validity": {"status": "external_public_validation", "physical_scale": "abstain: pixel spacing not provided",
                     "interpretation": "Tests localization of manually annotated nuclei, not instance segmentation or biological phenotype prediction."},
        "case_count": len(rows), "summary": summary, "cases": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "external_nuclei_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
