"""Structure-independent endpoint-family calibration of measurement support.

The calibrator maps an input-only support score to an estimated invalidity risk.
Endpoint family changes the calibration map; tissue or structure never enters
the predictor. Cross-fitting keeps every reference field in one fold.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass(frozen=True)
class IsotonicRiskMap:
    x_thresholds: tuple[float, ...]
    y_thresholds: tuple[float, ...]
    training_cases: int
    training_invalid: int
    bins: int
    prior_alpha: float
    prior_beta: float

    def predict(self, values: Sequence[float] | np.ndarray) -> np.ndarray:
        data = np.asarray(values, dtype=float)
        if not self.x_thresholds:
            raise ValueError("Risk map contains no thresholds.")
        if len(self.x_thresholds) == 1:
            return np.full(data.shape, self.y_thresholds[0], dtype=float)
        return np.interp(
            data,
            np.asarray(self.x_thresholds, dtype=float),
            np.asarray(self.y_thresholds, dtype=float),
            left=self.y_thresholds[0],
            right=self.y_thresholds[-1],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": "quantile_binned_jeffreys_isotonic",
            "x_thresholds": list(self.x_thresholds),
            "y_thresholds": list(self.y_thresholds),
            "training_cases": self.training_cases,
            "training_invalid": self.training_invalid,
            "bins": self.bins,
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
        }


def endpoint_family(endpoint: str, family_map: Mapping[str, Sequence[str]]) -> str:
    matches = [family for family, endpoints in family_map.items() if endpoint in endpoints]
    if len(matches) != 1:
        raise ValueError(
            f"Endpoint {endpoint!r} must belong to exactly one family; observed {matches}."
        )
    return matches[0]


def _score_groups(scores: np.ndarray, labels: np.ndarray) -> list[dict[str, Any]]:
    order = np.argsort(scores, kind="mergesort")
    scores = scores[order]
    labels = labels[order]
    groups: list[dict[str, Any]] = []
    index = 0
    while index < len(scores):
        end = index + 1
        while end < len(scores) and scores[end] == scores[index]:
            end += 1
        groups.append(
            {
                "score_sum": float(np.sum(scores[index:end])),
                "n": int(end - index),
                "invalid": int(np.sum(labels[index:end])),
            }
        )
        index = end
    return groups


def _quantile_bins(
    scores: np.ndarray,
    labels: np.ndarray,
    *,
    bins: int,
) -> list[dict[str, Any]]:
    if bins < 2:
        raise ValueError("At least two bins are required.")
    groups = _score_groups(scores, labels)
    target = max(1, int(np.ceil(len(scores) / bins)))
    output: list[dict[str, Any]] = []
    current = {"score_sum": 0.0, "n": 0, "invalid": 0}
    for group in groups:
        if current["n"] >= target and len(output) < bins - 1:
            output.append(current)
            current = {"score_sum": 0.0, "n": 0, "invalid": 0}
        current["score_sum"] += group["score_sum"]
        current["n"] += group["n"]
        current["invalid"] += group["invalid"]
    if current["n"]:
        output.append(current)
    return output


def fit_isotonic_risk_map(
    scores: Sequence[float] | np.ndarray,
    invalid: Sequence[bool] | np.ndarray,
    *,
    bins: int,
    prior_alpha: float = 0.5,
    prior_beta: float = 0.5,
) -> IsotonicRiskMap:
    """Fit a monotone risk map to quantile-bin Jeffreys posterior means."""

    x = np.asarray(scores, dtype=float)
    y = np.asarray(invalid, dtype=bool).astype(float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or not len(x):
        raise ValueError("Scores and labels must be nonempty aligned vectors.")
    if not np.isfinite(x).all():
        raise ValueError("Scores must be finite.")
    if prior_alpha <= 0 or prior_beta <= 0:
        raise ValueError("Beta-prior parameters must be positive.")
    summaries = _quantile_bins(x, y, bins=bins)
    bin_x = np.asarray(
        [item["score_sum"] / item["n"] for item in summaries],
        dtype=float,
    )
    bin_y = np.asarray(
        [
            (item["invalid"] + prior_alpha)
            / (item["n"] + prior_alpha + prior_beta)
            for item in summaries
        ],
        dtype=float,
    )
    weights = np.asarray([item["n"] for item in summaries], dtype=float)
    if len(bin_x) == 1:
        fitted_x = bin_x
        fitted_y = bin_y
    else:
        model = IsotonicRegression(
            increasing=True,
            out_of_bounds="clip",
            y_min=0.0,
            y_max=1.0,
        )
        model.fit(bin_x, bin_y, sample_weight=weights)
        fitted_x = np.asarray(model.X_thresholds_, dtype=float)
        fitted_y = np.asarray(model.y_thresholds_, dtype=float)
    return IsotonicRiskMap(
        x_thresholds=tuple(float(value) for value in fitted_x),
        y_thresholds=tuple(float(value) for value in fitted_y),
        training_cases=len(x),
        training_invalid=int(np.sum(y)),
        bins=int(bins),
        prior_alpha=float(prior_alpha),
        prior_beta=float(prior_beta),
    )


def assign_stratified_group_folds(
    rows: Sequence[Mapping[str, Any]],
    *,
    folds: int,
    seed: int,
) -> dict[tuple[str, str], int]:
    """Hash independent fields into balanced folds within each structure."""

    if folds < 2:
        raise ValueError("At least two folds are required.")
    strata: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        strata[str(row["structure"])].add(str(row["reference_group_id"]))
    assignments: dict[tuple[str, str], int] = {}
    for structure, groups in sorted(strata.items()):
        ordered = sorted(
            groups,
            key=lambda group: hashlib.sha256(
                f"{seed}|{structure}|{group}".encode("utf-8")
            ).hexdigest(),
        )
        for index, group in enumerate(ordered):
            assignments[(structure, group)] = index % folds
    return assignments


def cross_fitted_family_risk(
    rows: Sequence[Mapping[str, Any]],
    *,
    family_map: Mapping[str, Sequence[str]],
    raw_score: str,
    bins: int,
    folds: int,
    seed: int,
    prior_alpha: float = 0.5,
    prior_beta: float = 0.5,
) -> tuple[list[dict[str, Any]], dict[str, IsotonicRiskMap]]:
    """Generate out-of-field risk predictions and final all-development maps."""

    endpoints = {endpoint for values in family_map.values() for endpoint in values}
    cases = [
        row
        for row in rows
        if str(row["endpoint"]) in endpoints
        and bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
    ]
    if not cases:
        raise ValueError("No eligible calibration cases were supplied.")
    assignments = assign_stratified_group_folds(cases, folds=folds, seed=seed)
    augmented: list[dict[str, Any]] = []
    for family, endpoints_for_family in family_map.items():
        family_cases = [
            row
            for row in cases
            if str(row["endpoint"]) in set(endpoints_for_family)
        ]
        if not family_cases:
            raise ValueError(f"Family {family!r} has no eligible cases.")
        for fold in range(folds):
            training = [
                row
                for row in family_cases
                if assignments[(str(row["structure"]), str(row["reference_group_id"]))]
                != fold
                and not bool(row["hard_abstention"])
            ]
            held_out = [
                row
                for row in family_cases
                if assignments[(str(row["structure"]), str(row["reference_group_id"]))]
                == fold
            ]
            if not training or not held_out:
                raise ValueError(f"Family {family!r}, fold {fold} is empty.")
            risk_map = fit_isotonic_risk_map(
                [float(row["scores"][raw_score]) for row in training],
                [bool(row["invalid"]) for row in training],
                bins=bins,
                prior_alpha=prior_alpha,
                prior_beta=prior_beta,
            )
            nonhard = [row for row in held_out if not bool(row["hard_abstention"])]
            predictions = risk_map.predict(
                [float(row["scores"][raw_score]) for row in nonhard]
            )
            prediction_index = 0
            for row in held_out:
                clone = dict(row)
                clone["endpoint_family"] = family
                clone["calibration_fold"] = fold
                if bool(row["hard_abstention"]):
                    clone["calibrated_risk"] = 1.0
                else:
                    clone["calibrated_risk"] = float(predictions[prediction_index])
                    prediction_index += 1
                augmented.append(clone)
    augmented.sort(key=lambda row: str(row["case_id"]))
    final_maps: dict[str, IsotonicRiskMap] = {}
    for family, endpoints_for_family in family_map.items():
        training = [
            row
            for row in cases
            if str(row["endpoint"]) in set(endpoints_for_family)
            and not bool(row["hard_abstention"])
        ]
        final_maps[family] = fit_isotonic_risk_map(
            [float(row["scores"][raw_score]) for row in training],
            [bool(row["invalid"]) for row in training],
            bins=bins,
            prior_alpha=prior_alpha,
            prior_beta=prior_beta,
        )
    return augmented, final_maps


def brier_score(rows: Sequence[Mapping[str, Any]], *, score_key: str) -> float:
    probabilities = np.asarray([float(row[score_key]) for row in rows], dtype=float)
    labels = np.asarray([bool(row["invalid"]) for row in rows], dtype=float)
    return float(np.mean(np.square(probabilities - labels)))


def logarithmic_loss(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_key: str,
) -> float:
    probabilities = np.clip(
        np.asarray([float(row[score_key]) for row in rows], dtype=float),
        1e-9,
        1.0 - 1e-9,
    )
    labels = np.asarray([bool(row["invalid"]) for row in rows], dtype=float)
    return float(
        -np.mean(labels * np.log(probabilities) + (1.0 - labels) * np.log1p(-probabilities))
    )


def expected_calibration_error(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_key: str,
    bins: int = 10,
) -> float:
    probabilities = np.asarray([float(row[score_key]) for row in rows], dtype=float)
    labels = np.asarray([bool(row["invalid"]) for row in rows], dtype=float)
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    value = 0.0
    for index in range(bins):
        if index == bins - 1:
            selected = (probabilities >= boundaries[index]) & (
                probabilities <= boundaries[index + 1]
            )
        else:
            selected = (probabilities >= boundaries[index]) & (
                probabilities < boundaries[index + 1]
            )
        if not np.any(selected):
            continue
        value += float(np.mean(selected)) * abs(
            float(np.mean(probabilities[selected])) - float(np.mean(labels[selected]))
        )
    return float(value)


def risk_coverage_auc(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_key: str,
) -> float:
    """Area under tied-score risk–coverage curve, including a zero origin."""

    if not rows:
        raise ValueError("At least one row is required.")
    ordered = sorted(
        rows,
        key=lambda row: (float(row[score_key]), str(row["case_id"])),
    )
    coverage = [0.0]
    risk = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        score = float(ordered[index][score_key])
        end = index
        while end < len(ordered) and float(ordered[end][score_key]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage.append(end / len(ordered))
        risk.append(invalid / end)
        index = end
    return float(np.trapezoid(np.asarray(risk), np.asarray(coverage)))


def calibrated_operating_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    maximum_predicted_risk: float,
) -> dict[str, Any]:
    """Summarize a common calibrated-risk cutoff without structure tuning."""

    accepted = [
        row
        for row in rows
        if not bool(row["hard_abstention"])
        and float(row["calibrated_risk"]) <= maximum_predicted_risk
    ]
    combinations = []
    keys = sorted(
        {
            (str(row["structure"]), str(row["endpoint_family"]))
            for row in rows
        }
    )
    for structure, family in keys:
        subset = [
            row
            for row in rows
            if str(row["structure"]) == structure
            and str(row["endpoint_family"]) == family
        ]
        selected = [row for row in accepted if row in subset]
        invalid = sum(bool(row["invalid"]) for row in selected)
        combinations.append(
            {
                "structure": structure,
                "endpoint_family": family,
                "eligible": len(subset),
                "accepted": len(selected),
                "coverage": len(selected) / len(subset),
                "invalid": int(invalid),
                "risk": float(invalid / len(selected)) if selected else None,
                "reference_fields": len(
                    {str(row["reference_group_id"]) for row in subset}
                ),
            }
        )
    invalid = sum(bool(row["invalid"]) for row in accepted)
    return {
        "maximum_predicted_risk": float(maximum_predicted_risk),
        "eligible": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "invalid": int(invalid),
        "risk": float(invalid / len(accepted)) if accepted else None,
        "combinations": combinations,
    }
