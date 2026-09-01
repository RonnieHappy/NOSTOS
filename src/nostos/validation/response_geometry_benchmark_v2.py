"""Prospectively frozen, distribution-shifted response-geometry benchmark."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .comparators import conventional_vector, response_curve_blocks
from .phantoms import generate_phantom
from .perturbations import Perturbation, _center_crop_or_pad, apply_perturbation


PROTOCOL_SHA256 = "c86f7c9aaa5334b3e5eda61e76da89990edd381a776735a4470140efa4ae9408"
CLASSES = ("orientation", "spectral_scale", "blob", "roughness", "network", "heterogeneity")
MODULES = ("spectral", "tensor", "hessian", "spatial")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parameters(label: str, rng: np.random.Generator, split: str) -> dict[str, float]:
    scale_ranges = {
        "orientation": (16, 28), "spectral_scale": (6, 13), "blob": (10, 30),
        "roughness": (9, 24), "network": (8, 22), "heterogeneity": (7, 18),
    }
    low, high = scale_ranges[label]
    if split == "test":
        low *= .9
        high *= 1.1
    return {
        "angle_degrees": float(rng.uniform(0, 180)),
        "dispersion_degrees": float(rng.uniform(0, 24) if label == "orientation" else 0),
        "scale_um": float(rng.uniform(low, high)),
        "correlation_length_um": float(rng.uniform(low, high)),
        "anisotropy_ratio": float(rng.uniform(1.2, 3.2)),
    }


def _perturb(image_phantom, rng: np.random.Generator, split: str, seed: int) -> np.ndarray:
    phantom = image_phantom
    if split == "train":
        sequence = (
            Perturbation("contrast", float(rng.uniform(.75, 1.25)), seed),
            Perturbation("blur", float(rng.uniform(.15, .75)), seed + 1),
            Perturbation("noise", float(rng.uniform(.015, .08)), seed + 2),
        )
    else:
        sequence = (
            Perturbation("rotation", float(rng.uniform(13, 77)), seed),
            Perturbation("contrast", float(rng.uniform(.55, 1.55)), seed + 1),
            Perturbation("blur", float(rng.uniform(.9, 1.7)), seed + 2),
            Perturbation("partial_volume", float(rng.uniform(.58, .82)), seed + 3),
            Perturbation("noise", float(rng.uniform(.10, .20)), seed + 4),
        )
    for perturbation in sequence:
        phantom = apply_perturbation(phantom, perturbation)
    image = _center_crop_or_pad(phantom.image, (96, 96)).astype(np.float32)
    image = (image - image.mean()) / max(float(image.std()), np.finfo(np.float32).eps)
    return np.clip(image, -5, 5).astype(np.float32)


def generate_dataset(target: Path) -> Path:
    master = np.random.default_rng(260826)
    images, labels, splits, case_ids, parameters = [], [], [], [], []
    for split in ("train", "test"):
        for label in CLASSES:
            for index in range(40):
                seed = int(master.integers(1, 2**31 - 1))
                params = _parameters(label, master, split)
                phantom = generate_phantom(label, shape=(96, 96), spacing_um=(1, 1), seed=seed, **params)
                images.append(_perturb(phantom, master, split, seed))
                labels.append(label); splits.append(split)
                case_ids.append(f"{split}-{label}-{index:02d}")
                parameters.append(json.dumps({"seed": seed, **params}, sort_keys=True))
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target, images=np.stack(images), labels=np.asarray(labels), splits=np.asarray(splits),
                        case_ids=np.asarray(case_ids), parameters=np.asarray(parameters))
    return target


def _vector(blocks: dict[str, np.ndarray], mode: str, omitted: str | None = None) -> np.ndarray:
    retained = [blocks[name] for name in sorted(blocks) if name != omitted]
    if mode == "curves":
        return np.concatenate(retained)
    values = []
    for block in retained:
        values.extend((float(block.mean()), float(block.std()), float(block.min()), float(block.max())))
    return np.asarray(values)


def _fit_predict(x: np.ndarray, labels: np.ndarray, splits: np.ndarray) -> np.ndarray:
    train, test = splits == "train", splits == "test"
    model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
    model.fit(x[train], labels[train])
    return model.predict(x[test])


def _result(name: str, truth: np.ndarray, prediction: np.ndarray) -> dict:
    return {
        "representation": name,
        "balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
        "per_class_recall": {label: float(value) for label, value in zip(CLASSES, recall_score(truth, prediction, labels=CLASSES, average=None), strict=True)},
        "predictions": prediction.tolist(), "truth": truth.tolist(),
    }


def run_internal(dataset: Path, output: Path) -> dict:
    bundle = np.load(dataset, allow_pickle=False)
    images, labels, splits = bundle["images"], bundle["labels"], bundle["splits"]
    prepared = [(conventional_vector(image, None), response_curve_blocks(image, None)) for image in images]
    representations = {
        "conventional_scalar": np.stack([item[0] for item in prepared]),
        "matched_collapsed_summaries": np.stack([_vector(item[1], "summaries") for item in prepared]),
        "nostos_response_geometry": np.stack([_vector(item[1], "curves") for item in prepared]),
    }
    for module in MODULES:
        representations[f"nostos_without_{module}"] = np.stack([_vector(item[1], "curves", module) for item in prepared])
    truth = labels[splits == "test"]
    results = [_result(name, truth, _fit_predict(values, labels, splits)) for name, values in representations.items()]
    payload = {
        "protocol_version": "nostos-response-geometry-benchmark/2.0-internal",
        "protocol_sha256": PROTOCOL_SHA256, "dataset_sha256": _sha256(dataset),
        "design": "480 balanced analytic images; disjoint compound acquisition shifts; no masks; fixed linear SVM",
        "results": results,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "internal_results.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def _stratified_interval(truth: np.ndarray, first: np.ndarray, second: np.ndarray | None = None) -> list[float]:
    rng = np.random.default_rng(82626)
    groups = [np.flatnonzero(truth == label) for label in CLASSES]
    values = np.empty(10000)
    for draw in range(10000):
        selected = np.concatenate([group[rng.integers(0, len(group), len(group))] for group in groups])
        first_correct = (first[selected] == truth[selected]).astype(float)
        values[draw] = first_correct.mean() if second is None else (first_correct - (second[selected] == truth[selected]).astype(float)).mean()
    return [float(value) for value in np.quantile(values, (.025, .975))]


def finalize(internal_path: Path, kymatio_path: Path, pyradiomics_path: Path, output: Path) -> dict:
    internal = json.loads(internal_path.read_text(encoding="utf-8"))
    kymatio = json.loads(kymatio_path.read_text(encoding="utf-8"))
    pyradiomics = json.loads(pyradiomics_path.read_text(encoding="utf-8"))
    results = {item["representation"]: item for item in internal["results"]}
    truth = np.asarray(results["nostos_response_geometry"]["truth"])
    predictions = {name: np.asarray(item["predictions"]) for name, item in results.items()}
    predictions["kymatio"] = np.asarray(kymatio["predictions"])
    predictions["pyradiomics"] = np.asarray(pyradiomics["synthetic_benchmark"]["predictions"])
    nostos = predictions["nostos_response_geometry"]
    intervals = {"nostos_balanced_accuracy": _stratified_interval(truth, nostos)}
    for comparator in ("matched_collapsed_summaries", "conventional_scalar", "pyradiomics", "kymatio"):
        intervals[f"nostos_minus_{comparator}"] = _stratified_interval(truth, nostos, predictions[comparator])
    full_accuracy = results["nostos_response_geometry"]["balanced_accuracy"]
    ablation_changes = {module: results[f"nostos_without_{module}"]["balanced_accuracy"] - full_accuracy for module in MODULES}
    gates = {
        "nostos_ci_lower_gt_0.80": intervals["nostos_balanced_accuracy"][0] > .80,
        "curves_above_collapsed_ci_lower_gt_0": intervals["nostos_minus_matched_collapsed_summaries"][0] > 0,
        "noninferior_to_pyradiomics_margin_0.02": intervals["nostos_minus_pyradiomics"][0] > -.02,
        "noninferior_to_kymatio_margin_0.02": intervals["nostos_minus_kymatio"][0] > -.02,
        "at_least_two_ablation_drops_ge_0.03": sum(change <= -.03 for change in ablation_changes.values()) >= 2,
    }
    payload = {
        "protocol_version": "nostos-response-geometry-benchmark/2.0", "protocol_sha256": PROTOCOL_SHA256,
        "dataset_sha256": internal["dataset_sha256"], "status": "pass" if all(gates.values()) else "fail",
        "internal_results": internal["results"],
        "external_comparators": {"kymatio": kymatio, "pyradiomics": pyradiomics},
        "bootstrap_intervals": intervals, "ablation_changes": ablation_changes, "success_gates": gates,
        "scope": "Controlled synthetic distribution-shift evidence; not biological or clinical validation.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "response_geometry_benchmark_v2.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
