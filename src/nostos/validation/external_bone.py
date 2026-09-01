"""External trabecular-bone validation against archived reference thickness maps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.stats import spearmanr
from scipy.stats import wilcoxon

from nostos.features.response_modules import maximal_sphere_local_thickness

DATASET_DOI = "10.5281/zenodo.11061947"


def validate_bone_subset(data_root: Path, output: Path) -> dict:
    segmentation_files = sorted(data_root.glob("*_SEG_SUB.nii"))
    if not segmentation_files:
        raise FileNotFoundError(f"No bone segmentations found in {data_root}")
    cases = []
    for segmentation_path in segmentation_files:
        reference_path = segmentation_path.with_name(segmentation_path.name.replace("_SEG_SUB.nii", "_SEG_SUB_DT_THICK_CONVERT.nii"))
        if not reference_path.is_file():
            continue
        segmentation_image = nib.load(segmentation_path)
        mask = np.asanyarray(segmentation_image.dataobj) > 0
        reference = np.asanyarray(nib.load(reference_path).dataobj).astype(float)
        spacing_mm = tuple(float(v) for v in segmentation_image.header.get_zooms()[:3])
        baseline = 2.0 * distance_transform_edt(mask, sampling=spacing_mm)
        estimate = maximal_sphere_local_thickness(mask, spacing_um=spacing_mm, size_bins=32)
        truth = reference[mask]
        predicted = estimate[mask]
        if np.ptp(truth) <= np.finfo(float).eps or np.ptp(predicted) <= np.finfo(float).eps:
            rho = 0.0
        else:
            rho = float(spearmanr(truth, predicted).statistic)
            if not np.isfinite(rho):
                rho = 0.0
        difference = predicted - truth
        cases.append({
            "case": segmentation_path.name.replace("_SEG_SUB.nii", ""),
            "shape": list(mask.shape),
            "spacing_mm": list(spacing_mm),
            "bone_fraction": float(mask.mean()),
            "reference_mean_thickness_mm": float(truth.mean()),
            "nostos_mean_thickness_mm": float(predicted.mean()),
            "bias_mm": float(difference.mean()),
            "mae_mm": float(np.mean(np.abs(difference))),
            "voxelwise_spearman": rho,
            "nearest_boundary_baseline_mean_mm": float(baseline[mask].mean()),
            "nearest_boundary_baseline_mae_mm": float(np.mean(np.abs(baseline[mask] - truth))),
            "segmentation_sha256": hashlib.sha256(segmentation_path.read_bytes()).hexdigest(),
            "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        })
    if not cases:
        raise FileNotFoundError("No matched segmentation/reference pairs were found.")
    absolute_relative_bias = [abs(case["bias_mm"]) / case["reference_mean_thickness_mm"] for case in cases]
    rng = np.random.default_rng(11061947)
    indices = rng.integers(0, len(cases), size=(10000, len(cases)))
    bias_values = np.asarray(absolute_relative_bias)
    bootstrap_bias = bias_values[indices].mean(axis=1)
    nostos_mae = np.asarray([case["mae_mm"] for case in cases])
    baseline_mae = np.asarray([case["nearest_boundary_baseline_mae_mm"] for case in cases])
    paired = wilcoxon(nostos_mae, baseline_mae, alternative="less", method="exact")
    payload = {
        "protocol_version": "nostos-external-bone/1.0",
        "dataset": {
            "title": "MicroCT Trabecular Bone Samples for Trabecular Thickness and Separation Measures",
            "doi": DATASET_DOI,
            "license": "CC BY 4.0",
            "role": "external public reference data; not acquired by NOSTOS investigators",
        },
        "measurement": "NOSTOS maximal-inscribed-sphere thickness (32 frozen logarithmic radius levels) versus archived IPL thickness map",
        "cases": cases,
        "summary": {
            "n_volumes": len(cases),
            "mean_absolute_bias_fraction": float(np.mean(absolute_relative_bias)),
            "mean_absolute_bias_fraction_ci95": [float(np.quantile(bootstrap_bias, 0.025)), float(np.quantile(bootstrap_bias, 0.975))],
            "median_voxelwise_spearman": float(np.median([case["voxelwise_spearman"] for case in cases])),
            "mean_mae_mm": float(np.mean([case["mae_mm"] for case in cases])),
            "nearest_boundary_mean_mae_mm": float(baseline_mae.mean()),
            "paired_mae_reduction_mm": float(np.mean(baseline_mae - nostos_mae)),
            "wilcoxon_exact_one_sided_p": float(paired.pvalue),
        },
        "validity": {
            "status": "preliminary_external_validation",
            "reason": "The estimator is independently applied to public reference volumes, but three volumes from one archive cannot establish external generalization.",
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "external_bone_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
