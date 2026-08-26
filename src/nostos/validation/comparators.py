"""Leakage-resistant synthetic comparison of representation strategies."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from nostos.features.universal import analyze_response_geometry

from .phantoms import generate_phantom
from .perturbations import Perturbation, _center_crop_or_pad, apply_perturbation


@dataclass(frozen=True)
class BenchmarkResult:
    representation: str
    balanced_accuracy: float
    predictions: tuple[str, ...]
    truth: tuple[str, ...]


def _ordered_responses(geometry) -> list[tuple[str, np.ndarray]]:
    return sorted(
        ((f"{response.module}.{response.measurement}", np.asarray(response.values, dtype=float)) for response in geometry.responses),
        key=lambda item: item[0],
    )


def response_curve_blocks(image: np.ndarray, mask: np.ndarray | None) -> dict[str, np.ndarray]:
    geometry = analyze_response_geometry(
        image,
        spacing_um=(1.0, 1.0),
        mask=mask,
        scales_um=(2.0, 4.0, 8.0, 16.0),
        thresholds_um=(0.0, 1.0, 2.0, 4.0, 8.0),
        separations_um=(1.0, 2.0, 4.0, 8.0, 16.0, 24.0),
    )
    blocks: dict[str, list[np.ndarray]] = {}
    for name, values in _ordered_responses(geometry):
        module = name.split(".", 1)[0]
        blocks.setdefault(module, []).append(values)
    return {module: np.concatenate(values) for module, values in blocks.items()}


def response_curve_vector(image: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    blocks = response_curve_blocks(image, mask)
    return np.concatenate([blocks[name] for name in sorted(blocks)])


def naive_summary_vector(image: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    geometry = analyze_response_geometry(
        image,
        spacing_um=(1.0, 1.0),
        mask=mask,
        scales_um=(2.0, 4.0, 8.0, 16.0),
        thresholds_um=(0.0, 1.0, 2.0, 4.0, 8.0),
        separations_um=(1.0, 2.0, 4.0, 8.0, 16.0, 24.0),
    )
    summaries = []
    for _, values in _ordered_responses(geometry):
        summaries.extend((float(np.mean(values)), float(np.std(values)), float(np.min(values)), float(np.max(values))))
    return np.asarray(summaries)


def conventional_vector(image: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    values = np.asarray(image, dtype=float)
    gy, gx = np.gradient(values)
    magnitude = np.hypot(gx, gy)
    selected = values if mask is None else values[np.asarray(mask, dtype=bool)]
    histogram, _ = np.histogram(selected, bins=16, range=(float(values.min()), float(values.max()) + 1e-12), density=True)
    return np.asarray([
        selected.mean(), selected.std(), np.percentile(selected, 10), np.median(selected), np.percentile(selected, 90),
        magnitude.mean(), magnitude.std(), np.mean(np.abs(gx)), np.mean(np.abs(gy)), *histogram,
    ], dtype=float)


def _dataset():
    classes = ("orientation", "blob", "network", "heterogeneity")
    training_perturbations = (Perturbation("noise", 0.03, 10), Perturbation("noise", 0.08, 11), Perturbation("blur", 0.5, 12), Perturbation("contrast", 0.75, 13))
    test_perturbations = (Perturbation("rotation", 23, 20), Perturbation("noise", 0.14, 21), Perturbation("blur", 1.2, 22), Perturbation("partial_volume", 0.65, 23))
    rows = []
    for label in classes:
        base = generate_phantom(label, seed=100 + classes.index(label))  # type: ignore[arg-type]
        for split, perturbations in (("train", training_perturbations), ("test", test_perturbations)):
            for perturbation in perturbations:
                sample = apply_perturbation(base, perturbation)
                # The comparison controls ROI availability: every construct
                # receives the same full-field eligible ROI, preventing mask
                # presence or coverage from leaking the class label.
                eligible_mask = np.ones_like(sample.image, dtype=bool)
                rows.append((split, label, sample.image, eligible_mask))
    return rows


def write_external_comparator_dataset(target: Path, shape: tuple[int, int] = (192, 192)) -> Path:
    """Export frozen train/test images for isolated upstream comparators."""
    rows = _dataset()
    images = np.stack([
        _center_crop_or_pad(np.asarray(image, dtype=np.float32), shape)
        for _, _, image, _ in rows
    ])
    labels = np.asarray([label for _, label, _, _ in rows])
    splits = np.asarray([split for split, _, _, _ in rows])
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target, images=images, labels=labels, splits=splits)
    return target


def benchmark_representations() -> tuple[BenchmarkResult, ...]:
    rows = _dataset()
    prepared = []
    for split, label, image, mask in rows:
        blocks = response_curve_blocks(image, mask)
        prepared.append((split, label, conventional_vector(image, mask), blocks))
    def vector_from_blocks(blocks, mode, omitted=None):
        retained = [blocks[name] for name in sorted(blocks) if name != omitted]
        if mode == "curves":
            return np.concatenate(retained)
        summary = []
        for values in retained:
            summary.extend((float(np.mean(values)), float(np.std(values)), float(np.min(values)), float(np.max(values))))
        return np.asarray(summary)
    extractors = {
        "conventional_scalar": lambda conventional, blocks: conventional,
        "naive_response_summaries": lambda conventional, blocks: vector_from_blocks(blocks, "summary"),
        "nostos_response_curves": lambda conventional, blocks: vector_from_blocks(blocks, "curves"),
    }
    results = []
    for name, extractor in extractors.items():
        train = [(extractor(conventional, blocks), label) for split, label, conventional, blocks in prepared if split == "train"]
        test = [(extractor(conventional, blocks), label) for split, label, conventional, blocks in prepared if split == "test"]
        x_train = np.stack([item[0] for item in train])
        y_train = np.asarray([item[1] for item in train])
        x_test = np.stack([item[0] for item in test])
        y_test = np.asarray([item[1] for item in test])
        model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
        model.fit(x_train, y_train)
        prediction = model.predict(x_test)
        results.append(BenchmarkResult(name, float(balanced_accuracy_score(y_test, prediction)), tuple(prediction), tuple(y_test)))
    for omitted in ("spectral", "tensor", "hessian", "geometry", "network", "spatial"):
        train = [(vector_from_blocks(blocks, "curves", omitted), label) for split, label, conventional, blocks in prepared if split == "train"]
        test = [(vector_from_blocks(blocks, "curves", omitted), label) for split, label, conventional, blocks in prepared if split == "test"]
        x_train = np.stack([item[0] for item in train])
        y_train = np.asarray([item[1] for item in train])
        x_test = np.stack([item[0] for item in test])
        y_test = np.asarray([item[1] for item in test])
        model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
        model.fit(x_train, y_train)
        prediction = model.predict(x_test)
        results.append(BenchmarkResult(f"nostos_without_{omitted}", float(balanced_accuracy_score(y_test, prediction)), tuple(prediction), tuple(y_test)))
    return tuple(results)


def write_benchmark_receipt(output: Path) -> dict:
    results = benchmark_representations()
    full = next(item for item in results if item.representation == "nostos_response_curves")
    conventional = next(item for item in results if item.representation == "conventional_scalar")
    naive = next(item for item in results if item.representation == "naive_response_summaries")
    ablations = [item for item in results if item.representation.startswith("nostos_without_")]
    payload = {
        "protocol_version": "nostos-representation-benchmark/1.0",
        "design": "frozen training perturbations and disjoint held-out perturbation types/magnitudes",
        "scope": "synthetic construct discrimination; not biological validation",
        "results": [asdict(item) for item in results],
        "contrasts": {
            "nostos_minus_conventional": full.balanced_accuracy - conventional.balanced_accuracy,
            "nostos_minus_naive_summaries": full.balanced_accuracy - naive.balanced_accuracy,
            "worst_ablation_change": min(item.balanced_accuracy - full.balanced_accuracy for item in ablations),
        },
        "interpretation": "The benchmark is descriptive at this sample size and cannot establish general superiority.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "representation_benchmark.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
