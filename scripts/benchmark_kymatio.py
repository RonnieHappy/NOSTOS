"""Run official Kymatio on NOSTOS's frozen synthetic comparator split."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

import numpy as np
from kymatio.numpy import Scattering2D
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = np.load(args.dataset, allow_pickle=False)
    images, labels, splits = bundle["images"].astype(np.float32), bundle["labels"], bundle["splits"]
    scattering = Scattering2D(J=3, shape=tuple(images.shape[1:]), L=8, max_order=2)
    vectors = []
    for image in images:
        normalized = (image - image.mean()) / max(float(image.std()), np.finfo(np.float32).eps)
        vectors.append(scattering(normalized).mean(axis=(-2, -1)))
    x = np.stack(vectors)
    train, test = splits == "train", splits == "test"
    model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
    model.fit(x[train], labels[train])
    prediction = model.predict(x[test])
    payload = {
        "protocol_version": "nostos-kymatio-comparator/1.0",
        "implementation": "kymatio.numpy.Scattering2D",
        "kymatio_version": importlib.metadata.version("kymatio"),
        "configuration": {"J": 3, "L": 8, "max_order": 2, "aggregation": "spatial_mean"},
        "preprocessing": "center crop/pad to 192x192; per-image z normalization",
        "classifier": "StandardScaler + linear SVC(C=1.0)",
        "balanced_accuracy": float(balanced_accuracy_score(labels[test], prediction)),
        "truth": labels[test].tolist(),
        "predictions": prediction.tolist(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
