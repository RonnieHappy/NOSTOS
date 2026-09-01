"""Frozen classical osteochondral-interface estimator and validation metrics."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from nostos.features.response_modules import directional_variogram, structure_tensor_response
from nostos.features.spatial_fft import extract_spatial_fft


@dataclass(frozen=True)
class InterfaceParameters:
    sigma_px: float
    contrast_weight: float
    jump_penalty: float
    contrast_sign: int
    downsample: int = 2


def robust_normalize(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 32 or not np.isfinite(data).all():
        raise ValueError("A finite 2-D image with dimensions >=32 is required.")
    low, high = np.percentile(data, (1.0, 99.0))
    if high <= low:
        raise ValueError("Image has no robust intensity range.")
    return np.clip((data - low) / (high - low), 0.0, 1.0)


def reference_interface(mask: np.ndarray, *, minimum_run: int = 3) -> np.ndarray:
    """First vertically contiguous hard-tissue pixel in each image column."""
    binary = np.asarray(mask, dtype=bool)
    if binary.ndim != 2 or minimum_run < 1:
        raise ValueError("A 2-D mask and positive minimum_run are required.")
    valid = binary.copy()
    for offset in range(1, minimum_run):
        valid[:-offset] &= binary[offset:]
        valid[-offset:] = False
    present = valid.any(axis=0)
    rows = np.argmax(valid, axis=0).astype(float)
    rows[~present] = np.nan
    return rows


def _contrast_map(data: np.ndarray, radius: int = 12) -> np.ndarray:
    cumulative = np.pad(np.cumsum(data, axis=0), ((1, 0), (0, 0)))
    height = data.shape[0]
    rows = np.arange(height)
    above_lo = np.maximum(rows - radius, 0)
    above_n = np.maximum(rows - above_lo, 1)
    below_hi = np.minimum(rows + radius + 1, height)
    below_n = np.maximum(below_hi - rows - 1, 1)
    above = (cumulative[rows] - cumulative[above_lo]) / above_n[:, None]
    below = (cumulative[below_hi] - cumulative[rows + 1]) / below_n[:, None]
    return below - above


def interface_score(image: np.ndarray, parameters: InterfaceParameters) -> np.ndarray:
    data = robust_normalize(image)
    smooth = ndimage.gaussian_filter(data, sigma=parameters.sigma_px, mode="reflect")
    gradient = np.abs(ndimage.gaussian_filter1d(data, sigma=parameters.sigma_px, order=1, axis=0, mode="reflect"))
    contrast = _contrast_map(smooth)
    score = gradient + parameters.contrast_weight * parameters.contrast_sign * contrast
    lo, hi = int(round(0.20 * data.shape[0])), int(round(0.90 * data.shape[0]))
    score[:lo] = -np.inf
    score[hi:] = -np.inf
    return score


def _continuous_path(score: np.ndarray, jump_penalty: float, max_jump: int = 8) -> np.ndarray:
    """Maximum-score path with a first-order absolute-jump penalty."""
    height, width = score.shape
    costs = score[:, 0].copy()
    back = np.zeros((height, width), dtype=np.int16)
    rows = np.arange(height)
    for column in range(1, width):
        candidates = np.full((2 * max_jump + 1, height), -np.inf, dtype=np.float64)
        for index, delta in enumerate(range(-max_jump, max_jump + 1)):
            source = rows - delta
            valid = (source >= 0) & (source < height)
            candidates[index, valid] = costs[source[valid]] - jump_penalty * abs(delta)
        chosen = np.argmax(candidates, axis=0)
        costs = score[:, column] + candidates[chosen, rows]
        back[:, column] = chosen.astype(np.int16) - max_jump
    path = np.empty(width, dtype=np.int32)
    path[-1] = int(np.argmax(costs))
    for column in range(width - 1, 0, -1):
        path[column - 1] = path[column] - int(back[path[column], column])
    return path


def estimate_interface(image: np.ndarray, parameters: InterfaceParameters) -> tuple[np.ndarray, float]:
    """Estimate a continuous interface and return its intrinsic confidence."""
    score = interface_score(image, parameters)
    factor = parameters.downsample
    if factor > 1:
        reduced = ndimage.zoom(score, (1.0 / factor, 1.0 / factor), order=1, prefilter=False)
    else:
        reduced = score
    finite = np.isfinite(reduced)
    floor = float(np.min(reduced[finite]) - 1.0)
    reduced = np.where(finite, reduced, floor)
    path_small = _continuous_path(reduced, parameters.jump_penalty, max_jump=8)
    columns = np.arange(score.shape[1])
    source_columns = np.linspace(0, score.shape[1] - 1, len(path_small))
    path = np.interp(columns, source_columns, path_small * factor)
    selected = score[np.clip(np.rint(path).astype(int), 0, score.shape[0] - 1), columns]
    finite_scores = score[np.isfinite(score)]
    mad = np.median(np.abs(finite_scores - np.median(finite_scores))) + np.finfo(float).eps
    roughness = np.median(np.abs(np.diff(path))) if path.size > 1 else 0.0
    confidence = float(np.median(selected) / mad / (1.0 + roughness))
    return path, confidence


def mask_from_interface(path: np.ndarray, height: int) -> np.ndarray:
    boundary = np.asarray(path, dtype=float)
    if boundary.ndim != 1 or height < 1 or not np.isfinite(boundary).all():
        raise ValueError("A finite one-dimensional path and positive height are required.")
    return np.arange(height)[:, None] >= np.rint(boundary)[None, :]


def threshold_comparator(image: np.ndarray) -> np.ndarray:
    """Global Otsu threshold followed by selection of lower-border components."""
    data = robust_normalize(image)
    histogram, edges = np.histogram(data, bins=256, range=(0.0, 1.0))
    probabilities = histogram / max(histogram.sum(), 1)
    centers = (edges[:-1] + edges[1:]) / 2
    omega = np.cumsum(probabilities)
    mean = np.cumsum(probabilities * centers)
    total = mean[-1]
    between = (total * omega - mean) ** 2 / np.maximum(omega * (1 - omega), np.finfo(float).eps)
    threshold = centers[int(np.argmax(between[:-1]))]
    binary = data >= threshold
    labels, count = ndimage.label(binary)
    lower = np.unique(labels[-1])
    lower = lower[lower > 0]
    if lower.size == 0:
        return np.full(data.shape[1], np.nan)
    selected = np.isin(labels, lower)
    return reference_interface(selected)


def boundary_metrics(predicted: np.ndarray, reference: np.ndarray, *, spacing_um: float) -> dict[str, float | int]:
    prediction = np.asarray(predicted, dtype=float)
    truth = np.asarray(reference, dtype=float)
    if prediction.shape != truth.shape or spacing_um <= 0:
        raise ValueError("Paths must match and spacing must be positive.")
    eligible = np.isfinite(prediction) & np.isfinite(truth)
    if not eligible.any():
        raise ValueError("No eligible reference columns.")
    error = np.abs(prediction[eligible] - truth[eligible]) * spacing_um
    return {
        "eligible_columns": int(eligible.sum()),
        "median_absolute_error_um": float(np.median(error)),
        "p90_absolute_error_um": float(np.percentile(error, 90)),
        "within_15_um": float(np.mean(error <= 15.0)),
        "within_30_um": float(np.mean(error <= 30.0)),
        "within_60_um": float(np.mean(error <= 60.0)),
    }


def band_iou(predicted: np.ndarray, reference: np.ndarray, *, spacing_um: float, half_width_um: float = 75.0) -> float:
    prediction = np.asarray(predicted, dtype=float)
    truth = np.asarray(reference, dtype=float)
    eligible = np.isfinite(prediction) & np.isfinite(truth)
    if not eligible.any() or spacing_um <= 0:
        raise ValueError("Eligible paths and positive spacing are required.")
    half = half_width_um / spacing_um
    height = int(np.ceil(max(np.nanmax(prediction), np.nanmax(truth)) + half + 2))
    rows = np.arange(height)[:, None]
    p = (np.abs(rows - prediction[None, :]) <= half) & eligible[None, :]
    t = (np.abs(rows - truth[None, :]) <= half) & eligible[None, :]
    return float(np.logical_and(p, t).sum() / max(np.logical_or(p, t).sum(), 1))


def surface_flattened_band(
    image: np.ndarray, path: np.ndarray, *, spacing_um: float, width_um: float = 100.0
) -> np.ndarray:
    """Sample the non-calcified band immediately above a columnwise interface."""
    data = robust_normalize(image)
    boundary = np.asarray(path, dtype=float)
    if boundary.shape != (data.shape[1],) or spacing_um <= 0 or not np.isfinite(boundary).all():
        raise ValueError("Path must be finite, span the image width and have positive spacing.")
    samples = max(32, int(np.ceil(width_um / spacing_um)))
    offsets = np.linspace(samples, 1, samples)
    rows = boundary[None, :] - offsets[:, None]
    columns = np.broadcast_to(np.arange(data.shape[1], dtype=float), rows.shape)
    return ndimage.map_coordinates(data, (rows, columns), order=1, mode="nearest")


def band_measurements(image: np.ndarray, path: np.ndarray, *, spacing_um: float) -> dict[str, float]:
    band = surface_flattened_band(image, path, spacing_um=spacing_um)
    fft = extract_spatial_fft(band, pixel_size_um=spacing_um)
    tensor = structure_tensor_response(
        band, spacing_um=(spacing_um, spacing_um), scales_um=(12.8, 25.6)
    )
    variogram = directional_variogram(
        band, spacing_um=(spacing_um, spacing_um), separations_um=(25.6,)
    )
    horizontal, vertical = variogram.horizontal[0], variogram.vertical[0]
    anisotropy = abs(horizontal - vertical) / max(horizontal + vertical, np.finfo(float).eps)
    return {
        "normalized_mean_intensity": float(np.mean(band)),
        "normalized_intensity_sd": float(np.std(band)),
        "angular_spectral_entropy": float(fft.angular_entropy),
        "tensor_coherency_12_8_um": float(tensor.coherency[0]),
        "tensor_coherency_25_6_um": float(tensor.coherency[1]),
        "variogram_anisotropy_25_6_um": float(anisotropy),
    }


def concordance_correlation(x: np.ndarray, y: np.ndarray) -> float:
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    eligible = np.isfinite(a) & np.isfinite(b)
    a, b = a[eligible], b[eligible]
    if a.size < 3:
        return float("nan")
    covariance = float(np.mean((a - a.mean()) * (b - b.mean())))
    denominator = float(a.var() + b.var() + (a.mean() - b.mean()) ** 2)
    return float(2 * covariance / denominator) if denominator > 0 else float("nan")
