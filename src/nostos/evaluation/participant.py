from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
from scipy.stats import spearmanr


@dataclass(frozen=True)
class ParticipantMetrics:
    participant_count: int
    mae: float
    rmse: float
    r_squared: float
    spearman_rho: float
    calibration_intercept: float
    calibration_slope: float


def _validate_vectors(
    participant_ids: Iterable[str],
    observed: Iterable[float],
    predicted: Iterable[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ids = np.asarray(list(participant_ids), dtype=str)
    y = np.asarray(list(observed), dtype=float)
    yhat = np.asarray(list(predicted), dtype=float)
    if not (len(ids) == len(y) == len(yhat)):
        raise ValueError("Participant IDs, observed values, and predictions must have equal length.")
    if len(ids) == 0:
        raise ValueError("At least one observation is required.")
    if not (np.isfinite(y).all() and np.isfinite(yhat).all()):
        raise ValueError("Observed values and predictions must be finite.")
    return ids, y, yhat


def collapse_by_participant(
    participant_ids: Iterable[str],
    observed: Iterable[float],
    predicted: Iterable[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ids, y, yhat = _validate_vectors(participant_ids, observed, predicted)
    unique = np.unique(ids)
    participant_y = np.empty(len(unique), dtype=float)
    participant_yhat = np.empty(len(unique), dtype=float)
    for index, participant_id in enumerate(unique):
        selected = ids == participant_id
        participant_y[index] = float(np.mean(y[selected]))
        participant_yhat[index] = float(np.mean(yhat[selected]))
    return unique, participant_y, participant_yhat


def participant_metrics(
    participant_ids: Iterable[str],
    observed: Iterable[float],
    predicted: Iterable[float],
) -> ParticipantMetrics:
    ids, y, yhat = collapse_by_participant(participant_ids, observed, predicted)
    residual = yhat - y
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual**2)))
    denominator = float(np.sum((y - y.mean()) ** 2))
    r_squared = float(1.0 - np.sum(residual**2) / denominator) if denominator > 0 else float("nan")
    if np.std(yhat) > np.finfo(float).eps:
        slope, intercept = np.polyfit(yhat, y, 1)
    else:
        slope, intercept = float("nan"), float("nan")
    rho = float(spearmanr(y, yhat).statistic) if len(ids) > 1 else float("nan")
    return ParticipantMetrics(len(ids), mae, rmse, r_squared, rho, float(intercept), float(slope))


def paired_participant_bootstrap(
    participant_ids: Iterable[str],
    observed: Iterable[float],
    prediction_a: Iterable[float],
    prediction_b: Iterable[float],
    *,
    metric: Callable[[np.ndarray, np.ndarray], float] | None = None,
    iterations: int = 5000,
    seed: int = 240826,
) -> dict[str, float]:
    """Estimate paired uncertainty for model B minus model A at participant level.

    For the default MAE, negative differences favor model B.
    """
    if iterations < 100:
        raise ValueError("At least 100 bootstrap iterations are required.")
    ids_a, y_a, a = collapse_by_participant(participant_ids, observed, prediction_a)
    ids_b, y_b, b = collapse_by_participant(participant_ids, observed, prediction_b)
    if not (np.array_equal(ids_a, ids_b) and np.allclose(y_a, y_b)):
        raise ValueError("Paired models do not resolve to the same participants and outcomes.")
    if metric is None:
        metric = lambda truth, prediction: float(np.mean(np.abs(prediction - truth)))
    observed_difference = metric(y_a, b) - metric(y_a, a)
    rng = np.random.default_rng(seed)
    differences = np.empty(iterations, dtype=float)
    for index in range(iterations):
        selected = rng.integers(0, len(ids_a), size=len(ids_a))
        differences[index] = metric(y_a[selected], b[selected]) - metric(y_a[selected], a[selected])
    lower, upper = np.quantile(differences, [0.025, 0.975])
    return {
        "difference": float(observed_difference),
        "ci_95_lower": float(lower),
        "ci_95_upper": float(upper),
        "probability_b_better": float(np.mean(differences < 0.0)),
        "iterations": float(iterations),
    }


def assert_disjoint_participant_splits(splits: dict[str, list[str]]) -> None:
    names = list(splits)
    for first_index, first_name in enumerate(names):
        first = set(splits[first_name])
        if len(first) != len(splits[first_name]):
            raise ValueError(f"Duplicate participant IDs inside split {first_name}.")
        for second_name in names[first_index + 1 :]:
            overlap = first.intersection(splits[second_name])
            if overlap:
                raise ValueError(
                    f"Participant leakage between {first_name} and {second_name}: {sorted(overlap)}"
                )
