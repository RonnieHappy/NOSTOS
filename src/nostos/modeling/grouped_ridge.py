from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from nostos.evaluation.participant import participant_metrics


@dataclass(frozen=True)
class GroupedPredictions:
    observed: np.ndarray
    predicted: np.ndarray
    participant_ids: np.ndarray
    outer_fold: np.ndarray
    selected_alpha: np.ndarray


@dataclass(frozen=True)
class LockedPredictions:
    observed: np.ndarray
    predicted: np.ndarray
    participant_ids: np.ndarray
    selected_alpha: float


def _pipeline(alpha: float) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=alpha)),
        ]
    )


def _select_alpha(
    features: np.ndarray,
    outcome: np.ndarray,
    groups: np.ndarray,
    alphas: tuple[float, ...],
    inner_splits: int,
) -> float:
    unique_groups = np.unique(groups)
    folds = min(inner_splits, len(unique_groups))
    if folds < 2:
        return float(alphas[len(alphas) // 2])
    splitter = GroupKFold(n_splits=folds)
    scores: list[float] = []
    for alpha in alphas:
        predictions = np.full(len(outcome), np.nan, dtype=float)
        for train, validation in splitter.split(features, outcome, groups):
            model = _pipeline(alpha)
            model.fit(features[train], outcome[train])
            predictions[validation] = model.predict(features[validation])
        metric = participant_metrics(groups, outcome, predictions)
        scores.append(metric.mae)
    return float(alphas[int(np.argmin(scores))])


def grouped_nested_ridge_predictions(
    features: np.ndarray,
    outcome: np.ndarray,
    participant_ids: np.ndarray,
    *,
    alphas: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0),
    outer_splits: int = 5,
    inner_splits: int = 4,
) -> GroupedPredictions:
    """Generate leakage-safe nested-CV predictions grouped by participant."""
    x = np.asarray(features, dtype=float)
    y = np.asarray(outcome, dtype=float)
    groups = np.asarray(participant_ids, dtype=str)
    if x.ndim != 2 or y.ndim != 1 or groups.ndim != 1:
        raise ValueError("Features must be 2-D; outcome and participant IDs must be 1-D.")
    if not (len(x) == len(y) == len(groups)):
        raise ValueError("Features, outcome, and participant IDs must have equal rows.")
    if not np.isfinite(y).all():
        raise ValueError("Outcome must be finite; mechanical or histologic outcomes are never imputed.")
    unique_groups = np.unique(groups)
    folds = min(outer_splits, len(unique_groups))
    if folds < 3:
        raise ValueError("At least three independent participants are required.")

    splitter = GroupKFold(n_splits=folds)
    predictions = np.full(len(y), np.nan, dtype=float)
    fold_id = np.full(len(y), -1, dtype=int)
    selected_alpha = np.full(len(y), np.nan, dtype=float)
    for fold, (train, test) in enumerate(splitter.split(x, y, groups)):
        alpha = _select_alpha(x[train], y[train], groups[train], alphas, inner_splits)
        model = _pipeline(alpha)
        model.fit(x[train], y[train])
        predictions[test] = model.predict(x[test])
        fold_id[test] = fold
        selected_alpha[test] = alpha
        if set(groups[train]).intersection(groups[test]):
            raise AssertionError("Participant leakage detected inside GroupKFold.")

    if not np.isfinite(predictions).all() or (fold_id < 0).any():
        raise RuntimeError("Grouped cross-validation did not produce one prediction per row.")
    return GroupedPredictions(y, predictions, groups, fold_id, selected_alpha)


def participant_permutation_test(
    features: np.ndarray,
    outcome: np.ndarray,
    participant_ids: np.ndarray,
    *,
    iterations: int = 1000,
    seed: int = 240826,
    outer_splits: int = 5,
    inner_splits: int = 4,
) -> dict[str, float]:
    """Falsify prediction after shuffling outcomes across participant-level rows."""
    groups = np.asarray(participant_ids, dtype=str)
    if len(np.unique(groups)) != len(groups):
        raise ValueError("permutation input must contain exactly one row per participant")
    if iterations < 20:
        raise ValueError("at least 20 permutations are required")
    observed_predictions = grouped_nested_ridge_predictions(
        features, outcome, groups, outer_splits=outer_splits, inner_splits=inner_splits
    )
    observed_mae = participant_metrics(groups, outcome, observed_predictions.predicted).mae
    rng = np.random.default_rng(seed)
    null_mae = np.empty(iterations, dtype=float)
    for index in range(iterations):
        shuffled = rng.permutation(np.asarray(outcome, dtype=float))
        predictions = grouped_nested_ridge_predictions(
            features, shuffled, groups, outer_splits=outer_splits, inner_splits=inner_splits
        )
        null_mae[index] = participant_metrics(groups, shuffled, predictions.predicted).mae
    return {
        "observed_mae": float(observed_mae),
        "null_mae_mean": float(np.mean(null_mae)),
        "null_mae_sd": float(np.std(null_mae, ddof=1)),
        "permutation_p_lower_mae": float((1 + np.sum(null_mae <= observed_mae)) / (iterations + 1)),
        "iterations": float(iterations),
    }


def locked_ridge_predictions(
    development_features: np.ndarray,
    development_outcome: np.ndarray,
    development_participants: np.ndarray,
    test_features: np.ndarray,
    test_outcome: np.ndarray,
    test_participants: np.ndarray,
    *,
    alphas: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0),
    inner_splits: int = 5,
) -> LockedPredictions:
    """Select all preprocessing/model parameters in development, then predict test once."""
    x_dev, y_dev = np.asarray(development_features, float), np.asarray(development_outcome, float)
    g_dev = np.asarray(development_participants, str)
    x_test, y_test = np.asarray(test_features, float), np.asarray(test_outcome, float)
    g_test = np.asarray(test_participants, str)
    if x_dev.ndim != 2 or x_test.ndim != 2 or x_dev.shape[1] != x_test.shape[1]:
        raise ValueError("development and test features must be 2-D with matching columns")
    if not (len(x_dev) == len(y_dev) == len(g_dev) and len(x_test) == len(y_test) == len(g_test)):
        raise ValueError("feature, outcome, and participant row counts must agree")
    overlap = set(g_dev).intersection(g_test)
    if overlap:
        raise ValueError(f"participant leakage into locked test: {sorted(overlap)}")
    alpha = _select_alpha(x_dev, y_dev, g_dev, alphas, inner_splits)
    model = _pipeline(alpha)
    model.fit(x_dev, y_dev)
    prediction = model.predict(x_test)
    return LockedPredictions(y_test, prediction, g_test, alpha)
