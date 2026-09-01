"""Cross-species validation on annotated public mycelium images."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from sklearn.metrics import balanced_accuracy_score
from sklearn.base import clone
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from nostos.features.response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    local_thickness_response,
    structure_tensor_response,
)

DATASET_DOI = "10.5281/zenodo.15224240"


def _repeated_predictions(model, x: np.ndarray, y: np.ndarray, splits) -> tuple[np.ndarray, np.ndarray]:
    truth = []
    prediction = []
    for train_index, test_index in splits:
        fitted = clone(model).fit(x[train_index], y[train_index])
        truth.extend(y[test_index])
        prediction.extend(fitted.predict(x[test_index]))
    return np.asarray(truth), np.asarray(prediction)


def _find_pairs(root: Path) -> list[tuple[str, Path, Path]]:
    pairs = []
    for mask_path in sorted(root.rglob("*.png")):
        if "__MACOSX" in mask_path.parts or mask_path.name.startswith("._"):
            continue
        parts_lower = [part.lower() for part in mask_path.parts]
        if "mask" not in parts_lower and "masks" not in parts_lower:
            continue
        mask_index = max(i for i, part in enumerate(parts_lower) if part in {"mask", "masks"})
        species = next((part.upper() for part in mask_path.parts if part.upper() in {"GS", "PO", "TS"}), "UNKNOWN")
        image_dir_name = "image" if parts_lower[mask_index] == "mask" else "images"
        image_parts = list(mask_path.parts)
        image_parts[mask_index] = image_dir_name
        base = Path(*image_parts).with_suffix("")
        candidates = [base.with_suffix(extension) for extension in (".jpg", ".jpeg", ".png")]
        image_path = next((path for path in candidates if path.is_file()), None)
        if image_path is not None and species != "UNKNOWN":
            pairs.append((species, image_path, mask_path))
    return pairs


def _load_normalized(image_path: Path, mask_path: Path, maximum_size: int = 256) -> tuple[np.ndarray, np.ndarray, float]:
    with Image.open(image_path) as opened:
        grayscale = opened.convert("L")
        scale = min(1.0, maximum_size / max(grayscale.size))
        size = tuple(max(32, int(round(value * scale))) for value in grayscale.size)
        grayscale = grayscale.resize(size, Image.Resampling.BILINEAR)
        image = np.asarray(grayscale, dtype=float) / 255.0
    with Image.open(mask_path) as opened:
        mask = np.asarray(opened.convert("L").resize(size, Image.Resampling.NEAREST)) > 0
    relative_spacing = 1.0 / max(image.shape)
    return image, mask, relative_spacing


def _feature_blocks(image: np.ndarray, mask: np.ndarray, spacing: float) -> dict[str, np.ndarray]:
    scales = tuple(spacing * value for value in (2, 4, 8, 16))
    tensor = structure_tensor_response(image, spacing_um=(spacing, spacing), scales_um=scales)
    hessian = hessian_morphology_response(image, spacing_um=(spacing, spacing), scales_um=scales)
    thickness = local_thickness_response(mask, spacing_um=(spacing, spacing), size_bins=24)
    thresholds = tuple(spacing * value for value in (0, 1, 2, 4, 8))
    network = erosion_survival_response(mask, spacing_um=(spacing, spacing), thresholds_um=thresholds)
    separations = tuple(spacing * value for value in (1, 2, 4, 8, 16, 24))
    spatial = directional_variogram(image, spacing_um=(spacing, spacing), separations_um=separations)
    angle = np.deg2rad(np.asarray(tensor.orientation_degrees) * 2)
    thickness_quantiles = np.quantile(thickness.local_thickness_values_um, (0.1, 0.25, 0.5, 0.75, 0.9))
    return {
        "coverage": np.asarray([float(mask.mean())]),
        "tensor": np.asarray([*np.cos(angle), *np.sin(angle), *tensor.coherency]),
        "hessian": np.asarray([*hessian.blob, *hessian.tube, *hessian.sheet]),
        "geometry": np.asarray(thickness_quantiles),
        "network": np.asarray([*network.surviving_fraction, *network.component_count]),
        "spatial": np.asarray([*spatial.horizontal, *spatial.vertical]),
    }


def _conventional_features(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    selected = image[mask]
    gy, gx = np.gradient(image)
    gradient = np.hypot(gx, gy)
    histogram, _ = np.histogram(selected, bins=16, range=(0, 1), density=True)
    return np.asarray([
        float(mask.mean()), selected.mean(), selected.std(),
        np.percentile(selected, 10), np.median(selected), np.percentile(selected, 90),
        gradient.mean(), gradient.std(), np.mean(np.abs(gx)), np.mean(np.abs(gy)), *histogram,
    ])


def _evaluate(model, x: np.ndarray, y: np.ndarray, splits) -> float:
    truth, prediction = _repeated_predictions(model, x, y, splits)
    return float(balanced_accuracy_score(truth, prediction))


def validate_filament_dataset(data_root: Path, output: Path, *, repeats: int = 20, permutations: int = 200) -> dict:
    pairs = _find_pairs(data_root)
    if len(pairs) < 15:
        raise ValueError(f"Expected at least 15 paired filament images and masks; found {len(pairs)}.")
    blocks_by_case = []
    conventional = []
    labels = []
    cases = []
    for species, image_path, mask_path in pairs:
        image, mask, spacing = _load_normalized(image_path, mask_path)
        blocks_by_case.append(_feature_blocks(image, mask, spacing))
        conventional.append(_conventional_features(image, mask))
        labels.append(species)
        cases.append({
            "species": species,
            "image": image_path.name,
            "mask": mask_path.name,
            "normalized_shape": list(image.shape),
            "mask_fraction": float(mask.mean()),
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
        })
    block_names = tuple(sorted(blocks_by_case[0]))
    x = np.stack([np.concatenate([blocks[name] for name in block_names]) for blocks in blocks_by_case])
    y = np.asarray(labels)
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=repeats, random_state=15224240)
    model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
    cv_splits = list(cv.split(x, y))
    observed = _evaluate(model, x, y, cv_splits)
    comparison = {
        "nostos_response_geometry": observed,
        "conventional_scalar": _evaluate(model, np.stack(conventional), y, cv_splits),
    }
    naive = np.stack([
        np.asarray([value for name in block_names for value in (
            blocks[name].mean(), blocks[name].std(), blocks[name].min(), blocks[name].max()
        )]) for blocks in blocks_by_case
    ])
    comparison["naive_block_summaries"] = _evaluate(model, naive, y, cv_splits)
    for omitted in block_names:
        ablated = np.stack([np.concatenate([blocks[name] for name in block_names if name != omitted]) for blocks in blocks_by_case])
        comparison[f"nostos_without_{omitted}"] = _evaluate(model, ablated, y, cv_splits)
    rng = np.random.default_rng(15224240)
    permutation_scores = []
    # A fixed feature matrix and CV schedule are used; labels are permuted at
    # specimen level. 200 permutations balance auditability and CPU runtime.
    splits = list(RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=15224240).split(x, y))
    for _ in range(permutations):
        permuted = rng.permutation(y)
        permuted_truth, permuted_prediction = _repeated_predictions(model, x, permuted, splits)
        permutation_scores.append(float(balanced_accuracy_score(permuted_truth, permuted_prediction)))
    p_value = (1 + sum(score >= observed for score in permutation_scores)) / (len(permutation_scores) + 1)
    payload = {
        "protocol_version": "nostos-external-filament/1.0",
        "dataset": {
            "title": "A Mycelium Dataset with Edge-Precise Annotation for Semantic Segmentation",
            "doi": DATASET_DOI,
            "archive": "labeled-GS_PO_TS.zip",
            "role": "external public images and manual masks; not acquired by NOSTOS investigators",
        },
        "coordinate_system": "dimensionless normalized image coordinates; no physical pixel calibration claimed",
        "cases": cases,
        "summary": {
            "n_images": len(cases),
            "species_counts": {species: labels.count(species) for species in sorted(set(labels))},
            "repeated_stratified_balanced_accuracy": observed,
            "permutation_p": p_value,
            "feature_count": int(x.shape[1]),
            "representation_comparison": comparison,
        },
        "validity": {
            "status": "exploratory_cross_domain",
            "reason": "Species discrimination demonstrates sensitivity to annotated network organization but does not identify biological mechanism, and image acquisition may confound species.",
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "external_filament_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
