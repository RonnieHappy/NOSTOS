"""Training-only development audit for rotation-quotiented comparison geometry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import rotate
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from nostos.features.canonical_geometry import canonical_response_blocks
from nostos.features.universal import analyze_response_geometry
from nostos.validation.comparators import response_curve_blocks


ANGLES = (37, 59, 83)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _vectors(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    raw_blocks = response_curve_blocks(image, None)
    raw = np.concatenate([raw_blocks[name] for name in sorted(raw_blocks)])
    geometry = analyze_response_geometry(
        image, spacing_um=(1, 1), mask=None, scales_um=(2, 4, 8, 16),
        separations_um=(1, 2, 4, 8, 16, 24),
    )
    canonical_blocks = canonical_response_blocks(geometry)
    canonical = np.concatenate([canonical_blocks[name] for name in sorted(canonical_blocks)])
    return raw, canonical


def run_canonical_development(dataset: Path, output: Path) -> dict:
    bundle = np.load(dataset, allow_pickle=False)
    selected = bundle["splits"] == "train"
    images, labels, case_ids = bundle["images"][selected], bundle["labels"][selected], bundle["case_ids"][selected]
    base = [_vectors(image) for image in images]
    rotated = {angle: [_vectors(rotate(image, angle, reshape=False, order=1, mode="reflect")) for image in images] for angle in ANGLES}
    folds = tuple(StratifiedKFold(5, shuffle=True, random_state=826).split(images, labels))
    rows = []
    for angle in ANGLES:
        for name, index in (("raw", 0), ("canonical_rotation_quotient", 1)):
            fold_scores = []
            predictions = np.empty(len(labels), dtype=labels.dtype)
            for train, test in folds:
                x_train = np.stack([base[i][index] for i in train])
                x_test = np.stack([rotated[angle][i][index] for i in test])
                model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
                model.fit(x_train, labels[train])
                predictions[test] = model.predict(x_test)
                fold_scores.append(float(balanced_accuracy_score(labels[test], predictions[test])))
            rows.append({"angle_degrees": angle, "representation": name,
                         "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
                         "fold_balanced_accuracy": fold_scores, "predictions": predictions.tolist()})
    payload = {
        "protocol_version": "nostos-canonical-development/1.0",
        "dataset_sha256": _sha256(dataset),
        "scope": "Development only: v2 training split; v2 test split is not read.",
        "design": "Five stratified folds; train on unrotated images and evaluate held-out cases at fixed unseen rotations; no hyperparameter tuning.",
        "case_count": len(images), "case_ids_sha256": hashlib.sha256("\n".join(case_ids.tolist()).encode()).hexdigest(),
        "results": rows,
        "minimum_balanced_accuracy": {
            name: min(row["balanced_accuracy"] for row in rows if row["representation"] == name)
            for name in ("raw", "canonical_rotation_quotient")
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "canonical_development.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
