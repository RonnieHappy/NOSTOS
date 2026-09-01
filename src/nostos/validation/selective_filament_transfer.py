"""Frozen external transfer of selective FFT orientation to filament microscopy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.metrics import roc_auc_score

from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.external_filament import DATASET_DOI, _find_pairs
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.selective_fft_confirmation import THRESHOLD, _wilson
from nostos.validation.selective_fft_development import self_perturbation_score


PROTOCOL_SHA256 = "43176afa590402d9851588f3c57ec3bbee86041f48bd817ac77b79bb3f3e4242"


def _load_square(image_path: Path, mask_path: Path) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(image_path) as opened:
        image = np.asarray(opened.convert("L"), dtype=np.float32) / 255.0
    with Image.open(mask_path) as opened:
        mask = np.asarray(opened.convert("L")) > 0
    height = min(image.shape[0], mask.shape[0])
    width = min(image.shape[1], mask.shape[1])
    image, mask = image[:height, :width], mask[:height, :width]
    side = min(height, width)
    y0, x0 = (height - side) // 2, (width - side) // 2
    image, mask = image[y0:y0 + side, x0:x0 + side], mask[y0:y0 + side, x0:x0 + side]
    image = np.asarray(Image.fromarray(image, mode="F").resize((128, 128), Image.Resampling.BILINEAR), dtype=np.float32)
    mask = np.asarray(Image.fromarray(mask).resize((128, 128), Image.Resampling.NEAREST)) > 0
    return image, mask


def run_transfer(data_root: Path, output: Path) -> dict:
    pairs = _find_pairs(data_root)
    if len(pairs) < 15:
        raise ValueError(f"Expected at least 15 image-mask pairs; found {len(pairs)}")
    rows = []
    for species, image_path, mask_path in pairs:
        image, mask = _load_square(image_path, mask_path)
        score, diagnostics = self_perturbation_score(image, 1.0)
        image_measurement = diagnostics["measurement"]
        mask_measurement = extract_spatial_fft(mask.astype(np.float32), pixel_size_um=1.0)
        coverage = float(mask.mean())
        eligible = coverage >= 0.005 and mask_measurement.anisotropy >= 0.15
        disagreement = axial_angular_error_degrees(
            image_measurement["orientation"], mask_measurement.orientation_degrees
        )
        invalid = bool(disagreement > 10.0) if eligible else None
        accepted = bool(score <= THRESHOLD)
        pixels_per_scale = image_measurement["wavelength"]
        legacy_accepted = not (image_measurement["snr"] < 3.0 or pixels_per_scale < 4.0)
        rows.append({
            "species": species,
            "image": image_path.name,
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
            "mask_coverage": coverage,
            "mask_orientation": float(mask_measurement.orientation_degrees),
            "mask_anisotropy": float(mask_measurement.anisotropy),
            "reference_eligible": eligible,
            "image_orientation": float(image_measurement["orientation"]),
            "axial_disagreement_degrees": float(disagreement),
            "score": float(score),
            "accepted": accepted,
            "legacy_accepted": legacy_accepted,
            "invalid": invalid,
            "diagnostics": diagnostics,
        })
    eligible_rows = [row for row in rows if row["reference_eligible"]]
    accepted = [row for row in eligible_rows if row["accepted"]]
    legacy = [row for row in eligible_rows if row["legacy_accepted"]]
    invalid_count = sum(bool(row["invalid"]) for row in accepted)
    coverage = len(accepted) / len(eligible_rows) if eligible_rows else 0.0
    risk = invalid_count / len(accepted) if accepted else 1.0
    risk_all = float(np.mean([row["invalid"] for row in eligible_rows])) if eligible_rows else 1.0
    legacy_coverage = len(legacy) / len(eligible_rows) if eligible_rows else 0.0
    legacy_risk = float(np.mean([row["invalid"] for row in legacy])) if legacy else 1.0
    labels = [bool(row["invalid"]) for row in eligible_rows]
    auc = float(roc_auc_score(labels, [row["score"] for row in eligible_rows])) if len(set(labels)) == 2 else None
    median_error = float(np.median([row["axial_disagreement_degrees"] for row in accepted])) if accepted else None
    wilson = _wilson(invalid_count, len(accepted))
    gates = {
        "reference_eligible_ge_15": len(eligible_rows) >= 15,
        "selective_coverage_ge_0.40": coverage >= 0.40,
        "selective_risk_wilson_upper_le_0.20": wilson[1] <= 0.20,
        "accepted_median_disagreement_le_5_degrees": median_error is not None and median_error <= 5.0,
        "lower_risk_than_unselected_and_legacy_or_legacy_low_coverage": risk < risk_all and (risk < legacy_risk or legacy_coverage < coverage / 2),
        "invalid_detection_auc_ge_0.75": auc is not None and auc >= 0.75,
    }
    payload = {
        "protocol_version": "nostos-selective-filament-transfer/1.0",
        "protocol_sha256": PROTOCOL_SHA256,
        "dataset": {"doi": DATASET_DOI, "role": "external images and manual masks"},
        "frozen_threshold": THRESHOLD,
        "status": "pass" if all(gates.values()) else "fail",
        "summary": {
            "n_images": len(rows), "reference_eligible": len(eligible_rows),
            "accepted": len(accepted), "selective_coverage": coverage,
            "selective_risk": risk, "selective_risk_wilson95": wilson,
            "risk_all": risk_all, "invalid_detection_auc": auc,
            "legacy_coverage": legacy_coverage, "legacy_risk": legacy_risk,
            "accepted_median_axial_disagreement_degrees": median_error,
        },
        "success_gates": gates,
        "scope": "External biological transfer of selective 2D FFT orientation; no physical scale validation.",
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "selective_filament_transfer.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload

