"""Training-derived reliability weighting for response-geometry comparison."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class StabilityWeightModel:
    location: tuple[float, ...]
    scale: tuple[float, ...]
    reliability: tuple[float, ...]
    minimum_reliability: float
    effective_coordinates: int

    def to_dict(self) -> dict:
        return asdict(self)


def fit_stability_weights(reference: np.ndarray, perturbed: np.ndarray, *, minimum_reliability: float = .05) -> StabilityWeightModel:
    """Estimate coordinate reliability from paired development measurements.

    Reliability is between-specimen variance divided by between-specimen plus
    perturbation-error variance. It is estimated without outcome labels.
    """
    reference = np.asarray(reference, dtype=float); perturbed = np.asarray(perturbed, dtype=float)
    if reference.shape != perturbed.shape or reference.ndim != 2 or reference.shape[0] < 3:
        raise ValueError("Reference and perturbed matrices must be paired 2-D arrays with at least three cases.")
    if not 0 <= minimum_reliability < 1 or not np.isfinite(reference).all() or not np.isfinite(perturbed).all():
        raise ValueError("Reliability threshold and all matrix values must be finite and valid.")
    between = np.var(reference, axis=0, ddof=1)
    error = np.mean((perturbed - reference) ** 2, axis=0)
    reliability = between / np.maximum(between + error, np.finfo(float).eps)
    reliability = np.where(reliability >= minimum_reliability, reliability, 0.0)
    # The comparison coordinate system must cover both the reference and its
    # declared perturbation envelope. Centering on only one state introduces
    # a systematic shift before reliability weighting.
    envelope = np.vstack([reference, perturbed])
    location = np.mean(envelope, axis=0)
    scale = np.std(envelope, axis=0, ddof=1)
    scale = np.where(scale > np.finfo(float).eps, scale, 1.0)
    return StabilityWeightModel(tuple(location), tuple(scale), tuple(reliability), minimum_reliability,
                                int(np.count_nonzero(reliability)))


def apply_stability_weights(values: np.ndarray, model: StabilityWeightModel) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    location, scale, reliability = map(np.asarray, (model.location, model.scale, model.reliability))
    if values.ndim != 2 or values.shape[1] != len(location) or not np.isfinite(values).all():
        raise ValueError("Values must be a finite 2-D matrix matching the fitted coordinate count.")
    return ((values - location) / scale) * np.sqrt(reliability)
