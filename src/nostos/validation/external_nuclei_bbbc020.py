"""Frozen independent-acquisition transfer to partially annotated BBBC020 fields."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from sklearn.metrics import average_precision_score, roc_auc_score

from nostos.features.response_modules import hessian_morphology_maps


SOURCE = "https://bbbc.broadinstitute.org/BBBC020"
PROTOCOL_SHA256 = "3d209232d07b88ff33301bd10836ca6ee47f8109bed94c79f456564a13f44968"
ARCHIVE_HASHES = {
    "images.zip": "edf4a87be957ec2b7ab268bef92c2efae8e098dc0855a4fa9df80895ff7062e4",
    "outlines_nuclei.zip": "b212f10013ae2a0260976cff2134204ecba226853922aea2ab5289051a47ceb7",
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


def _local_support(masks: list[np.ndarray], ring_width: int = 4) -> tuple[np.ndarray, np.ndarray]:
    foreground = np.logical_or.reduce(masks)
    ring = np.zeros_like(foreground)
    for mask in masks:
        ring |= ndimage.binary_dilation(mask, iterations=ring_width) & ~mask
    ring &= ~foreground
    return foreground, foreground | ring


def _interval(values: np.ndarray, seed: int = 20020, draws: int = 10000) -> list[float]:
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
    return [float(value) for value in np.quantile(sampled, (.025, .975))]


def validate_bbbc020(data_root: Path, output: Path) -> dict:
    for name, expected in ARCHIVE_HASHES.items():
        path = data_root / name
        if not path.is_file() or _sha256(path).lower() != expected:
            raise ValueError(f"Missing or checksum-mismatched official archive: {name}")
    image_root = data_root / "images" / "BBBC020_v1_images"
    outline_root = data_root / "outlines_nuclei" / "BBC020_v1_outlines_nuclei"
    field_names = sorted({path.name.rsplit("_c5_", 1)[0] for path in outline_root.glob("*_c5_*.TIF")})
    if len(field_names) != 20:
        raise ValueError(f"Expected 20 annotated BBBC020 fields, found {len(field_names)}")

    rows = []
    for field in field_names:
        image_path = image_root / field / f"{field}_c5.TIF"
        outline_paths = sorted(path for path in outline_root.glob(f"{field}_c5_*.TIF") if path.stat().st_size > 0)
        if not image_path.is_file() or not outline_paths:
            raise FileNotFoundError(f"Missing BBBC020 image or outlines for {field}")
        with Image.open(image_path) as opened:
            rgb = opened.convert("RGB")
            scale = min(1.0, 256 / max(rgb.size))
            size = tuple(max(32, int(round(value * scale))) for value in rgb.size)
            image = np.asarray(rgb.resize(size, Image.Resampling.BILINEAR), dtype=float)[..., 2]
        masks = []
        for path in outline_paths:
            with Image.open(path) as opened:
                mask = np.asarray(opened.convert("L").resize(size, Image.Resampling.NEAREST)) > 0
            if mask.any():
                masks.append(mask)
        foreground, support = _local_support(masks)
        image = _normalize(image)
        spacing = 1.0 / max(image.shape)
        scales = tuple(spacing * value for value in (2, 4, 8))
        fields = hessian_morphology_maps(image, spacing_um=(spacing, spacing), scales_um=scales, polarity="bright")
        blob = np.max(np.stack(fields["blob"]), axis=0)
        log = np.max(np.stack([np.abs(ndimage.gaussian_laplace(image, sigma=s)) * s**2 for s in (2, 4, 8)]), axis=0)
        truth = foreground[support].astype(int)
        row = {"case": field, "annotated_objects": len(masks), "supported_pixels": int(support.sum()), "foreground_fraction": float(truth.mean())}
        for name, score in {"nostos_blob": blob, "intensity": image, "multiscale_log": log}.items():
            local_score = score[support]
            row[f"{name}_average_precision"] = float(average_precision_score(truth, local_score))
            row[f"{name}_roc_auc"] = float(roc_auc_score(truth, local_score))
        rows.append(row)

    summary = {}
    for metric in ("average_precision", "roc_auc"):
        for method in ("nostos_blob", "intensity", "multiscale_log"):
            values = np.asarray([row[f"{method}_{metric}"] for row in rows])
            summary[f"{method}_{metric}"] = {"mean": float(values.mean()), "median": float(np.median(values)), "ci95_mean": _interval(values)}
        for baseline in ("intensity", "multiscale_log"):
            difference = np.asarray([row[f"nostos_blob_{metric}"] - row[f"{baseline}_{metric}"] for row in rows])
            summary[f"nostos_minus_{baseline}_{metric}"] = {"mean": float(difference.mean()), "ci95_mean": _interval(difference)}
    auc = np.asarray([row["nostos_blob_roc_auc"] for row in rows])
    ap_chance = np.asarray([row["nostos_blob_average_precision"] - row["foreground_fraction"] for row in rows])
    ap_log = np.asarray([row["nostos_blob_average_precision"] - row["multiscale_log_average_precision"] for row in rows])
    gates = {
        "mean_auc_gt_0.75": {"value": float(auc.mean()), "pass": bool(auc.mean() > .75)},
        "ap_above_local_prevalence_ci_lower_gt_0": {"ci95_mean": _interval(ap_chance), "pass": bool(_interval(ap_chance)[0] > 0)},
        "ap_above_log_ci_lower_gt_0": {"ci95_mean": _interval(ap_log), "pass": bool(_interval(ap_log)[0] > 0)},
    }
    status = "pass" if all(gate["pass"] for gate in gates.values()) else "fail"
    payload = {
        "protocol_version": "nostos-external-nuclei-bbbc020/1.0", "protocol_sha256": PROTOCOL_SHA256,
        "dataset": "BBBC020v1", "source": SOURCE, "license": "CC BY-NC-SA 3.0",
        "design": "prospectively frozen independent-acquisition transfer; all 20 fields with archived manual nuclei; local support accounts for intentionally incomplete annotations",
        "input_archives": ARCHIVE_HASHES,
        "method": {"channel": "c5 DAPI", "resize_maximum_pixels": 256, "dimensionless_scales_pixels": [2, 4, 8], "polarity": "bright", "local_ring_pixels": 4},
        "validity": {"status": status, "physical_scale": "abstain: pixel spacing not provided", "interpretation": "Local foreground localization for eligible annotated nuclei; not whole-field or instance segmentation."},
        "success_gates": gates, "case_count": len(rows), "summary": summary, "cases": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "external_nuclei_bbbc020.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
