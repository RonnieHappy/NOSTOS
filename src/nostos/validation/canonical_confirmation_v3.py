"""Prospectively frozen confirmation of canonical NOSTOS comparison geometry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.metrics import balanced_accuracy_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from nostos.features.canonical_geometry import canonical_response_blocks
from nostos.features.universal import analyze_response_geometry
from nostos.validation.comparators import conventional_vector, response_curve_blocks
from nostos.validation.phantoms import generate_phantom
from nostos.validation.perturbations import _center_crop_or_pad


PROTOCOL_SHA256 = "5665cd87be0890854e7a8934266b0b4ade5cbe56ec4f62582fc22f89fa55892d"
CLASSES = ("orientation", "spectral_scale", "blob", "roughness", "network", "heterogeneity")
MODULES = ("spectral", "tensor", "hessian", "spatial")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _standardize(image: np.ndarray) -> np.ndarray:
    values = np.asarray(image, dtype=np.float32)
    values = (values - values.mean()) / max(float(values.std()), np.finfo(np.float32).eps)
    return np.clip(values, -5, 5).astype(np.float32)


def _gamma(image: np.ndarray, value: float) -> np.ndarray:
    low, high = float(image.min()), float(image.max())
    unit = np.clip((image - low) / max(high - low, np.finfo(float).eps), 0, 1)
    return np.power(unit, value) * (high - low) + low


def _illumination(image: np.ndarray, magnitude: float, angle: float) -> np.ndarray:
    y, x = np.mgrid[-1:1:complex(image.shape[0]), -1:1:complex(image.shape[1])]
    gradient = np.cos(angle) * x + np.sin(angle) * y
    return image + magnitude * max(float(image.std()), np.finfo(float).eps) * gradient


def _shot_noise(image: np.ndarray, counts: float, rng: np.random.Generator) -> np.ndarray:
    low, high = float(image.min()), float(image.max())
    unit = np.clip((image - low) / max(high - low, np.finfo(float).eps), 0, 1)
    return rng.poisson(unit * counts) / counts * (high - low) + low


def _parameters(label: str, rng: np.random.Generator) -> dict[str, float]:
    ranges = {"orientation": (16, 28), "spectral_scale": (6, 13), "blob": (10, 30),
              "roughness": (9, 24), "network": (8, 22), "heterogeneity": (7, 18)}
    low, high = ranges[label]
    return {"angle_degrees": float(rng.uniform(0, 180)),
            "dispersion_degrees": float(rng.uniform(0, 24) if label == "orientation" else 0),
            "scale_um": float(rng.uniform(low, high)),
            "correlation_length_um": float(rng.uniform(low, high)),
            "anisotropy_ratio": float(rng.uniform(1.2, 3.2))}


def _transform(image: np.ndarray, rng: np.random.Generator, split: str) -> np.ndarray:
    values = np.asarray(image, dtype=float)
    if split == "train":
        values = ndimage.shift(values, shift=tuple(rng.uniform(-3, 3, 2)), order=1, mode="reflect")
        values = _gamma(values, float(rng.uniform(.85, 1.18)))
        values = _illumination(values, float(rng.uniform(-.15, .15)), float(rng.uniform(0, 2 * np.pi)))
        values = _shot_noise(values, float(rng.uniform(90, 180)), rng)
    else:
        values = ndimage.rotate(values, float(rng.uniform(25, 155)), reshape=False, order=1, mode="reflect")
        values = ndimage.gaussian_filter(values, sigma=tuple(rng.uniform((.7, 1.6), (1.5, 2.8))))
        factors = tuple(rng.uniform(.68, 1.28, 2))
        values = _center_crop_or_pad(ndimage.zoom(values, factors, order=1, mode="reflect"), (104, 104))
        values = ndimage.shift(values, shift=tuple(rng.uniform(-11, 11, 2)), order=1, mode="reflect")
        values = _gamma(values, float(rng.uniform(.55, 1.75)))
        values = _illumination(values, float(rng.uniform(-.45, .45)), float(rng.uniform(0, 2 * np.pi)))
        values = _shot_noise(values, float(rng.uniform(24, 70)), rng)
    return _standardize(values)


def generate_dataset(target: Path) -> Path:
    rng = np.random.default_rng(308260)
    images, bases, labels, splits, case_ids, parameters = [], [], [], [], [], []
    for split in ("train", "test"):
        for label in CLASSES:
            for index in range(50):
                seed = int(rng.integers(1, 2**31 - 1)); params = _parameters(label, rng)
                phantom = generate_phantom(label, shape=(104, 104), spacing_um=(1, 1), seed=seed, **params)
                bases.append(_standardize(phantom.image)); images.append(_transform(phantom.image, rng, split))
                labels.append(label); splits.append(split); case_ids.append(f"{split}-{label}-{index:02d}")
                parameters.append(json.dumps({"seed": seed, **params}, sort_keys=True))
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target, images=np.stack(images), base_images=np.stack(bases), labels=np.asarray(labels),
                        splits=np.asarray(splits), case_ids=np.asarray(case_ids), parameters=np.asarray(parameters))
    return target


def _features(image: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    raw = response_curve_blocks(image, None)
    geometry = analyze_response_geometry(image, spacing_um=(1, 1), mask=None, scales_um=(2, 4, 8, 16),
                                         separations_um=(1, 2, 4, 8, 16, 24))
    canonical = canonical_response_blocks(geometry)
    conventional = conventional_vector(image, None)
    return conventional, raw, canonical


def _join(blocks: dict[str, np.ndarray], omitted: str | None = None) -> np.ndarray:
    return np.concatenate([blocks[name] for name in sorted(blocks) if name != omitted])


def _summaries(blocks: dict[str, np.ndarray]) -> np.ndarray:
    values = []
    for name in sorted(blocks):
        block = blocks[name]
        values.extend((float(block.mean()), float(block.std()), float(block.min()), float(block.max())))
    return np.asarray(values)


def _fit_result(name: str, x: np.ndarray, labels: np.ndarray, splits: np.ndarray) -> dict:
    train, test = splits == "train", splits == "test"
    model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
    model.fit(x[train], labels[train]); prediction = model.predict(x[test]); truth = labels[test]
    return {"representation": name, "balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
            "per_class_recall": {label: float(value) for label, value in zip(CLASSES, recall_score(truth, prediction, labels=CLASSES, average=None), strict=True)},
            "truth": truth.tolist(), "predictions": prediction.tolist()}


def run_internal(dataset: Path, output: Path) -> dict:
    bundle = np.load(dataset, allow_pickle=False)
    images, bases, labels, splits = bundle["images"], bundle["base_images"], bundle["labels"], bundle["splits"]
    transformed = [_features(image) for image in images]
    base = [_features(image) for image in bases]
    matrices = {"conventional_scalar": np.stack([item[0] for item in transformed]),
                "raw_response_geometry": np.stack([_join(item[1]) for item in transformed]),
                "canonical_response_geometry": np.stack([_join(item[2]) for item in transformed]),
                "matched_collapsed_summaries": np.stack([_summaries(item[1]) for item in transformed])}
    for module in MODULES:
        matrices[f"canonical_without_{module}"] = np.stack([_join(item[2], module) for item in transformed])
    results = [_fit_result(name, values, labels, splits) for name, values in matrices.items()]

    train, test = splits == "train", splits == "test"
    distances = {}
    for name, index, block_index in (("raw", 1, 1), ("canonical", 2, 2)):
        train_matrix = np.stack([_join(item[block_index]) for item in transformed])[train]
        scaler = StandardScaler().fit(train_matrix)
        changed = scaler.transform(np.stack([_join(item[block_index]) for item in transformed])[test])
        unchanged = scaler.transform(np.stack([_join(item[block_index]) for item in base])[test])
        distances[name] = (np.linalg.norm(changed - unchanged, axis=1) / np.sqrt(changed.shape[1])).tolist()
    payload = {"protocol_version": "nostos-canonical-confirmation/3.0-internal",
               "protocol_sha256": PROTOCOL_SHA256, "dataset_sha256": _sha256(dataset),
               "design": "600 balanced analytic images; new compound optical and sampling shifts; fixed untuned linear SVM",
               "results": results, "standardized_same_construct_distances": distances}
    output.mkdir(parents=True, exist_ok=True)
    (output / "internal_results.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def _interval(truth: np.ndarray, first: np.ndarray, second: np.ndarray | None = None) -> list[float]:
    rng = np.random.default_rng(38260); groups = [np.flatnonzero(truth == label) for label in CLASSES]
    values = np.empty(10000)
    for draw in range(len(values)):
        selected = np.concatenate([group[rng.integers(0, len(group), len(group))] for group in groups])
        correct = (first[selected] == truth[selected]).astype(float)
        values[draw] = correct.mean() if second is None else (correct - (second[selected] == truth[selected]).astype(float)).mean()
    return [float(value) for value in np.quantile(values, (.025, .975))]


def finalize(internal_path: Path, kymatio_path: Path, pyradiomics_path: Path, output: Path) -> dict:
    internal = json.loads(internal_path.read_text(encoding="utf-8")); kymatio = json.loads(kymatio_path.read_text(encoding="utf-8")); pyradiomics = json.loads(pyradiomics_path.read_text(encoding="utf-8"))
    results = {item["representation"]: item for item in internal["results"]}
    truth = np.asarray(results["canonical_response_geometry"]["truth"])
    predictions = {name: np.asarray(item["predictions"]) for name, item in results.items()}
    predictions["kymatio"] = np.asarray(kymatio["predictions"]); predictions["pyradiomics"] = np.asarray(pyradiomics["synthetic_benchmark"]["predictions"])
    canonical = predictions["canonical_response_geometry"]
    intervals = {"canonical_balanced_accuracy": _interval(truth, canonical)}
    for comparator in ("raw_response_geometry", "matched_collapsed_summaries", "pyradiomics", "kymatio"):
        intervals[f"canonical_minus_{comparator}"] = _interval(truth, canonical, predictions[comparator])
    full = results["canonical_response_geometry"]["balanced_accuracy"]
    ablations = {module: results[f"canonical_without_{module}"]["balanced_accuracy"] - full for module in MODULES}
    raw_distance = float(np.median(internal["standardized_same_construct_distances"]["raw"])); canonical_distance = float(np.median(internal["standardized_same_construct_distances"]["canonical"])); ratio = canonical_distance / raw_distance
    gates = {"canonical_ci_lower_gt_0.80": intervals["canonical_balanced_accuracy"][0] > .80,
             "canonical_above_raw_ci_lower_gt_0": intervals["canonical_minus_raw_response_geometry"][0] > 0,
             "noninferior_to_collapsed_margin_0.03": intervals["canonical_minus_matched_collapsed_summaries"][0] > -.03,
             "noninferior_to_pyradiomics_margin_0.03": intervals["canonical_minus_pyradiomics"][0] > -.03,
             "noninferior_to_kymatio_margin_0.03": intervals["canonical_minus_kymatio"][0] > -.03,
             "at_least_two_ablation_drops_ge_0.03": sum(change <= -.03 for change in ablations.values()) >= 2,
             "canonical_distance_at_least_25pct_lower": ratio <= .75}
    payload = {"protocol_version": "nostos-canonical-confirmation/3.0", "protocol_sha256": PROTOCOL_SHA256,
               "dataset_sha256": internal["dataset_sha256"], "status": "pass" if all(gates.values()) else "fail",
               "internal_results": internal["results"], "external_comparators": {"kymatio": kymatio, "pyradiomics": pyradiomics},
               "bootstrap_intervals": intervals, "ablation_changes": ablations,
               "same_construct_distance": {"raw_median": raw_distance, "canonical_median": canonical_distance, "canonical_to_raw_ratio": ratio},
               "success_gates": gates, "scope": "Analytic acquisition-shift confirmation; not biological or clinical validation."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "canonical_confirmation_v3.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
