"""Acquisition diagnostics restricted to a declared instrument-support domain."""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def acquisition_qc_on_support(image: np.ndarray, support: np.ndarray) -> dict:
    """Calculate acquisition diagnostics without treating unsupported background as signal."""

    data = np.asarray(image, dtype=np.float64)
    domain = np.asarray(support, dtype=bool)
    if data.ndim != 2 or not np.isfinite(data).all():
        raise ValueError("Support-aware QC requires one finite 2-D image.")
    if domain.shape != data.shape:
        raise ValueError("The acquisition-support map must match the image shape.")
    support_pixels = int(np.sum(domain))
    if support_pixels == 0:
        raise ValueError("The acquisition-support map is empty.")

    values = data[domain]
    low, high = np.percentile(values, (1.0, 99.0))
    dynamic = float(high - low)
    variance = float(np.var(values))
    minimum, maximum = float(np.min(values)), float(np.max(values))
    endpoint_fraction = float(np.mean((values == minimum) | (values == maximum)))

    nearest = ndimage.distance_transform_edt(
        ~domain,
        return_distances=False,
        return_indices=True,
    )
    filled = data[tuple(nearest)]
    interior = ndimage.binary_erosion(domain, iterations=2, border_value=0)
    if int(np.sum(interior)) < min(256, support_pixels):
        interior = domain
    laplacian = ndimage.laplace(filled, mode="reflect")
    focus_score = float(np.var(laplacian[interior]) / max(variance, np.finfo(float).eps))
    sobel_energy = np.zeros_like(filled, dtype=np.float64)
    for axis in range(2):
        derivative = ndimage.sobel(filled, axis=axis, mode="reflect")
        sobel_energy += derivative * derivative
    tenengrad_focus = float(np.mean(sobel_energy[interior]))
    smooth = ndimage.gaussian_filter(filled, sigma=1.0, mode="reflect")
    residual = (filled - smooth)[interior]
    residual_mad = float(np.median(np.abs(residual - np.median(residual))))
    contrast_to_residual = float(dynamic / max(1.4826 * residual_mad, np.finfo(float).eps))

    flags: list[str] = []
    status = "pass"
    if dynamic <= np.finfo(float).eps:
        flags.append("LOW_DYNAMIC_RANGE")
        status = "abstain"
    if endpoint_fraction >= 0.20:
        flags.append("HIGH_ENDPOINT_FRACTION")
        if status == "pass":
            status = "review"
    return {
        "schema_version": "nostos-acquisition-qc-on-support/1.0",
        "status": status,
        "support_pixels": support_pixels,
        "support_fraction": float(support_pixels / data.size),
        "derivative_interior_pixels": int(np.sum(interior)),
        "robust_dynamic_range": dynamic,
        "variance": variance,
        "normalized_laplacian_focus": focus_score,
        "tenengrad_focus_v2": tenengrad_focus,
        "contrast_to_residual": contrast_to_residual,
        "observed_endpoint_fraction": endpoint_fraction,
        "flags": flags,
        "domain_policy": "R2/SNR acquisition support before measurement-level edge and energy exclusions",
        "outside_support_used": False,
        "interpretation": "Acquisition diagnostics only; thresholds are not tissue-quality or diagnostic criteria.",
    }
