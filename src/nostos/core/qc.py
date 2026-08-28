"""Sample-agnostic acquisition diagnostics with explicit non-diagnostic scope."""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def acquisition_qc(image: np.ndarray) -> dict:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim not in {2, 3} or not np.isfinite(data).all():
        raise ValueError("QC requires a finite 2-D image or 3-D volume.")
    low, high = np.percentile(data, (1, 99))
    dynamic = float(high - low)
    variance = float(np.var(data))
    minimum, maximum = float(data.min()), float(data.max())
    endpoint_fraction = float(np.mean((data == minimum) | (data == maximum)))
    if data.ndim == 2:
        laplacian = ndimage.laplace(data, mode="reflect")
    else:
        laplacian = sum(ndimage.convolve1d(data, np.asarray([1.0, -2.0, 1.0]), axis=axis, mode="reflect") for axis in range(3))
    focus_score = float(np.var(laplacian) / max(variance, np.finfo(float).eps))
    sobel_energy = np.zeros_like(data, dtype=np.float64)
    for axis in range(data.ndim):
        derivative = ndimage.sobel(data, axis=axis, mode="reflect")
        sobel_energy += derivative * derivative
    tenengrad_focus = float(np.mean(sobel_energy))
    smooth = ndimage.gaussian_filter(data, sigma=1.0, mode="reflect")
    residual_mad = float(np.median(np.abs((data - smooth) - np.median(data - smooth))))
    contrast_to_residual = float(dynamic / max(1.4826 * residual_mad, np.finfo(float).eps))
    flags = []
    status = "pass"
    if dynamic <= np.finfo(float).eps:
        flags.append("LOW_DYNAMIC_RANGE")
        status = "abstain"
    if endpoint_fraction >= 0.20:
        flags.append("HIGH_ENDPOINT_FRACTION")
        if status == "pass":
            status = "review"
    return {
        "schema_version": "nostos-acquisition-qc/1.0", "status": status,
        "robust_dynamic_range": dynamic, "variance": variance,
        "normalized_laplacian_focus": focus_score,
        "tenengrad_focus_v2": tenengrad_focus,
        "contrast_to_residual": contrast_to_residual,
        "observed_endpoint_fraction": endpoint_fraction,
        "flags": flags,
        "interpretation": "Acquisition diagnostics only; thresholds are not tissue-quality or diagnostic criteria.",
    }
