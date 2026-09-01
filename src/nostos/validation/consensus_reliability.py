"""Group-separated development and confirmation of estimator-consensus reliability."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nostos.features.response_modules import structure_tensor_response
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.selective_fft_confirmation import _wilson
from nostos.validation.selective_fft_development import self_perturbation_score
from nostos.validation.selective_shg_transfer import _cluster_interval, _index, _load


PROTOCOL_SHA256 = "9929a005e605118fa10f5cb4e6561fcafd0eec768d2f074e2b09bcb08c6774b8"
FEATURE_NAMES = (
    "synthetic_score", "angle_instability", "scale_instability", "low_anisotropy",
    "high_entropy", "low_snr", "undersampling", "fft_anisotropy", "fft_entropy",
    "log_snr", "log_wavelength", "tensor_orientation_1", "tensor_orientation_2",
    "tensor_orientation_4", "tensor_orientation_8", "tensor_coherence_1",
    "tensor_coherence_2", "tensor_coherence_4", "tensor_coherence_8",
    "fft_tensor_disagreement_1", "fft_tensor_disagreement_2",
    "fft_tensor_disagreement_4", "fft_tensor_disagreement_8", "tensor_interscale_spread",
)


def _partition(group: str) -> str:
    value = int.from_bytes(hashlib.sha256(group.encode("utf-8")).digest()[:8], "big") % 10
    return "development" if value <= 5 else "confirmation"


def _coordinates(image: np.ndarray) -> tuple[np.ndarray, dict]:
    score, diagnostics = self_perturbation_score(image, 1.0)
    measurement = diagnostics["measurement"]
    components = diagnostics["components"]
    tensor = structure_tensor_response(image, spacing_um=(1.0, 1.0), scales_um=(1.0, 2.0, 4.0, 8.0))
    disagreements = [
        axial_angular_error_degrees(measurement["orientation"], angle)
        for angle in tensor.orientation_degrees
    ]
    interscale = max(
        axial_angular_error_degrees(a, b)
        for i, a in enumerate(tensor.orientation_degrees)
        for b in tensor.orientation_degrees[i + 1:]
    )
    vector = np.asarray([
        score, components["angle_instability"], components["scale_instability"],
        components["low_anisotropy"], components["high_entropy"], components["low_snr"],
        components["undersampling"], measurement["anisotropy"], measurement["entropy"],
        np.log1p(measurement["snr"]), np.log1p(measurement["wavelength"]),
        *tensor.orientation_degrees, *tensor.coherency, *disagreements, interscale,
    ], dtype=float)
    return vector, {"self_perturbation": diagnostics, "tensor_orientations": tensor.orientation_degrees,
                    "tensor_coherencies": tensor.coherency, "fft_tensor_disagreements": disagreements,
                    "tensor_interscale_spread": float(interscale)}


def _choose_threshold(probability: np.ndarray, invalid: np.ndarray) -> dict | None:
    selected = None
    for threshold in np.unique(probability):
        accepted = probability <= threshold
        coverage = float(accepted.mean())
        if coverage < 0.30:
            continue
        risk = float(invalid[accepted].mean())
        if risk <= 0.10 and (selected is None or coverage > selected["coverage"]):
            selected = {"threshold": float(threshold), "coverage": coverage, "risk": risk,
                        "accepted": int(accepted.sum())}
    return selected


def run_development_confirmation(dataset_root: Path, output: Path) -> dict:
    train_root = dataset_root / "final_train_test" / "train"
    identifiers = _index(train_root)
    rows = []
    vectors = []
    for number in sorted(identifiers, key=int):
        image = _load(train_root / "images" / f"{number}.png")
        label = _load(train_root / "labels" / f"{number}.png", nearest=True)
        vector, diagnostics = _coordinates(image)
        reference = extract_spatial_fft(label.astype(np.float32), pixel_size_um=1.0)
        measurement = diagnostics["self_perturbation"]["measurement"]
        disagreement = axial_angular_error_degrees(measurement["orientation"], reference.orientation_degrees)
        group = identifiers[number].rsplit("_", 1)[0]
        eligible = float(label.mean()) >= 0.001 and reference.anisotropy >= 0.15
        rows.append({
            "patch": int(number), "identifier": identifiers[number], "source_group": group,
            "partition": _partition(group), "reference_eligible": eligible,
            "label_coverage": float(label.mean()), "label_anisotropy": float(reference.anisotropy),
            "axial_disagreement_degrees": float(disagreement),
            "invalid": bool(disagreement > 10.0) if eligible else None,
            "legacy_accepted": not (measurement["snr"] < 3.0 or measurement["wavelength"] < 4.0),
            "diagnostics": diagnostics,
        })
        vectors.append(vector)
    x = np.stack(vectors)
    development_indices = [i for i, row in enumerate(rows) if row["partition"] == "development" and row["reference_eligible"]]
    confirmation_indices = [i for i, row in enumerate(rows) if row["partition"] == "confirmation" and row["reference_eligible"]]
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=7243211))
    y_development = np.asarray([rows[i]["invalid"] for i in development_indices], dtype=int)
    model.fit(x[development_indices], y_development)
    development_probability = model.predict_proba(x[development_indices])[:, 1]
    selection = _choose_threshold(development_probability, y_development)
    threshold = selection["threshold"] if selection else -1.0
    for index, probability in zip(development_indices, development_probability, strict=True):
        rows[index]["predicted_invalid_probability"] = float(probability)
        rows[index]["accepted"] = bool(probability <= threshold)
    confirmation_probability = model.predict_proba(x[confirmation_indices])[:, 1]
    for index, probability in zip(confirmation_indices, confirmation_probability, strict=True):
        rows[index]["predicted_invalid_probability"] = float(probability)
        rows[index]["accepted"] = bool(probability <= threshold)
    confirmation = [rows[i] for i in confirmation_indices]
    accepted = [row for row in confirmation if row["accepted"]]
    legacy = [row for row in confirmation if row["legacy_accepted"]]
    risk = float(np.mean([row["invalid"] for row in accepted])) if accepted else 1.0
    risk_all = float(np.mean([row["invalid"] for row in confirmation])) if confirmation else 1.0
    legacy_coverage = len(legacy) / len(confirmation) if confirmation else 0.0
    legacy_risk = float(np.mean([row["invalid"] for row in legacy])) if legacy else 1.0
    coverage = len(accepted) / len(confirmation) if confirmation else 0.0
    auc = float(roc_auc_score([row["invalid"] for row in confirmation], confirmation_probability))
    cluster_interval = _cluster_interval(confirmation, seed=7243212)
    median_error = float(np.median([row["axial_disagreement_degrees"] for row in accepted])) if accepted else None
    groups = len({row["source_group"] for row in confirmation})
    gates = {
        "eligible_patches_ge_200_and_groups_ge_100": len(confirmation) >= 200 and groups >= 100,
        "selective_coverage_ge_0.40": coverage >= 0.40,
        "cluster_risk_upper_le_0.15": cluster_interval[1] <= 0.15,
        "accepted_median_disagreement_le_5_degrees": median_error is not None and median_error <= 5.0,
        "invalid_detection_auc_ge_0.75": auc >= 0.75,
        "lower_risk_than_unselected_and_legacy_or_legacy_low_coverage": risk < risk_all and (risk < legacy_risk or legacy_coverage < coverage / 2),
    }
    logistic = model.named_steps["logisticregression"]
    scaler = model.named_steps["standardscaler"]
    payload = {
        "protocol_version": "nostos-consensus-reliability/1.0", "protocol_sha256": PROTOCOL_SHA256,
        "status": "pass" if selection is not None and all(gates.values()) else "fail",
        "development": {"eligible": len(development_indices), "source_groups": len({rows[i]["source_group"] for i in development_indices}),
                        "invalid_prevalence": float(y_development.mean()), "selection": selection,
                        "auc": float(roc_auc_score(y_development, development_probability))},
        "frozen_model": {"feature_names": FEATURE_NAMES, "scaler_mean": scaler.mean_.tolist(),
                         "scaler_scale": scaler.scale_.tolist(), "coefficients": logistic.coef_[0].tolist(),
                         "intercept": float(logistic.intercept_[0]), "threshold": threshold},
        "confirmation": {"eligible": len(confirmation), "source_groups": groups, "accepted": len(accepted),
                         "coverage": coverage, "selective_risk": risk,
                         "selective_risk_wilson95": _wilson(sum(row["invalid"] for row in accepted), len(accepted)),
                         "selective_risk_cluster_bootstrap95": cluster_interval, "risk_all": risk_all,
                         "invalid_detection_auc": auc, "legacy_coverage": legacy_coverage,
                         "legacy_risk": legacy_risk, "accepted_median_disagreement_degrees": median_error},
        "success_gates": gates,
        "scope": "Same-archive group-separated SHG reliability development and confirmation; not independent acquisition.",
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "consensus_reliability.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload

