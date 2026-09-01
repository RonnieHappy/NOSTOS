"""Ground-truth and stability metrics used by the frozen validation harness."""
from __future__ import annotations

import numpy as np


def axial_angular_error_degrees(estimate: float, truth: float) -> float:
    difference = abs((estimate - truth) % 180.0)
    return float(min(difference, 180.0 - difference))


def relative_scale_error(estimate: float, truth: float) -> float:
    if truth <= 0:
        raise ValueError("Scale truth must be positive.")
    return float(abs(estimate - truth) / truth)


def physical_mae(estimate: np.ndarray, truth: np.ndarray) -> float:
    estimate_array = np.asarray(estimate, dtype=float)
    truth_array = np.asarray(truth, dtype=float)
    if estimate_array.shape != truth_array.shape:
        raise ValueError("Estimate and truth must have identical shapes.")
    return float(np.mean(np.abs(estimate_array - truth_array)))


def normalized_curve_distance(reference: np.ndarray, perturbed: np.ndarray) -> float:
    a = np.asarray(reference, dtype=float).ravel()
    b = np.asarray(perturbed, dtype=float).ravel()
    if a.shape != b.shape:
        raise ValueError("Curves must have identical shapes.")
    denominator = max(float(np.linalg.norm(a)), np.finfo(float).eps)
    return float(np.linalg.norm(a - b) / denominator)


def should_abstain(*, pixels_per_scale: float, signal_to_noise: float, mask_coverage: float = 1.0) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if pixels_per_scale < 4.0:
        reasons.append("requested scale is represented by fewer than four pixels")
    if signal_to_noise < 3.0:
        reasons.append("estimated signal-to-noise ratio is below 3")
    if mask_coverage < 0.05:
        reasons.append("eligible mask coverage is below 5 percent")
    return bool(reasons), tuple(reasons)
