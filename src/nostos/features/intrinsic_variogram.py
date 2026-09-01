"""Rotation-aware spatial response geometry for calibrated 2-D images.

The public object is the scale-by-direction semivariance surface. Scalar axes
and ranges are secondary summaries and abstain when the response cannot support
them. No image-horizontal or image-vertical range is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import ndimage, signal


@dataclass(frozen=True)
class IntrinsicVariogramResponse:
    separations_um: tuple[float, ...]
    directions_degrees: tuple[float, ...]
    semivariance: tuple[tuple[float, ...], ...]
    overlap_fraction: tuple[tuple[float, ...], ...]
    angular_mean_curve: tuple[float, ...]
    angular_anisotropy_curve: tuple[float, ...]
    major_correlation_curve: tuple[float, ...]
    minor_correlation_curve: tuple[float, ...]
    major_correlation_axis_degrees_by_scale: tuple[float | None, ...]
    axis_consensus_degrees: float | None
    axis_consensus_resultant: float
    major_e_fold_range_um: float | None
    minor_e_fold_range_um: float | None
    range_identifiable: bool
    abstention_reasons: tuple[str, ...]


def _validate(
    image: np.ndarray,
    spacing_um: Sequence[float],
    separations_um: Sequence[float],
    directions_degrees: Sequence[float],
) -> tuple[np.ndarray, tuple[float, float], tuple[float, ...], tuple[float, ...]]:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 16:
        raise ValueError("A 2-D image of at least 16 x 16 pixels is required.")
    if not np.isfinite(data).all():
        raise ValueError("The image must contain only finite values.")
    spacing = tuple(float(value) for value in spacing_um)
    if len(spacing) != 2 or any(value <= 0 for value in spacing):
        raise ValueError("spacing_um must contain two positive values in y, x order.")
    separations = tuple(float(value) for value in separations_um)
    if len(separations) < 3 or any(value <= 0 for value in separations):
        raise ValueError("At least three positive separations are required.")
    if any(right <= left for left, right in zip(separations, separations[1:])):
        raise ValueError("separations_um must be strictly increasing.")
    directions = tuple(float(value) % 180.0 for value in directions_degrees)
    if len(directions) < 6 or len(set(directions)) != len(directions):
        raise ValueError("At least six unique axial directions are required.")
    if np.ptp(data) <= np.finfo(float).eps:
        data = np.zeros_like(data)
    else:
        data = data - float(np.mean(data))
    return data, (spacing[0], spacing[1]), separations, directions


def _autocovariance(data: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Return unbiased zero-padded autocovariance and overlap-count surfaces."""

    reversed_data = data[::-1, ::-1]
    covariance_sum = signal.fftconvolve(data, reversed_data, mode="full")
    support = np.ones(data.shape, dtype=np.float64)
    counts = signal.fftconvolve(support, support[::-1, ::-1], mode="full")
    covariance = covariance_sum / np.maximum(counts, 1.0)
    variance = float(np.mean(np.square(data)))
    return covariance, counts, variance


def _directional_surface(
    data: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    separations_um: tuple[float, ...],
    directions_degrees: tuple[float, ...],
) -> tuple[np.ndarray, np.ndarray]:
    covariance, counts, variance = _autocovariance(data)
    center_y = data.shape[0] - 1
    center_x = data.shape[1] - 1
    total = float(data.size)
    surface = np.empty((len(separations_um), len(directions_degrees)), dtype=float)
    overlap = np.empty_like(surface)
    for row_index, separation in enumerate(separations_um):
        angles = np.deg2rad(np.asarray(directions_degrees, dtype=float))
        shifts_y = separation * np.sin(angles) / spacing_um[0]
        shifts_x = separation * np.cos(angles) / spacing_um[1]
        if (
            np.max(np.abs(shifts_y)) >= data.shape[0] - 2
            or np.max(np.abs(shifts_x)) >= data.shape[1] - 2
        ):
            raise ValueError("A requested separation exceeds the supported image extent.")
        coordinates = np.vstack((center_y + shifts_y, center_x + shifts_x))
        sampled_covariance = ndimage.map_coordinates(
            covariance,
            coordinates,
            order=1,
            mode="nearest",
            prefilter=False,
        )
        sampled_counts = ndimage.map_coordinates(
            counts,
            coordinates,
            order=1,
            mode="nearest",
            prefilter=False,
        )
        surface[row_index] = np.maximum(0.0, variance - sampled_covariance)
        overlap[row_index] = np.clip(sampled_counts / total, 0.0, 1.0)
    return surface, overlap


def _angular_harmonics(
    surface: np.ndarray,
    directions_degrees: tuple[float, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[float | None]]:
    angles = np.deg2rad(np.asarray(directions_degrees, dtype=float))
    design = np.column_stack(
        (
            np.ones(len(angles), dtype=float),
            np.cos(2.0 * angles),
            np.sin(2.0 * angles),
        )
    )
    coefficients = np.linalg.lstsq(design, surface.T, rcond=None)[0].T
    mean = np.maximum(coefficients[:, 0], 0.0)
    amplitude = np.hypot(coefficients[:, 1], coefficients[:, 2])
    amplitude = np.minimum(amplitude, mean)
    anisotropy = np.divide(
        amplitude,
        mean,
        out=np.zeros_like(amplitude),
        where=mean > np.finfo(float).eps,
    )
    major_curve = np.maximum(mean - amplitude, 0.0)
    minor_curve = mean + amplitude
    axes: list[float | None] = []
    for a0, cosine, sine, ratio in zip(
        mean,
        coefficients[:, 1],
        coefficients[:, 2],
        anisotropy,
        strict=True,
    ):
        if a0 <= np.finfo(float).eps or ratio < 0.05:
            axes.append(None)
            continue
        maximum_semivariance = 0.5 * np.degrees(np.arctan2(sine, cosine))
        axes.append(float((maximum_semivariance + 90.0) % 180.0))
    return mean, anisotropy, major_curve, minor_curve, axes


def _axis_consensus(
    axes: Sequence[float | None],
    anisotropy: np.ndarray,
) -> tuple[float | None, float]:
    available = [
        (float(axis), float(weight))
        for axis, weight in zip(axes, anisotropy, strict=True)
        if axis is not None and weight > 0
    ]
    if not available:
        return None, 0.0
    angles = np.deg2rad([2.0 * item[0] for item in available])
    weights = np.asarray([item[1] for item in available], dtype=float)
    vector = np.sum(weights * np.exp(1j * angles))
    resultant = float(abs(vector) / np.sum(weights))
    if float(np.mean(weights)) < 0.05 or resultant < 0.5:
        return None, resultant
    axis = float((0.5 * np.degrees(np.angle(vector))) % 180.0)
    return axis, resultant


def _e_fold_range(
    separations_um: tuple[float, ...],
    curve: np.ndarray,
) -> tuple[float | None, str | None]:
    """Estimate a finite-window e-fold crossing, abstaining without a plateau."""

    values = np.maximum.accumulate(np.asarray(curve, dtype=float))
    if values[-1] <= np.finfo(float).eps:
        return None, "variogram_signal_absent"
    increments = np.diff(values)
    recent = float(np.sum(increments[-2:])) if increments.size >= 2 else float(increments[-1])
    total = float(values[-1] - values[0])
    if total <= np.finfo(float).eps or recent / total > 0.25:
        return None, "variogram_plateau_not_observed"
    target = (1.0 - np.exp(-1.0)) * values[-1]
    indices = np.flatnonzero(values >= target)
    if not indices.size or int(indices[0]) == len(values) - 1:
        return None, "variogram_e_fold_crossing_not_interior"
    upper = int(indices[0])
    if upper == 0:
        return float(separations_um[0]), None
    lower = upper - 1
    denominator = float(values[upper] - values[lower])
    fraction = 0.0 if denominator <= 0 else float((target - values[lower]) / denominator)
    estimate = float(
        separations_um[lower]
        + fraction * (separations_um[upper] - separations_um[lower])
    )
    return estimate, None


def intrinsic_variogram_2d(
    image: np.ndarray,
    *,
    spacing_um: Sequence[float],
    separations_um: Sequence[float],
    directions_degrees: Sequence[float] = tuple(float(value) for value in range(0, 180, 15)),
) -> IntrinsicVariogramResponse:
    """Measure a physically indexed, rotation-aware 2-D variogram surface.

    The major/minor curves are second-harmonic summaries and therefore remain
    intrinsic under in-plane rotation. The consensus axis is equivariant. Range
    summaries are emitted only when an interior e-fold crossing and finite-field
    plateau are both supported.
    """

    data, spacing, separations, directions = _validate(
        image,
        spacing_um,
        separations_um,
        directions_degrees,
    )
    surface, overlap = _directional_surface(
        data,
        spacing_um=spacing,
        separations_um=separations,
        directions_degrees=directions,
    )
    mean, anisotropy, major, minor, axes = _angular_harmonics(surface, directions)
    consensus, resultant = _axis_consensus(axes, anisotropy)
    major_range, major_reason = _e_fold_range(separations, major)
    minor_range, minor_reason = _e_fold_range(separations, minor)
    reasons = []
    if consensus is None:
        reasons.append("directional_axis_not_identifiable")
    if major_reason is not None:
        reasons.append(f"major_{major_reason}")
    if minor_reason is not None:
        reasons.append(f"minor_{minor_reason}")
    if float(np.min(overlap)) < 0.25:
        reasons.append("directional_overlap_below_25_percent")
    range_identifiable = (
        major_range is not None
        and minor_range is not None
        and "directional_overlap_below_25_percent" not in reasons
    )
    return IntrinsicVariogramResponse(
        separations_um=separations,
        directions_degrees=directions,
        semivariance=tuple(tuple(float(value) for value in row) for row in surface),
        overlap_fraction=tuple(tuple(float(value) for value in row) for row in overlap),
        angular_mean_curve=tuple(float(value) for value in mean),
        angular_anisotropy_curve=tuple(float(value) for value in anisotropy),
        major_correlation_curve=tuple(float(value) for value in major),
        minor_correlation_curve=tuple(float(value) for value in minor),
        major_correlation_axis_degrees_by_scale=tuple(axes),
        axis_consensus_degrees=consensus,
        axis_consensus_resultant=resultant,
        major_e_fold_range_um=major_range,
        minor_e_fold_range_um=minor_range,
        range_identifiable=range_identifiable,
        abstention_reasons=tuple(dict.fromkeys(reasons)),
    )
