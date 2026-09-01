"""Site-matched inference for cartilage boundary and conventional-feature ablations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nostos.validation.external_cartilage import _bh_adjust, _bootstrap_spearman


VARIANTS = (
    "baseline_072", "strict_095", "eroded_100um", "eroded_250um",
    "surface_excluded_100um", "surface_excluded_250um", "void_excluded_100um",
    "internal_hole_excluded_100um", "extreme_dark_object_excluded_25um",
)
GEOMETRY_OD = (
    "cartilage_area_mm2", "cartilage_perimeter_area_ratio_per_mm", "void_fraction_near_cartilage",
    "od_red_median", "od_green_median", "od_blue_median", "luminance_median", "luminance_iqr",
)


def _paired_delta_bootstrap(frame: pd.DataFrame, first: str, second: str, outcome: str, seed: int, draws: int = 2000) -> tuple[float, float, float]:
    selected = frame[[first, second, outcome]].dropna()
    observed = float(spearmanr(selected[first], selected[outcome]).statistic - spearmanr(selected[second], selected[outcome]).statistic)
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(draws):
        index = rng.integers(0, len(selected), len(selected))
        sample = selected.iloc[index]
        rho_first = spearmanr(sample[first], sample[outcome]).statistic
        rho_second = spearmanr(sample[second], sample[outcome]).statistic
        if np.isfinite(rho_first) and np.isfinite(rho_second):
            estimates.append(float(rho_first - rho_second))
    return observed, float(np.quantile(estimates, .025)), float(np.quantile(estimates, .975))


def _paired_nested_predictions(frame: pd.DataFrame, outcome: str, families: dict[str, list[str]], seed: int) -> list[dict]:
    selected = frame[frame[outcome].notna()].reset_index(drop=True)
    y = selected[outcome].to_numpy(float)
    rows = []
    for repeat in range(10):
        outer = KFold(n_splits=5, shuffle=True, random_state=seed + repeat)
        predictions = {family: np.full(len(y), np.nan) for family in families}
        for train, test in outer.split(selected):
            inner = KFold(n_splits=5, shuffle=True, random_state=seed + 100 + repeat)
            for family, columns in families.items():
                model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                      RidgeCV(alphas=np.logspace(-3, 4, 30), cv=inner))
                model.fit(selected.loc[train, columns].to_numpy(float), y[train])
                predictions[family][test] = model.predict(selected.loc[test, columns].to_numpy(float))
        metrics = {family: {"r2": float(r2_score(y, prediction)), "mae": float(mean_absolute_error(y, prediction))}
                   for family, prediction in predictions.items()}
        for family, values in metrics.items():
            rows.append({"repeat": repeat, "family": family, **values})
    return rows


def analyze_cartilage_ablations(medial: Path, lateral: Path, scores: Path, output: Path) -> dict:
    raw = pd.read_csv(scores, dtype={"participant_id": str})
    raw["participant_id"] = raw["participant_id"].astype(str).str.removeprefix("P").str.zfill(3)
    for column in ("meanhhgsscore", "meanoarsiscore", "plmscore"):
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    outcomes = raw.groupby(["participant_id", "site"], as_index=False)[["meanhhgsscore", "meanoarsiscore", "plmscore"]].mean()
    association_rows, contrast_rows, prediction_rows, availability = [], [], [], []
    site_frames = {"Medial": pd.read_csv(medial, dtype={"participant_id": str}), "Lateral": pd.read_csv(lateral, dtype={"participant_id": str})}
    for site_index, (site, features) in enumerate(site_frames.items()):
        features["participant_id"] = features["participant_id"].astype(str).str.removeprefix("P").str.zfill(3)
        frame = features[features["success"].fillna(False)].merge(outcomes[outcomes["site"] == site], on=["participant_id", "site"])
        for variant in VARIANTS:
            availability.append({"site": site, "variant": variant, "sections": len(frame),
                                 "sections_with_tiles": int((frame[f"{variant}_tiles"] > 0).sum()),
                                 "median_tiles": float(frame[f"{variant}_tiles"].median()),
                                 "median_eligible_fraction": float(frame[f"{variant}_eligible_fraction"].median())})
        site_outcomes = ["meanhhgsscore", "meanoarsiscore"] + (["plmscore"] if site == "Medial" else [])
        entropy_features = [f"{variant}_angular_entropy_median" for variant in VARIANTS]
        analysis_features = entropy_features + list(GEOMETRY_OD)
        for outcome_index, outcome in enumerate(site_outcomes):
            for feature_index, feature in enumerate(analysis_features):
                selected = frame[[feature, outcome]].dropna()
                if len(selected) < 20 or selected[feature].nunique() < 2:
                    continue
                rho, p_value = spearmanr(selected[feature], selected[outcome])
                low, high = _bootstrap_spearman(selected[feature].to_numpy(), selected[outcome].to_numpy(), seed=110000 + site_index * 10000 + outcome_index * 1000 + feature_index)
                association_rows.append({"site": site, "outcome": outcome, "feature": feature, "n": len(selected),
                                         "spearman_rho": float(rho), "ci95_low": low, "ci95_high": high, "p_value": float(p_value)})
            baseline = "baseline_072_angular_entropy_median"
            comparators = [feature for feature in analysis_features if feature != baseline]
            for feature_index, comparator in enumerate(comparators):
                selected = frame[[baseline, comparator, outcome]].dropna()
                if len(selected) < 20 or selected[baseline].nunique() < 2 or selected[comparator].nunique() < 2:
                    continue
                delta, low, high = _paired_delta_bootstrap(frame, baseline, comparator, outcome,
                    seed=210000 + site_index * 10000 + outcome_index * 1000 + feature_index)
                contrast_rows.append({"site": site, "outcome": outcome, "first": baseline, "second": comparator,
                                      "n": len(selected), "delta_spearman": delta, "ci95_low": low, "ci95_high": high})
            fft = [f"baseline_072_{metric}_median" for metric in ("angular_entropy", "anisotropy", "characteristic_frequency_cycles_per_mm")]
            families = {"geometry_od": list(GEOMETRY_OD), "fft": fft, "fft_plus_geometry_od": fft + list(GEOMETRY_OD)}
            for variant in VARIANTS[1:]:
                families[variant] = [f"{variant}_{metric}_median" for metric in ("angular_entropy", "anisotropy", "characteristic_frequency_cycles_per_mm")]
            rows = _paired_nested_predictions(frame, outcome, families, seed=310000 + site_index * 10000 + outcome_index * 1000)
            for row in rows:
                prediction_rows.append({"site": site, "outcome": outcome, "n": int(frame[outcome].notna().sum()), **row})
    associations = pd.DataFrame(association_rows)
    associations["fdr_q"] = associations.groupby(["site", "outcome"])["p_value"].transform(lambda values: _bh_adjust(values.to_numpy()))
    contrasts = pd.DataFrame(contrast_rows)
    predictions = pd.DataFrame(prediction_rows)
    summary = predictions.groupby(["site", "outcome", "family"], as_index=False).agg(mean_r2=("r2", "mean"), sd_r2=("r2", "std"), mean_mae=("mae", "mean"), sd_mae=("mae", "std"))
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(availability).to_csv(output / "ablation_availability.csv", index=False)
    associations.to_csv(output / "ablation_associations.csv", index=False)
    contrasts.to_csv(output / "ablation_correlation_contrasts.csv", index=False)
    predictions.to_csv(output / "ablation_prediction_repeats.csv", index=False)
    summary.to_csv(output / "ablation_prediction_summary.csv", index=False)
    payload = {"protocol_version": "nostos-cartilage-ablation-analysis/1.1", "status": "exploratory_weak_mask",
               "availability": availability, "association_rows": len(associations), "contrast_rows": len(contrasts),
               "prediction_rows": len(predictions), "paired_correlation_contrasts": "participant bootstrap, 2000 draws",
               "prediction_design": "10 repeats of participant-level 5-fold outer CV with inner RidgeCV; folds paired across families",
               "claim_boundary": "Results localize sensitivity within proposal-defined compartments and cannot establish matrix specificity before mask review."}
    (output / "cartilage_ablation_analysis.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--medial", type=Path, required=True)
    parser.add_argument("--lateral", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze_cartilage_ablations(args.medial, args.lateral, args.scores, args.output), indent=2))


if __name__ == "__main__":
    main()
