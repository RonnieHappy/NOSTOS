"""Participant-level validation of frozen response modules in public OA histology."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _bh_adjust(p_values: np.ndarray) -> np.ndarray:
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = np.minimum.accumulate((ranked * len(ranked) / np.arange(1, len(ranked) + 1))[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def _bootstrap_spearman(x: np.ndarray, y: np.ndarray, seed: int, draws: int = 2000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(draws):
        index = rng.integers(0, len(x), len(x))
        if np.ptp(x[index]) == 0 or np.ptp(y[index]) == 0:
            continue
        ranked_x = rankdata(x[index])
        ranked_y = rankdata(y[index])
        centered_x = ranked_x - ranked_x.mean()
        centered_y = ranked_y - ranked_y.mean()
        estimates.append(float(np.dot(centered_x, centered_y) / np.sqrt(np.dot(centered_x, centered_x) * np.dot(centered_y, centered_y))))
    return float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))


def _feature_families(frame: pd.DataFrame) -> dict[str, list[str]]:
    medians = [name for name in frame if name.endswith("_median")]
    fft = [name for name in medians if name.startswith(("anisotropy_", "angular_entropy_", "spectral_slope_", "characteristic_frequency_"))]
    tensor = [name for name in medians if name.startswith("tensor_")]
    hessian = [name for name in medians if name.startswith("hessian_")]
    spatial = [name for name in medians if name.startswith("variogram_")]
    conventional = [name for name in medians if name.startswith("glcm_")] + ["cartilage_fraction", "bone_fraction"]
    full = sorted(set(fft + tensor + hessian + spatial))
    return {
        "conventional_texture": conventional,
        "fft": fft,
        "nostos_response_geometry": full,
        "nostos_without_tensor": [name for name in full if name not in tensor],
        "nostos_without_hessian": [name for name in full if name not in hessian],
        "nostos_without_spatial": [name for name in full if name not in spatial],
    }


def _nested_repeated_cv(x: np.ndarray, y: np.ndarray, seed: int) -> list[dict[str, float]]:
    results = []
    for repeat in range(10):
        outer = KFold(n_splits=5, shuffle=True, random_state=seed + repeat)
        prediction = np.full(len(y), np.nan)
        for train, test in outer.split(x):
            inner = KFold(n_splits=5, shuffle=True, random_state=seed + 100 + repeat)
            model = make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                RidgeCV(alphas=np.logspace(-3, 4, 30), cv=inner),
            )
            model.fit(x[train], y[train])
            prediction[test] = model.predict(x[test])
        results.append({"repeat": repeat, "r2": float(r2_score(y, prediction)), "mae": float(mean_absolute_error(y, prediction))})
    return results


def validate_cartilage_response_geometry(medial_path: Path, lateral_path: Path, raw_scores_path: Path, output: Path) -> dict:
    features_by_site = {"Medial": pd.read_csv(medial_path, dtype={"participant_id": str}), "Lateral": pd.read_csv(lateral_path, dtype={"participant_id": str})}
    raw = pd.read_csv(raw_scores_path, dtype={"participant_id": str})
    for column in ("meanhhgsscore", "meanoarsiscore", "plmscore"):
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    outcomes = raw.groupby(["participant_id", "site"], as_index=False)[["meanhhgsscore", "meanoarsiscore", "plmscore"]].mean()
    association_rows = []
    prediction_results = []
    processing = {}
    for site, feature_frame in features_by_site.items():
        frame = feature_frame[feature_frame["feature_success"].fillna(False)].merge(outcomes[outcomes["site"] == site], on=["participant_id", "site"], how="inner")
        processing[site] = {"available": len(feature_frame), "successful_with_outcomes": len(frame)}
        families = _feature_families(frame)
        response_features = families["nostos_response_geometry"]
        site_outcomes = ["meanhhgsscore", "meanoarsiscore"] + (["plmscore"] if site == "Medial" else [])
        for outcome_index, outcome in enumerate(site_outcomes):
            for feature_index, feature in enumerate(response_features):
                selected = frame[[feature, outcome]].dropna()
                if len(selected) < 20 or selected[feature].nunique() < 2 or selected[outcome].nunique() < 2:
                    continue
                rho, p_value = spearmanr(selected[feature], selected[outcome])
                low, high = _bootstrap_spearman(selected[feature].to_numpy(), selected[outcome].to_numpy(), seed=10000 + outcome_index * 1000 + feature_index)
                association_rows.append({"site": site, "outcome": outcome, "feature": feature, "n": len(selected), "spearman_rho": float(rho), "ci95_low": low, "ci95_high": high, "p_value": float(p_value)})
            selected_outcome = frame[outcome].notna()
            y = frame.loc[selected_outcome, outcome].to_numpy(float)
            for family_index, (family, columns) in enumerate(families.items()):
                x = frame.loc[selected_outcome, columns].to_numpy(float)
                repeats = _nested_repeated_cv(x, y, seed=30000 + outcome_index * 1000 + family_index * 100 + (0 if site == "Medial" else 50))
                prediction_results.append({"site": site, "outcome": outcome, "family": family, "n": len(y), "mean_r2": float(np.mean([item["r2"] for item in repeats])), "sd_r2": float(np.std([item["r2"] for item in repeats], ddof=1)), "mean_mae": float(np.mean([item["mae"] for item in repeats])), "sd_mae": float(np.std([item["mae"] for item in repeats], ddof=1)), "repeats": repeats})
    associations = pd.DataFrame(association_rows)
    if not associations.empty:
        associations["fdr_q"] = associations.groupby(["site", "outcome"])["p_value"].transform(lambda values: _bh_adjust(values.to_numpy()))
    output.mkdir(parents=True, exist_ok=True)
    associations.to_csv(output / "cartilage_response_associations.csv", index=False)
    pd.DataFrame([{key: value for key, value in item.items() if key != "repeats"} for item in prediction_results]).to_csv(output / "cartilage_response_prediction.csv", index=False)
    payload = {
        "protocol_version": "nostos-external-cartilage/1.0",
        "scope": "repository-derived public histology with unreviewed stain-aware cartilage proposals",
        "processing": processing,
        "site_matching": {"Medial": ["HHGS", "OARSI", "PLM"], "Lateral": ["HHGS", "OARSI"], "note": "Lateral PLM is not treated as site-specific replication."},
        "prediction_results": prediction_results,
        "association_rows": len(associations),
        "validity": {"status": "exploratory_weak_mask", "reason": "The ROI proposals remain unvalidated and cannot support definitive biological attribution."},
    }
    (output / "external_cartilage_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
