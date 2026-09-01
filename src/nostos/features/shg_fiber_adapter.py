"""Deterministic, validity-reporting adapter for bright-fiber SHG images."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage.filters import frangi
from skimage.morphology import disk, remove_small_objects, white_tophat


@dataclass(frozen=True)
class SHGFiberAdapterResult:
    normalized_image: np.ndarray
    background_corrected_image: np.ndarray
    ridge_response: np.ndarray
    mask: np.ndarray
    foreground_fraction: float
    low_percentile: float
    high_percentile: float
    threshold: float
    finite_fraction: float
    endpoint_fraction: float
    flags: tuple[str, ...]
    status: str


def _normalize(image: np.ndarray, percentiles: tuple[float, float]) -> tuple[np.ndarray, float, float, float, float]:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2:
        raise ValueError("The SHG adapter requires one two-dimensional field.")
    finite = np.isfinite(data)
    finite_fraction = float(np.mean(finite))
    if not finite.any():
        raise ValueError("The SHG field contains no finite samples.")
    filled = data.copy()
    filled[~finite] = float(np.median(filled[finite]))
    low_q, high_q = (float(value) for value in percentiles)
    if not (0.0 <= low_q < high_q <= 100.0):
        raise ValueError("normalization percentiles must be ordered inside [0, 100].")
    low, high = np.percentile(filled, (low_q, high_q))
    dynamic = float(high - low)
    if dynamic <= np.finfo(float).eps:
        normalized = np.zeros_like(filled)
    else:
        normalized = np.clip((filled - low) / dynamic, 0.0, 1.0)
    endpoint_fraction = float(np.mean((normalized <= 0.0) | (normalized >= 1.0)))
    return normalized, float(low), float(high), finite_fraction, endpoint_fraction


def shg_fiber_adapter(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    background_opening_radius_um: float,
    ridge_scales_um: tuple[float, ...],
    foreground_quantile: float,
    minimum_object_area_pixels: int = 16,
    normalization_percentiles: tuple[float, float] = (1.0, 99.5),
) -> SHGFiberAdapterResult:
    """Produce a generic bright-ridge support and explicit adapter flags.

    Parameters are expressed in physical units except for the declared minimum
    digital object area.  Tissue identity and biological labels are never used.
    """

    spacing = np.asarray(spacing_um, dtype=float)
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or np.any(spacing <= 0):
        raise ValueError("spacing_um must contain two finite positive values.")
    if not np.isfinite(background_opening_radius_um) or background_opening_radius_um <= 0:
        raise ValueError("background_opening_radius_um must be finite and positive.")
    scales = np.asarray(ridge_scales_um, dtype=float)
    if scales.ndim != 1 or not scales.size or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("ridge_scales_um must be a finite positive sequence.")
    if not 0.0 < foreground_quantile < 1.0:
        raise ValueError("foreground_quantile must be inside (0, 1).")
    if minimum_object_area_pixels < 1:
        raise ValueError("minimum_object_area_pixels must be positive.")

    normalized, low, high, finite_fraction, endpoint_fraction = _normalize(
        image, normalization_percentiles
    )
    radius_px = max(1, int(round(background_opening_radius_um / float(np.sqrt(np.prod(spacing))))))
    corrected = white_tophat(normalized, footprint=disk(radius_px))
    maximum = float(np.max(corrected))
    if maximum > np.finfo(float).eps:
        corrected = corrected / maximum
    pixel_scales = tuple(float(scale / np.sqrt(np.prod(spacing))) for scale in scales)
    response = frangi(
        corrected,
        sigmas=pixel_scales,
        black_ridges=False,
        mode="reflect",
    )
    positive = response[np.isfinite(response) & (response > 0)]
    threshold = float(np.quantile(positive, foreground_quantile)) if positive.size else float("inf")
    mask = np.isfinite(response) & (response >= threshold)
    mask = remove_small_objects(mask, min_size=int(minimum_object_area_pixels), connectivity=2)

    foreground_fraction = float(np.mean(mask))
    flags: list[str] = []
    if finite_fraction < 1.0:
        flags.append("NONFINITE_INPUT_REPAIRED")
    if high <= low + np.finfo(float).eps:
        flags.append("LOW_DYNAMIC_RANGE")
    if endpoint_fraction >= 0.20:
        flags.append("HIGH_ENDPOINT_FRACTION")
    if foreground_fraction < 0.01:
        flags.append("INSUFFICIENT_FOREGROUND_SUPPORT")
    if foreground_fraction > 0.60:
        flags.append("EXCESSIVE_FOREGROUND_SUPPORT")
    status = "abstain" if any(flag in {"LOW_DYNAMIC_RANGE", "INSUFFICIENT_FOREGROUND_SUPPORT", "EXCESSIVE_FOREGROUND_SUPPORT"} for flag in flags) else ("review" if flags else "pass")
    return SHGFiberAdapterResult(
        normalized_image=normalized,
        background_corrected_image=corrected,
        ridge_response=np.asarray(response, dtype=np.float64),
        mask=np.asarray(mask, dtype=bool),
        foreground_fraction=foreground_fraction,
        low_percentile=low,
        high_percentile=high,
        threshold=threshold,
        finite_fraction=finite_fraction,
        endpoint_fraction=endpoint_fraction,
        flags=tuple(flags),
        status=status,
    )


__all__ = ["SHGFiberAdapterResult", "shg_fiber_adapter"]
