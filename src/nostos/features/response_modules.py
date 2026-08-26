"""Interpretable CPU modules for the calibrated NOSTOS response geometry."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


def _image(array: np.ndarray) -> np.ndarray:
    result = np.asarray(array, dtype=np.float64)
    if result.ndim not in (2, 3) or not np.isfinite(result).all():
        raise ValueError("A finite 2-D image or 3-D volume is required.")
    if min(result.shape) < 16:
        raise ValueError("Each image dimension must contain at least 16 samples.")
    return result


def _scales(scales_um: tuple[float, ...], spacing_um: tuple[float, ...], ndim: int) -> tuple[np.ndarray, list[tuple[float, ...]]]:
    physical = np.asarray(scales_um, dtype=float)
    spacing = np.asarray(spacing_um, dtype=float)
    if physical.ndim != 1 or not len(physical) or np.any(physical <= 0):
        raise ValueError("Physical scales must be a nonempty positive sequence.")
    if spacing.shape != (ndim,) or np.any(spacing <= 0):
        raise ValueError("Spacing must match image dimensionality and be positive.")
    return physical, [tuple(float(scale / value) for value in spacing) for scale in physical]


@dataclass(frozen=True)
class TensorResponse:
    scales_um: tuple[float, ...]
    orientation_degrees: tuple[float, ...]
    coherency: tuple[float, ...]


def structure_tensor_response(image: np.ndarray, *, spacing_um: tuple[float, float], scales_um: tuple[float, ...]) -> TensorResponse:
    """Return axial orientation and coherency across physical integration scales."""
    data = _image(image)
    if data.ndim != 2:
        raise ValueError("The current tensor orientation response is defined for 2-D images.")
    physical, pixel_scales = _scales(scales_um, spacing_um, 2)
    gy, gx = np.gradient(data, *spacing_um)
    orientations: list[float] = []
    coherencies: list[float] = []
    for sigma in pixel_scales:
        jxx = ndimage.gaussian_filter(gx * gx, sigma=sigma, mode="reflect")
        jyy = ndimage.gaussian_filter(gy * gy, sigma=sigma, mode="reflect")
        jxy = ndimage.gaussian_filter(gx * gy, sigma=sigma, mode="reflect")
        # Gradient direction is normal to the spatial structure. Doubling
        # angles produces an axial mean that is invariant to 180-degree flips.
        angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
        delta = np.sqrt((jxx - jyy) ** 2 + 4 * jxy**2)
        coherence = delta / np.maximum(jxx + jyy, np.finfo(float).eps)
        weights = delta
        moment = np.sum(weights * np.exp(2j * angle)) / max(float(weights.sum()), np.finfo(float).eps)
        orientations.append(float(np.mod(0.5 * np.angle(moment), np.pi) * 180 / np.pi))
        coherencies.append(float(np.average(coherence, weights=np.maximum(weights, np.finfo(float).eps))))
    return TensorResponse(tuple(physical.tolist()), tuple(orientations), tuple(coherencies))


@dataclass(frozen=True)
class HessianResponse:
    scales_um: tuple[float, ...]
    blob: tuple[float, ...]
    tube: tuple[float, ...]
    sheet: tuple[float, ...]
    winning_class: str
    winning_scale_um: float


def hessian_morphology_maps(
    image: np.ndarray, *, spacing_um: tuple[float, ...], scales_um: tuple[float, ...],
    polarity: str = "either",
) -> dict[str, tuple[np.ndarray, ...]]:
    """Return scale-resolved blob, tube and sheet response fields.

    This is the spatially resolved counterpart of
    :func:`hessian_morphology_response`; it uses the identical normalization
    and shape ratios and performs no thresholding or tissue-specific fitting.
    """
    if polarity not in {"bright", "dark", "either"}:
        raise ValueError("polarity must be 'bright', 'dark' or 'either'")
    data = _image(image)
    physical, pixel_scales = _scales(scales_um, spacing_um, data.ndim)
    maps: dict[str, list[np.ndarray]] = {"blob": [], "tube": [], "sheet": []}
    for scale, sigma in zip(physical, pixel_scales, strict=True):
        hessian = np.empty(data.shape + (data.ndim, data.ndim), dtype=float)
        for i in range(data.ndim):
            for j in range(i, data.ndim):
                order = [0] * data.ndim
                order[i] += 1
                order[j] += 1
                derivative = ndimage.gaussian_filter(data, sigma=sigma, order=order, mode="reflect") * scale**2
                derivative /= spacing_um[i] * spacing_um[j]
                hessian[..., i, j] = derivative
                hessian[..., j, i] = derivative
        eigen = np.linalg.eigvalsh(hessian)
        if polarity == "bright":
            polarity_gate = np.all(eigen < 0, axis=-1)
        elif polarity == "dark":
            polarity_gate = np.all(eigen > 0, axis=-1)
        else:
            polarity_gate = np.ones(data.shape, dtype=bool)
        magnitude = np.sort(np.abs(eigen), axis=-1)
        eps = np.finfo(float).eps
        if data.ndim == 2:
            small, large = magnitude[..., 0], magnitude[..., 1]
            maps["tube"].append((1.0 - np.exp(-(large / (small + eps)) ** 2 / 2.0)) * large * polarity_gate)
            maps["blob"].append(np.exp(-((large - small) / (large + small + eps)) ** 2 / 0.25) * (large + small) / 2 * polarity_gate)
            maps["sheet"].append(np.zeros_like(data))
        else:
            a, b, c = magnitude[..., 0], magnitude[..., 1], magnitude[..., 2]
            ac, bc, ab = a / (c + eps), b / (c + eps), a / (b + eps)
            tolerance = 0.20
            maps["blob"].append(np.exp(-((1.0 - ac) ** 2 + (1.0 - bc) ** 2) / (2 * tolerance**2)) * c * polarity_gate)
            maps["tube"].append(np.exp(-((1.0 - bc) ** 2 + ab**2) / (2 * tolerance**2)) * c * polarity_gate)
            maps["sheet"].append(np.exp(-(bc**2) / (2 * tolerance**2)) * c * polarity_gate)
    return {name: tuple(values) for name, values in maps.items()}


def hessian_morphology_response(image: np.ndarray, *, spacing_um: tuple[float, ...], scales_um: tuple[float, ...]) -> HessianResponse:
    """Scale-normalized Hessian morphology responses for 2-D or 3-D data."""
    data = _image(image)
    physical, _ = _scales(scales_um, spacing_um, data.ndim)
    maps = hessian_morphology_maps(data, spacing_um=spacing_um, scales_um=scales_um)
    quantile = 99 if data.ndim == 2 else 99.9
    blob_curve = [float(np.percentile(value, quantile)) for value in maps["blob"]]
    tube_curve = [float(np.percentile(value, quantile)) for value in maps["tube"]]
    sheet_curve = [float(np.percentile(value, quantile)) for value in maps["sheet"]]
    curves = {"blob": blob_curve, "tube": tube_curve, "sheet": sheet_curve}
    winner = max(curves, key=lambda name: max(curves[name]))
    index = int(np.argmax(curves[winner]))
    return HessianResponse(tuple(physical.tolist()), tuple(blob_curve), tuple(tube_curve), tuple(sheet_curve), winner, float(physical[index]))


@dataclass(frozen=True)
class GeometryResponse:
    local_thickness_values_um: tuple[float, ...]
    mean_thickness_um: float
    median_thickness_um: float
    p95_thickness_um: float
    method: str


def maximal_sphere_local_thickness(mask: np.ndarray, *, spacing_um: tuple[float, ...], size_bins: int = 32) -> np.ndarray:
    """Approximate maximal-inscribed-sphere thickness using physical radii.

    Radius levels are frozen on a logarithmic grid. At each level, the union of
    spheres centered where the Euclidean distance transform supports that
    radius is assigned the largest containing diameter. The construction is
    scale-aware and works with anisotropic spacing.
    """
    binary = np.asarray(mask, dtype=bool)
    if binary.ndim not in (2, 3) or len(spacing_um) != binary.ndim or not binary.any():
        raise ValueError("A nonempty 2-D/3-D mask with matching spacing is required.")
    if size_bins < 8:
        raise ValueError("size_bins must be at least 8.")
    distance = ndimage.distance_transform_edt(binary, sampling=spacing_um)
    minimum_radius = min(spacing_um) / 2.0
    radii = np.geomspace(float(distance.max()), minimum_radius, size_bins)
    thickness = np.zeros(binary.shape, dtype=np.float32)
    for radius in radii:
        centers = distance >= radius
        if not centers.any():
            continue
        covered = ndimage.distance_transform_edt(~centers, sampling=spacing_um) <= radius
        assign = binary & covered & (thickness == 0)
        thickness[assign] = 2.0 * radius
    thickness[binary & (thickness == 0)] = min(spacing_um)
    return thickness


def local_thickness_response(mask: np.ndarray, *, spacing_um: tuple[float, ...], size_bins: int = 32) -> GeometryResponse:
    """Maximal-sphere local thickness distribution in physical units."""
    binary = np.asarray(mask, dtype=bool)
    thickness = maximal_sphere_local_thickness(binary, spacing_um=spacing_um, size_bins=size_bins)
    values = thickness[binary].astype(float)
    return GeometryResponse(tuple(float(v) for v in values), float(values.mean()), float(np.median(values)), float(np.percentile(values, 95)), f"maximal_sphere_log_bins_{size_bins}")


@dataclass(frozen=True)
class NetworkResponse:
    thresholds: tuple[float, ...]
    component_count: tuple[int, ...]
    surviving_fraction: tuple[float, ...]
    percolates: tuple[bool, ...]
    fragmentation_threshold: float | None


def erosion_survival_response(mask: np.ndarray, *, spacing_um: tuple[float, ...], thresholds_um: tuple[float, ...]) -> NetworkResponse:
    binary = np.asarray(mask, dtype=bool)
    if binary.ndim not in (2, 3) or not binary.any() or len(spacing_um) != binary.ndim:
        raise ValueError("A nonempty calibrated 2-D/3-D mask is required.")
    distance = ndimage.distance_transform_edt(binary, sampling=spacing_um)
    counts: list[int] = []
    fractions: list[float] = []
    percolation: list[bool] = []
    for threshold in thresholds_um:
        retained = binary if threshold == 0 else distance >= threshold
        labels, count = ndimage.label(retained)
        counts.append(int(count))
        fractions.append(float(retained.sum() / binary.sum()))
        spanning = False
        for label_id in range(1, count + 1):
            component = labels == label_id
            for axis in range(binary.ndim):
                low = np.take(component, 0, axis=axis).any()
                high = np.take(component, -1, axis=axis).any()
                spanning |= bool(low and high)
        percolation.append(spanning)
    failure = next((float(t) for t, spans in zip(thresholds_um, percolation, strict=True) if not spans), None)
    return NetworkResponse(thresholds_um, tuple(counts), tuple(fractions), tuple(percolation), failure)


@dataclass(frozen=True)
class VariogramResponse:
    separations_um: tuple[float, ...]
    horizontal: tuple[float, ...]
    vertical: tuple[float, ...]
    estimated_range_horizontal_um: float
    estimated_range_vertical_um: float


def directional_variogram(image: np.ndarray, *, spacing_um: tuple[float, float], separations_um: tuple[float, ...]) -> VariogramResponse:
    data = _image(image)
    if data.ndim != 2:
        raise ValueError("Directional variograms currently require 2-D data.")
    horizontal: list[float] = []
    vertical: list[float] = []
    for separation in separations_um:
        dx = max(1, int(round(separation / spacing_um[1])))
        dy = max(1, int(round(separation / spacing_um[0])))
        horizontal.append(float(0.5 * np.mean((data[:, dx:] - data[:, :-dx]) ** 2)) if dx < data.shape[1] else float("nan"))
        vertical.append(float(0.5 * np.mean((data[dy:, :] - data[:-dy, :]) ** 2)) if dy < data.shape[0] else float("nan"))
    if not np.isfinite(horizontal).all() or not np.isfinite(vertical).all():
        raise ValueError("Requested separation exceeds the supported image extent.")
    def estimate(values: list[float]) -> float:
        sill = max(values)
        # Gaussian/exponential correlation lengths are conventionally tied to
        # an e-folding point; the corresponding variogram reaches 1-e^-1 of
        # its sill. This is estimable before the finite field fully plateaus.
        target = (1.0 - np.exp(-1.0)) * sill
        return float(next((s for s, v in zip(separations_um, values, strict=True) if v >= target), separations_um[-1]))
    return VariogramResponse(separations_um, tuple(horizontal), tuple(vertical), estimate(horizontal), estimate(vertical))
