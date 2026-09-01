"""Calibrated time-series measurements kept separate from spatial volumes."""
from __future__ import annotations

import hashlib

import numpy as np
from scipy.ndimage import map_coordinates, sobel
from skimage.registration import optical_flow_ilk, optical_flow_tvl1


DENSE_UNCERTAINTY_OFFSET_PIXELS = 0.3076263275029393

from nostos.core.response import Axis, Calibration, ResponseGeometry, ResponseSurface


def _phase_shift(reference: np.ndarray, moving: np.ndarray) -> tuple[np.ndarray, float]:
    """Return the integer shift that aligns ``moving`` to ``reference`` and peak quality."""
    first = np.asarray(reference, dtype=float)
    second = np.asarray(moving, dtype=float)
    first = first - float(first.mean())
    second = second - float(second.mean())
    if float(np.linalg.norm(first)) <= 1e-12 or float(np.linalg.norm(second)) <= 1e-12:
        raise ValueError("Phase correlation requires spatial contrast in both frames.")
    cross = np.fft.fftn(first) * np.conj(np.fft.fftn(second))
    magnitude = np.abs(cross)
    eligible = magnitude > np.finfo(float).eps
    cross[eligible] /= magnitude[eligible]
    cross[~eligible] = 0
    correlation = np.abs(np.fft.ifftn(cross))
    peak_index = np.asarray(np.unravel_index(int(np.argmax(correlation)), correlation.shape), dtype=float)
    shape = np.asarray(correlation.shape, dtype=float)
    shift = np.where(peak_index > np.floor(shape / 2.0), peak_index - shape, peak_index)
    quality = float(correlation.max() / max(float(np.mean(correlation)), np.finfo(float).eps))
    return shift, quality


def _robust_normalize(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float32)
    low, high = np.percentile(data, (1.0, 99.0))
    if not np.isfinite((low, high)).all() or float(high - low) <= np.finfo(np.float32).eps:
        raise ValueError("Dense deformation requires nonconstant robust intensity support in both frames.")
    return np.clip((data - low) / float(high - low), 0.0, 1.0)


def _sample_vector_field(field: np.ndarray, coordinates: np.ndarray) -> np.ndarray:
    return np.stack([
        map_coordinates(component, coordinates, order=1, mode="constant", cval=np.nan)
        for component in field
    ])


def dense_deformation_pair(
    reference: np.ndarray,
    moving: np.ndarray,
    *,
    minimum_gradient: float = 0.01,
    maximum_forward_backward_error: float = 2.0,
) -> dict[str, np.ndarray]:
    """Estimate 2-D displacement and label-free reliability for one frame pair.

    Returned flow maps coordinates in ``reference`` to their locations in ``moving``.
    Forward-backward inconsistency is measured after sampling the reverse field at
    those target coordinates. Values are in pixels until calibrated by the caller.
    """
    first = _robust_normalize(reference)
    second = _robust_normalize(moving)
    if first.ndim != 2 or second.shape != first.shape:
        raise ValueError("Dense deformation currently requires two shape-matched 2-D frames.")
    forward = np.asarray(optical_flow_tvl1(first, second, prefilter=True), dtype=float)
    reverse = np.asarray(optical_flow_tvl1(second, first, prefilter=True), dtype=float)
    comparator = np.asarray(
        optical_flow_ilk(first, second, radius=7, num_warp=10, gaussian=True, prefilter=True),
        dtype=float,
    )
    yy, xx = np.mgrid[: first.shape[0], : first.shape[1]]
    target = np.stack((yy + forward[0], xx + forward[1]))
    reverse_at_target = _sample_vector_field(reverse, target)
    inconsistency = np.sqrt(np.sum((forward + reverse_at_target) ** 2, axis=0))
    gradient = np.hypot(sobel(first, axis=0, mode="reflect"), sobel(first, axis=1, mode="reflect")) / 8.0
    inside = (
        (target[0] >= 0.0) & (target[0] <= first.shape[0] - 1.0)
        & (target[1] >= 0.0) & (target[1] <= first.shape[1] - 1.0)
    )
    eligible = inside & np.isfinite(inconsistency) & (gradient >= minimum_gradient) & (
        inconsistency <= maximum_forward_backward_error
    )
    return {
        "flow_pixels": forward,
        "comparator_flow_pixels": comparator,
        "forward_backward_error_pixels": inconsistency,
        "uncertainty_upper_bound_pixels": np.hypot(forward[0] - comparator[0], forward[1] - comparator[1])
        + DENSE_UNCERTAINTY_OFFSET_PIXELS,
        "gradient_energy": gradient,
        "eligible": eligible,
    }


def analyze_dense_deformation(
    series: np.ndarray,
    *,
    spacing: tuple[float, float],
    temporal_spacing: float,
    spatial_unit: str = "um",
    temporal_unit: str = "s",
    field_stride: int = 4,
    minimum_eligible_fraction: float = 0.20,
) -> ResponseGeometry:
    """Measure calibrated 2-D+t dense deformation with reliability and abstention."""
    data = np.asarray(series, dtype=float)
    if data.ndim != 3 or data.shape[0] < 2 or min(data.shape[1:]) < 32:
        raise ValueError("Dense deformation requires shape (time, y, x), at least two 32 x 32 frames.")
    if len(spacing) != 2 or field_stride < 1:
        raise ValueError("Dense deformation requires two spacing values and a positive field stride.")
    calibration = Calibration(
        spacing=spacing, spatial_unit=spatial_unit, temporal_spacing=temporal_spacing,
        temporal_unit=temporal_unit,
    )
    geometry = ResponseGeometry(
        calibration=calibration, input_dimensions=tuple(data.shape),
        provenance={
            "analyzer": "nostos.features.dynamic/analyze_dense_deformation",
            "input_sha256": hashlib.sha256(np.ascontiguousarray(data).tobytes()).hexdigest(),
            "time_axis": 0, "endpoint": "frame_to_frame_dense_deformation",
            "estimator": "scikit-image optical_flow_tvl1 0.25.2",
            "eligibility": "forward_backward_inconsistency_and_gradient_support",
            "uncertainty": "tvl1_ilk_disagreement_plus_frozen_analytic_conformal_offset",
            "uncertainty_offset_pixels": DENSE_UNCERTAINTY_OFFSET_PIXELS,
            "field_stride": field_stride,
            "minimum_eligible_fraction": minimum_eligible_fraction,
        },
    )
    pair_results: list[dict[str, np.ndarray]] = []
    pair_indices: list[int] = []
    for index in range(data.shape[0] - 1):
        try:
            result = dense_deformation_pair(data[index], data[index + 1])
        except ValueError as error:
            geometry.abstain("DENSE_DEFORMATION_LOW_INFORMATION", str(error), f"dynamic.frame_{index + 1}")
            continue
        fraction = float(np.mean(result["eligible"]))
        if fraction < minimum_eligible_fraction:
            geometry.abstain(
                "DENSE_DEFORMATION_INSUFFICIENT_SUPPORT",
                f"Eligible fraction {fraction:.4f} is below {minimum_eligible_fraction:.4f}.",
                f"dynamic.frame_{index + 1}",
            )
            continue
        pair_results.append(result)
        pair_indices.append(index)
    if not pair_results:
        return geometry

    ys = np.arange(0, data.shape[1], field_stride)
    xs = np.arange(0, data.shape[2], field_stride)
    time_axis = Axis("time", tuple(float((i + 1) * temporal_spacing) for i in pair_indices), temporal_unit)
    y_axis = Axis("other", tuple(float(y * spacing[0]) for y in ys), spatial_unit)
    x_axis = Axis("other", tuple(float(x * spacing[1]) for x in xs), spatial_unit)
    axes = (time_axis, y_axis, x_axis)
    shape = (len(pair_results), len(ys), len(xs))
    sampled_flow = np.stack([item["flow_pixels"][:, ::field_stride, ::field_stride] for item in pair_results])
    sampled_uncertainty = np.stack([item["uncertainty_upper_bound_pixels"][::field_stride, ::field_stride] for item in pair_results])
    sampled_uncertainty = np.nan_to_num(sampled_uncertainty, nan=4.0, posinf=4.0, neginf=4.0)
    sampled_eligible = np.stack([item["eligible"][::field_stride, ::field_stride] for item in pair_results])
    physical_y = sampled_flow[:, 0] * spacing[0]
    physical_x = sampled_flow[:, 1] * spacing[1]
    sampled_comparator = np.stack([item["comparator_flow_pixels"][:, ::field_stride, ::field_stride] for item in pair_results])
    physical_uncertainty = np.hypot(
        (sampled_flow[:, 0] - sampled_comparator[:, 0]) * spacing[0],
        (sampled_flow[:, 1] - sampled_comparator[:, 1]) * spacing[1],
    ) + DENSE_UNCERTAINTY_OFFSET_PIXELS * max(spacing)
    magnitude = np.hypot(physical_y, physical_x)
    common = {
        "module": "dynamic", "axes": axes, "shape": shape,
        "uncertainty": tuple(float(value) for value in physical_uncertainty.ravel()),
    }
    geometry.add(ResponseSurface(
        measurement="dense_displacement_y", values=tuple(float(v) for v in physical_y.ravel()),
        amplitude_unit=spatial_unit, **common,
    ))
    geometry.add(ResponseSurface(
        measurement="dense_displacement_x", values=tuple(float(v) for v in physical_x.ravel()),
        amplitude_unit=spatial_unit, **common,
    ))
    geometry.add(ResponseSurface(
        measurement="dense_displacement_magnitude", values=tuple(float(v) for v in magnitude.ravel()),
        amplitude_unit=spatial_unit, **common,
    ))
    geometry.add(ResponseSurface(
        module="dynamic", measurement="dense_eligible", axes=axes,
        values=tuple(float(v) for v in sampled_eligible.ravel()), shape=shape,
    ))
    return geometry


def analyze_time_series(
    series: np.ndarray,
    *,
    spacing: tuple[float, ...],
    temporal_spacing: float,
    spatial_unit: str = "um",
    temporal_unit: str = "s",
    minimum_peak_ratio: float = 5.0,
) -> ResponseGeometry:
    """Measure frame-to-frame bulk translation in an explicit 2-D+t or 3-D+t array.

    The first axis is always time. Reported vectors are sample displacement from the
    preceding frame, not the registration shift applied to align the frames.
    """
    data = np.asarray(series, dtype=float)
    if data.ndim not in {3, 4}:
        raise ValueError("A time series must have shape (time, y, x) or (time, z, y, x).")
    if data.shape[0] < 2 or min(data.shape[1:]) < 8:
        raise ValueError("A time series requires at least two frames and eight samples per spatial axis.")
    if len(spacing) != data.ndim - 1:
        raise ValueError("Spatial spacing must match the number of spatial dimensions.")
    calibration = Calibration(
        spacing=spacing,
        spatial_unit=spatial_unit,  # type: ignore[arg-type]
        temporal_spacing=temporal_spacing,
        temporal_unit=temporal_unit,
    )
    geometry = ResponseGeometry(
        calibration=calibration,
        input_dimensions=tuple(data.shape),
        provenance={
            "analyzer": "nostos.features.dynamic/analyze_time_series",
            "input_sha256": hashlib.sha256(np.ascontiguousarray(data).tobytes()).hexdigest(),
            "time_axis": 0,
            "endpoint": "frame_to_frame_bulk_translation",
        },
    )
    shifts: list[np.ndarray] = []
    qualities: list[float] = []
    for index in range(data.shape[0] - 1):
        try:
            alignment, quality = _phase_shift(data[index], data[index + 1])
        except ValueError as error:
            geometry.abstain("DYNAMIC_LOW_INFORMATION", str(error), f"dynamic.frame_{index + 1}")
            continue
        qualities.append(quality)
        shifts.append(-alignment * np.asarray(spacing, dtype=float))
    if not shifts:
        return geometry
    time_values = tuple(float((index + 1) * temporal_spacing) for index in range(len(shifts)))
    time_axis = Axis("time", time_values, temporal_unit)
    matrix = np.asarray(shifts)
    for dimension, name in enumerate(("z", "y", "x")[-matrix.shape[1]:]):
        values = tuple(float(value) for value in matrix[:, dimension])
        validity = "valid" if min(qualities) >= minimum_peak_ratio else "review"
        reasons = () if validity == "valid" else ("phase_correlation_peak_below_declared_threshold",)
        geometry.add(ResponseSurface(
            module="dynamic",
            measurement=f"displacement_{name}",
            axes=(time_axis,), values=values, shape=(len(values),),
            amplitude_unit=spatial_unit, validity=validity, validity_reasons=reasons,
        ))
    geometry.add(ResponseSurface(
        module="dynamic", measurement="phase_peak_ratio", axes=(time_axis,),
        values=tuple(qualities), shape=(len(qualities),), validity="valid",
    ))
    return geometry
