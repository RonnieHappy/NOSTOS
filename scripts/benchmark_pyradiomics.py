"""Run PyRadiomics IBSI subset conformance and frozen synthetic comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import radiomics
import SimpleITK as sitk
from radiomics import featureextractor
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


IBSI_FIRST_ORDER = {
    "10Percentile": 1.00,
    "90Percentile": 4.00,
    "Energy": 567.0,
    "InterquartileRange": 3.00,
    "Kurtosis": -0.355,  # IBSI excess kurtosis; PyRadiomics reports kurtosis.
    "Maximum": 6.00,
    "MeanAbsoluteDeviation": 1.55,
    "Mean": 2.15,
    "Median": 1.00,
    "Minimum": 1.00,
    "Range": 5.00,
    "RootMeanSquared": 2.77,
    "Skewness": 1.08,
    "Variance": 3.05,
}


def _three_significant(value: float) -> float:
    return float(f"{value:.3g}")


def _ibsi_conformance(image: Path, mask: Path) -> dict:
    extractor = featureextractor.RadiomicsFeatureExtractor()
    extractor.disableAllFeatures()
    extractor.enableFeatureClassByName("firstorder")
    raw = extractor.execute(str(image), str(mask))
    rows = []
    for feature, expected in IBSI_FIRST_ORDER.items():
        observed = float(raw[f"original_firstorder_{feature}"])
        if feature == "Kurtosis":
            observed -= 3.0
        passed = _three_significant(observed) == _three_significant(expected)
        rows.append({"feature": feature, "expected": expected, "observed": observed,
                     "comparison": "three_significant_digits", "passed": passed})
    return {"scope": "IBSI digital phantom, 14 first-order features",
            "passed": sum(row["passed"] for row in rows), "total": len(rows),
            "status": "pass" if all(row["passed"] for row in rows) else "fail", "features": rows}


def _radiomics_vector(extractor, image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    itk_image = sitk.GetImageFromArray(image.astype(np.float32))
    itk_mask = sitk.GetImageFromArray(np.ones_like(image, dtype=np.uint8))
    result = extractor.execute(itk_image, itk_mask)
    names = sorted(key for key in result if key.startswith("original_"))
    return np.asarray([float(result[key]) for key in names]), names


def _synthetic_benchmark(dataset: Path) -> dict:
    bundle = np.load(dataset, allow_pickle=False)
    images, labels, splits = bundle["images"], bundle["labels"], bundle["splits"]
    extractor = featureextractor.RadiomicsFeatureExtractor(binCount=16)
    extractor.disableAllFeatures()
    for feature_class in ("firstorder", "glcm", "glrlm", "glszm", "gldm", "ngtdm"):
        extractor.enableFeatureClassByName(feature_class)
    vectors, names = [], None
    for image in images:
        vector, current_names = _radiomics_vector(extractor, image)
        if names is not None and names != current_names:
            raise RuntimeError("PyRadiomics feature order changed within the frozen dataset.")
        names = current_names
        vectors.append(vector)
    x = np.stack(vectors)
    train, test = splits == "train", splits == "test"
    model = make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0))
    model.fit(x[train], labels[train])
    prediction = model.predict(x[test])
    return {
        "feature_count": int(x.shape[1]),
        "feature_classes": ["firstorder", "glcm", "glrlm", "glszm", "gldm", "ngtdm"],
        "discretization": "fixed bin count 16; comparator setting, not asserted IBSI-equivalent",
        "classifier": "StandardScaler + linear SVC(C=1.0)",
        "balanced_accuracy": float(balanced_accuracy_score(labels[test], prediction)),
        "truth": labels[test].tolist(), "predictions": prediction.tolist(),
        "feature_names": names,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--ibsi-image", type=Path, required=True)
    parser.add_argument("--ibsi-mask", type=Path, required=True)
    parser.add_argument("--ibsi-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = {
        "protocol_version": "nostos-pyradiomics-comparator/1.0",
        "implementation": "PyRadiomics",
        "pyradiomics_version": radiomics.__version__,
        "ibsi_data_commit": args.ibsi_commit,
        "ibsi_conformance": _ibsi_conformance(args.ibsi_image, args.ibsi_mask),
        "synthetic_benchmark": _synthetic_benchmark(args.dataset),
    }
    payload["status"] = "pass" if payload["ibsi_conformance"]["status"] == "pass" else "fail"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "pyradiomics_version": radiomics.__version__,
                      "ibsi": payload["ibsi_conformance"],
                      "balanced_accuracy": payload["synthetic_benchmark"]["balanced_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
