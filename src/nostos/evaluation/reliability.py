from __future__ import annotations

import numpy as np
import pandas as pd


def _complete_matrix(
    frame: pd.DataFrame, *, target: str, rater: str, score: str
) -> tuple[np.ndarray, list[str], list[str]]:
    required = {target, rater, score}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing reliability columns: {sorted(missing)}")
    matrix = frame.pivot_table(index=target, columns=rater, values=score, aggfunc="mean")
    matrix = matrix.dropna(axis=0, how="any")
    if matrix.shape[0] < 3 or matrix.shape[1] < 2:
        raise ValueError("ICC requires at least three complete targets and two raters")
    return matrix.to_numpy(float), matrix.index.astype(str).tolist(), matrix.columns.astype(str).tolist()


def icc_2_1(matrix: np.ndarray) -> float:
    """Two-way random-effects, absolute-agreement, single-measure ICC."""
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] < 3 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("ICC matrix must be complete with >=3 targets and >=2 raters")
    n, k = values.shape
    grand = values.mean()
    row_means, column_means = values.mean(axis=1), values.mean(axis=0)
    ms_rows = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_columns = n * np.sum((column_means - grand) ** 2) / (k - 1)
    residual = values - row_means[:, None] - column_means[None, :] + grand
    ms_error = np.sum(residual**2) / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_columns - ms_error) / n
    return float((ms_rows - ms_error) / denominator) if denominator else float("nan")


def reliability_summary(
    frame: pd.DataFrame,
    *,
    target: str,
    rater: str,
    score: str,
    iterations: int = 2000,
    seed: int = 240826,
) -> dict[str, float | int]:
    matrix, targets, raters = _complete_matrix(frame, target=target, rater=rater, score=score)
    estimate = icc_2_1(matrix)
    rng = np.random.default_rng(seed)
    samples = np.empty(iterations)
    for index in range(iterations):
        selected = rng.integers(0, len(matrix), len(matrix))
        samples[index] = icc_2_1(matrix[selected])
    finite = samples[np.isfinite(samples)]
    lower, upper = np.quantile(finite, [0.025, 0.975])
    # Compare each rater with the mean of the other raters; no self-inclusion.
    errors = []
    for column in range(matrix.shape[1]):
        consensus = np.mean(np.delete(matrix, column, axis=1), axis=1)
        errors.extend(np.abs(matrix[:, column] - consensus))
    return {
        "complete_target_count": len(targets),
        "rater_count": len(raters),
        "icc_2_1": estimate,
        "icc_2_1_ci_95_lower": float(lower),
        "icc_2_1_ci_95_upper": float(upper),
        "leave_one_rater_out_mae": float(np.mean(errors)),
        "iterations": iterations,
    }

