"""Physically scaled two-parameter structure-tensor responses.

The local derivative scale and the outer integration scale are both expressed
in physical units.  This prevents a high-resolution reference from contributing
native-grid gradients that the paired lower-resolution acquisition cannot
represent.  The response preserves scale curves and axial histograms instead of
immediately collapsing the image to one unqualified scalar.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class PhysicalTensorResponse:
    scales_um: tuple[float, ...]
    derivative_sigma_um: tuple[float, ...]
    integration_sigma_um: tuple[float, ...]
    orientation_degrees: tuple[float, ...]
    coherency: tuple[float, ...]
    orientation_resultant: tuple[float, ...]
    jackknife_axis_drift_degrees: tuple[float, ...]
    orientation_histogram_edges_degrees: tuple[float, ...]
    orientation_histograms: tuple[tuple[float, ...], ...]
    trace_energy_density: tuple[float, ...]


def axial_circular_wasserstein_degrees(
    first: np.ndarray | tuple[float, ...],
    second: np.ndarray | tuple[float, ...],
) -> float:
    """Return circular Wasserstein-1 distance for an axial histogram.

    Histograms cover 180 degrees with uniform bins.  The median-centred
    cumulative-difference formula minimizes transport over every possible cut
    of the axial circle and returns an interpretable distance in degrees.
    """

    left = np.asarray(first, dtype=float)
    right = np.asarray(second, dtype=float)
    if left.ndim != 1 or left.shape != right.shape or len(left) < 12:
        raise ValueError("Axial histograms must be equal one-dimensional arrays.")
    if (
        np.any(~np.isfinite(left))
        or np.any(~np.isfinite(right))
        or np.any(left < 0)
        or np.any(right < 0)
    ):
        raise ValueError("Axial histograms must contain finite nonnegative mass.")
    left_total = float(left.sum())
    right_total = float(right.sum())
    if left_total <= 0 or right_total <= 0:
        raise ValueError("Axial histograms must contain positive mass.")
    difference = np.cumsum(left / left_total - right / right_total)
    bin_width = 180.0 / len(left)
    return float(bin_width * np.sum(np.abs(difference - np.median(difference))))


def shift_axial_histogram(
    histogram: np.ndarray | tuple[float, ...],
    angle_degrees: float,
) -> np.ndarray:
    """Shift an axial histogram by a possibly fractional angle with wraparound."""

    values = np.asarray(histogram, dtype=float)
    if values.ndim != 1 or len(values) < 12 or np.any(values < 0):
        raise ValueError("A nonnegative one-dimensional axial histogram is required.")
    total = float(values.sum())
    if not np.isfinite(values).all() or total <= 0 or not np.isfinite(angle_degrees):
        raise ValueError("Histogram mass and angle must be finite.")
    indices = np.arange(len(values), dtype=float)
    shift_bins = float(angle_degrees) / (180.0 / len(values))
    shifted = np.interp(
        np.mod(indices - shift_bins, len(values)),
        indices,
        values,
        period=len(values),
    )
    shifted = np.clip(shifted, 0.0, None)
    return shifted / float(shifted.sum())


def _validate_image(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 32:
        raise ValueError("A 2-D image of at least 32 x 32 pixels is required.")
    if not np.isfinite(data).all():
        raise ValueError("The image contains non-finite values.")
    if float(np.std(data)) <= np.finfo(float).eps:
        raise ValueError("The image has no measurable intensity variation.")
    return data


def _axial_error_degrees(first: float, second: float) -> float:
    difference = abs(float(first) - float(second)) % 180.0
    return float(min(difference, 180.0 - difference))


def _axis(moment: complex) -> float:
    return float(np.mod(0.5 * np.angle(moment), np.pi) * 180.0 / np.pi)


def _hann(shape: tuple[int, int]) -> np.ndarray:
    y = np.hanning(shape[0])
    x = np.hanning(shape[1])
    window = np.outer(y, x)
    return window / max(float(window.mean()), np.finfo(float).eps)


def _jackknife_axis_drift(
    weighted_axial: np.ndarray,
    weights: np.ndarray,
    global_axis: float,
) -> float:
    rows, columns = weights.shape
    quadrants = (
        (slice(0, rows // 2), slice(0, columns // 2)),
        (slice(0, rows // 2), slice(columns // 2, columns)),
        (slice(rows // 2, rows), slice(0, columns // 2)),
        (slice(rows // 2, rows), slice(columns // 2, columns)),
    )
    total = complex(np.sum(weighted_axial))
    total_weight = float(np.sum(weights))
    drifts: list[float] = []
    for region in quadrants:
        retained_weight = total_weight - float(np.sum(weights[region]))
        if retained_weight <= np.finfo(float).eps:
            continue
        retained = (total - complex(np.sum(weighted_axial[region]))) / retained_weight
        if abs(retained) <= np.finfo(float).eps:
            return 90.0
        drifts.append(_axial_error_degrees(_axis(retained), global_axis))
    return float(max(drifts, default=90.0))


def physical_structure_tensor_response(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    scales_um: tuple[float, ...],
    derivative_scale_fraction: float = 0.5,
    integration_scale_factor: float = 1.0,
    angular_bins: int = 36,
) -> PhysicalTensorResponse:
    """Return a calibrated scale-space structure-tensor response.

    ``scales_um`` declares the response scale.  Gaussian derivatives are
    evaluated at ``derivative_scale_fraction * scale`` and second moments are
    integrated at ``integration_scale_factor * scale``.  Both filters therefore
    describe the same physical support on differently sampled images.
    """

    data = _validate_image(image)
    spacing = np.asarray(spacing_um, dtype=float)
    scales = np.asarray(scales_um, dtype=float)
    if spacing.shape != (2,) or np.any(~np.isfinite(spacing)) or np.any(spacing <= 0):
        raise ValueError("spacing_um must contain two finite positive values.")
    if scales.ndim != 1 or not len(scales) or np.any(~np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("scales_um must be a nonempty finite positive sequence.")
    if derivative_scale_fraction <= 0 or integration_scale_factor <= 0:
        raise ValueError("Both tensor scale factors must be positive.")
    if angular_bins < 12:
        raise ValueError("angular_bins must be at least 12.")

    window = _hann(data.shape)
    edges = np.linspace(0.0, 180.0, angular_bins + 1)
    derivative_sigmas: list[float] = []
    integration_sigmas: list[float] = []
    orientations: list[float] = []
    coherencies: list[float] = []
    resultants: list[float] = []
    jackknife_drifts: list[float] = []
    histograms: list[tuple[float, ...]] = []
    trace_energies: list[float] = []

    for scale in scales:
        derivative_um = float(scale * derivative_scale_fraction)
        integration_um = float(scale * integration_scale_factor)
        derivative_px = tuple(float(derivative_um / value) for value in spacing)
        integration_px = tuple(float(integration_um / value) for value in spacing)

        # Gaussian derivatives define a physical inner scale before the tensor
        # products are formed.  scipy returns derivatives per sample, so divide
        # by physical spacing to obtain comparable gradient units.
        gy = ndimage.gaussian_filter(
            data,
            sigma=derivative_px,
            order=(1, 0),
            mode="reflect",
        ) / float(spacing[0])
        gx = ndimage.gaussian_filter(
            data,
            sigma=derivative_px,
            order=(0, 1),
            mode="reflect",
        ) / float(spacing[1])
        jxx = ndimage.gaussian_filter(gx * gx, sigma=integration_px, mode="reflect")
        jyy = ndimage.gaussian_filter(gy * gy, sigma=integration_px, mode="reflect")
        jxy = ndimage.gaussian_filter(gx * gy, sigma=integration_px, mode="reflect")

        trace = np.maximum(jxx + jyy, 0.0)
        delta = np.sqrt(np.maximum((jxx - jyy) ** 2 + 4.0 * jxy**2, 0.0))
        angle = np.mod(0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + np.pi / 2.0, np.pi)
        weights = window * delta
        total_weight = float(weights.sum())
        total_trace = float(np.sum(window * trace))
        if total_weight <= np.finfo(float).eps or total_trace <= np.finfo(float).eps:
            raise ValueError("The image has insufficient gradient energy at a requested scale.")

        axial = np.exp(2j * angle)
        weighted_axial = weights * axial
        moment = complex(np.sum(weighted_axial) / total_weight)
        orientation = _axis(moment)
        histogram, _ = np.histogram(
            np.degrees(angle),
            bins=edges,
            weights=weights,
        )
        histogram = histogram.astype(np.float64)
        histogram /= max(float(histogram.sum()), np.finfo(float).eps)

        derivative_sigmas.append(derivative_um)
        integration_sigmas.append(integration_um)
        orientations.append(orientation)
        coherencies.append(float(np.clip(total_weight / total_trace, 0.0, 1.0)))
        resultants.append(float(np.clip(abs(moment), 0.0, 1.0)))
        jackknife_drifts.append(
            _jackknife_axis_drift(weighted_axial, weights, orientation)
        )
        histograms.append(tuple(float(value) for value in histogram))
        trace_energies.append(float(total_trace / np.sum(window)))

    return PhysicalTensorResponse(
        scales_um=tuple(float(value) for value in scales),
        derivative_sigma_um=tuple(derivative_sigmas),
        integration_sigma_um=tuple(integration_sigmas),
        orientation_degrees=tuple(orientations),
        coherency=tuple(coherencies),
        orientation_resultant=tuple(resultants),
        jackknife_axis_drift_degrees=tuple(jackknife_drifts),
        orientation_histogram_edges_degrees=tuple(float(value) for value in edges),
        orientation_histograms=tuple(histograms),
        trace_energy_density=tuple(trace_energies),
    )
