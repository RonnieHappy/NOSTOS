"""Development-only coordinate bridges between NOSTOS and SHG comparators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.stats import spearmanr, theilslopes


MODEL_ORDER = ("identity", "robust_affine", "robust_log_affine")


def fit_bridge(kind: str, observed: Sequence[float], reference: Sequence[float]) -> dict[str, Any]:
    x = np.asarray(observed, dtype=float)
    y = np.asarray(reference, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 4:
        raise ValueError("Bridge fitting requires at least four aligned scalar pairs.")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Bridge fitting requires finite values.")
    if kind == "identity":
        return {"kind": kind}
    if kind == "robust_affine":
        slope, intercept, lower, upper = theilslopes(y, x)
        if not np.isfinite([slope, intercept, lower, upper]).all():
            raise ValueError("Robust affine fitting produced non-finite parameters.")
        return {
            "kind": kind,
            "slope": float(slope),
            "intercept": float(intercept),
            "slope_95": [float(lower), float(upper)],
        }
    if kind == "robust_log_affine":
        if np.any(x <= 0) or np.any(y <= 0):
            raise ValueError("Log-affine fitting requires strictly positive values.")
        slope, intercept, lower, upper = theilslopes(np.log(y), np.log(x))
        if not np.isfinite([slope, intercept, lower, upper]).all():
            raise ValueError("Robust log-affine fitting produced non-finite parameters.")
        return {
            "kind": kind,
            "exponent": float(slope),
            "log_intercept": float(intercept),
            "exponent_95": [float(lower), float(upper)],
        }
    raise ValueError(f"Unknown bridge model: {kind!r}")


def apply_bridge(model: Mapping[str, Any], values: Sequence[float]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    kind = str(model["kind"])
    if kind == "identity":
        return x.copy()
    if kind == "robust_affine":
        return float(model["intercept"]) + float(model["slope"]) * x
    if kind == "robust_log_affine":
        if np.any(x <= 0):
            raise ValueError("Log-affine application requires strictly positive values.")
        return np.exp(float(model["log_intercept"])) * np.power(x, float(model["exponent"]))
    raise ValueError(f"Unknown bridge model: {kind!r}")


def normalized_error(
    predicted: Sequence[float],
    reference: Sequence[float],
    *,
    mode: str,
    tolerance: float,
    denominator_floor: float,
) -> np.ndarray:
    predicted_values = np.asarray(predicted, dtype=float)
    reference_values = np.asarray(reference, dtype=float)
    difference = np.abs(predicted_values - reference_values)
    if mode == "absolute":
        return difference / float(tolerance)
    if mode == "relative":
        denominator = np.maximum(np.abs(reference_values), float(denominator_floor))
        return difference / denominator / float(tolerance)
    raise ValueError(f"Unknown error mode: {mode!r}")


def stability_invalid(
    model: Mapping[str, Any],
    observed: float | None,
    clean: float | None,
    *,
    mode: str,
    tolerance: float,
    denominator_floor: float,
) -> tuple[bool, float | None]:
    """Judge mapped perturbation drift relative to the same field's clean value."""

    if observed is None or clean is None or not np.isfinite(observed) or not np.isfinite(clean):
        return True, None
    mapped = apply_bridge(model, [float(observed), float(clean)])
    error = normalized_error(
        [mapped[0]],
        [mapped[1]],
        mode=mode,
        tolerance=tolerance,
        denominator_floor=denominator_floor,
    )[0]
    return bool(error > 1.0), float(error)


def leave_one_mouse_out_models(
    rows: Sequence[Mapping[str, Any]],
    *,
    observed_key: str,
    reference_key: str,
    mode: str,
    tolerance: float,
    denominator_floor: float,
) -> dict[str, Any]:
    mice = sorted({str(row["mouse"]) for row in rows})
    if len(mice) < 4:
        raise ValueError("At least four independent mice are required.")
    candidate_errors: dict[str, list[float]] = {kind: [] for kind in MODEL_ORDER}
    candidate_predictions: dict[str, list[float]] = {kind: [] for kind in MODEL_ORDER}
    heldout_reference: list[float] = []
    for mouse in mice:
        training = [row for row in rows if str(row["mouse"]) != mouse]
        heldout = [row for row in rows if str(row["mouse"]) == mouse]
        x_train = [float(row[observed_key]) for row in training]
        y_train = [float(row[reference_key]) for row in training]
        x_test = [float(row[observed_key]) for row in heldout]
        y_test = [float(row[reference_key]) for row in heldout]
        heldout_reference.extend(y_test)
        for kind in MODEL_ORDER:
            try:
                model = fit_bridge(kind, x_train, y_train)
                predicted = apply_bridge(model, x_test)
                errors = normalized_error(
                    predicted,
                    y_test,
                    mode=mode,
                    tolerance=tolerance,
                    denominator_floor=denominator_floor,
                )
            except ValueError:
                predicted = np.full(len(x_test), np.nan)
                errors = np.full(len(x_test), np.inf)
            candidate_predictions[kind].extend(float(value) for value in predicted)
            candidate_errors[kind].extend(float(value) for value in errors)
    reference_array = np.asarray(heldout_reference, dtype=float)
    summaries: dict[str, Any] = {}
    for kind in MODEL_ORDER:
        errors = np.asarray(candidate_errors[kind], dtype=float)
        predictions = np.asarray(candidate_predictions[kind], dtype=float)
        reference_iqr = float(np.subtract(*np.percentile(reference_array, [75, 25])))
        prediction_iqr = (
            float(np.subtract(*np.percentile(predictions, [75, 25])))
            if np.isfinite(predictions).all()
            else float("nan")
        )
        finite = bool(np.isfinite(errors).all() and np.isfinite(predictions).all())
        summaries[kind] = {
            "finite": finite,
            "median_normalized_error": float(np.median(errors)) if finite else None,
            "p90_normalized_error": float(np.percentile(errors, 90.0)) if finite else None,
            "within_tolerance_fraction": float(np.mean(errors <= 1.0)) if finite else 0.0,
            "prediction_to_reference_iqr_ratio": (
                float(prediction_iqr / reference_iqr)
                if reference_iqr > 0 and np.isfinite(prediction_iqr)
                else None
            ),
        }
    eligible = [
        kind
        for kind in MODEL_ORDER
        if summaries[kind]["finite"]
        and summaries[kind]["prediction_to_reference_iqr_ratio"] is not None
        and 0.20 <= summaries[kind]["prediction_to_reference_iqr_ratio"] <= 5.0
    ]
    selected = (
        min(
            eligible,
            key=lambda kind: (
                summaries[kind]["median_normalized_error"],
                summaries[kind]["p90_normalized_error"],
                MODEL_ORDER.index(kind),
            ),
        )
        if eligible
        else None
    )
    x_all = [float(row[observed_key]) for row in rows]
    y_all = [float(row[reference_key]) for row in rows]
    rho = (
        float(spearmanr(x_all, y_all).statistic)
        if np.ptp(np.asarray(x_all, dtype=float)) > 0 and np.ptp(np.asarray(y_all, dtype=float)) > 0
        else float("nan")
    )
    return {
        "independent_mice": len(mice),
        "cases": len(rows),
        "rank_spearman_rho": rho if np.isfinite(rho) else None,
        "candidate_summaries": summaries,
        "selected_kind": selected,
        "selected_model": fit_bridge(selected, x_all, y_all) if selected is not None else None,
        "no_eligible_model_reason": (
            None if selected is not None else "all candidate mappings were non-finite or collapsed the reference variation"
        ),
    }


__all__ = [
    "MODEL_ORDER",
    "apply_bridge",
    "fit_bridge",
    "leave_one_mouse_out_models",
    "normalized_error",
    "stability_invalid",
]
