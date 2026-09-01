"""Development-only audit of label-free stability weighting on v3 training cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

from nostos.features.stability_weighting import apply_stability_weights, fit_stability_weights
from nostos.validation.canonical_confirmation_v3 import _features, _join, _transform


def run_stability_development(dataset: Path, output: Path) -> dict:
    bundle = np.load(dataset, allow_pickle=False); selected = bundle["splits"] == "train"
    bases, labels = bundle["base_images"][selected], bundle["labels"][selected]
    rng_a, rng_b = np.random.default_rng(44041), np.random.default_rng(44042)
    development_a = np.stack([_transform(image, rng_a, "test") for image in bases])
    development_b = np.stack([_transform(image, rng_b, "test") for image in bases])
    base_x = np.stack([_join(_features(image)[2]) for image in bases])
    first_x = np.stack([_join(_features(image)[2]) for image in development_a])
    second_x = np.stack([_join(_features(image)[2]) for image in development_b])
    predictions = {"unweighted_canonical": np.empty(len(labels), dtype=labels.dtype),
                   "stability_weighted_canonical": np.empty(len(labels), dtype=labels.dtype)}
    fold_rows = []
    for fold, (train, test) in enumerate(StratifiedKFold(5, shuffle=True, random_state=4404).split(bases, labels)):
        x_train = np.vstack([base_x[train], first_x[train]]); y_train = np.concatenate([labels[train], labels[train]])
        unweighted = make_pipeline(StandardScaler(), LinearSVC(C=1.0, dual="auto", max_iter=10000)).fit(x_train, y_train)
        predictions["unweighted_canonical"][test] = unweighted.predict(second_x[test])
        weights = fit_stability_weights(base_x[train], first_x[train])
        weighted_train = np.vstack([apply_stability_weights(base_x[train], weights), apply_stability_weights(first_x[train], weights)])
        weighted = LinearSVC(C=1.0, dual="auto", max_iter=10000).fit(weighted_train, y_train)
        predictions["stability_weighted_canonical"][test] = weighted.predict(apply_stability_weights(second_x[test], weights))
        fold_rows.append({"fold": fold, "effective_coordinates": weights.effective_coordinates,
                          "median_reliability": float(np.median(weights.reliability))})
    results = {name: {"balanced_accuracy": float(balanced_accuracy_score(labels, prediction)),
                      "predictions": prediction.tolist()} for name, prediction in predictions.items()}
    payload = {"protocol_version": "nostos-stability-weighting-development/1.0",
               "scope": "Development only: v3 training cases with two newly generated perturbation replicas; v3 test cases are not read.",
               "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
               "design": "Five stratified case folds; label-free coordinate reliability fitted within each training fold; fixed linear SVM.",
               "results": results, "fold_diagnostics": fold_rows}
    output.mkdir(parents=True, exist_ok=True)
    (output / "stability_weighting_development.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
