"""Frozen building blocks for the Heaton in-vivo SHG transfer benchmark."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

from nostos.features.response_modules import structure_tensor_response
from nostos.features.shg_fiber_adapter import shg_fiber_adapter
from nostos.features.skeleton_geometry import skeleton_geometry_response
from nostos.intraop.support_qc import acquisition_qc_on_support


ENDPOINTS = (
    "axial_resultant",
    "foreground_occupancy",
    "median_segment_straightness",
    "median_segment_length_um",
    "median_local_width_um",
)


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _axial_difference(first: float, second: float) -> float:
    return float(abs((first - second + 90.0) % 180.0 - 90.0))


def select_perturbation_fields(
    rows: Sequence[Mapping[str, Any]],
    *,
    salt: str = "nostos-heaton-shg-perturb-v1",
) -> list[dict[str, Any]]:
    """Select one field per mouse without reading image pixels."""

    mice = sorted({str(row["mouse"]) for row in rows})
    selected = []
    for mouse in mice:
        candidates = [dict(row) for row in rows if str(row["mouse"]) == mouse]
        candidates.sort(
            key=lambda row: hashlib.sha256(
                f"{salt}|{row['source']}".encode("utf-8")
            ).hexdigest()
        )
        selected.append(candidates[0])
    return selected


def _resize_back(image: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return np.asarray(image, dtype=np.float64).copy()
    height, width = image.shape
    small = ndimage.zoom(
        image,
        zoom=(1.0 / factor, 1.0 / factor),
        order=1,
        mode="reflect",
        prefilter=False,
    )
    return ndimage.zoom(
        small,
        zoom=(height / small.shape[0], width / small.shape[1]),
        order=1,
        mode="reflect",
        prefilter=False,
    )[:height, :width]


def apply_condition(
    image: np.ndarray,
    condition: Mapping[str, Any],
    *,
    field_id: str,
    seed: int,
) -> np.ndarray:
    shifted = np.asarray(image, dtype=np.float64).copy()
    blur = float(condition.get("blur_sigma_px", 0.0))
    if blur > 0:
        shifted = ndimage.gaussian_filter(shifted, sigma=blur, mode="reflect")
    resample = int(condition.get("resample_factor", 1))
    if resample > 1:
        shifted = _resize_back(shifted, resample)
    contrast = float(condition.get("contrast_factor", 1.0))
    if contrast != 1.0:
        median = float(np.median(shifted))
        shifted = median + contrast * (shifted - median)
    target_snr = condition.get("noise_snr_db")
    if target_snr is not None:
        rng = np.random.default_rng(_stable_seed(seed, field_id, condition["id"]))
        scale = float(np.std(shifted)) / (10.0 ** (float(target_snr) / 20.0))
        shifted = shifted + rng.normal(0.0, scale, size=shifted.shape)
    crop_fraction = float(condition.get("crop_fraction", 1.0))
    if crop_fraction < 1.0:
        if not 0.0 < crop_fraction < 1.0:
            raise ValueError("crop_fraction must be inside (0, 1].")
        target = tuple(max(16, int(round(size * crop_fraction))) for size in shifted.shape)
        starts = tuple((size - width) // 2 for size, width in zip(shifted.shape, target, strict=True))
        shifted = shifted[tuple(slice(start, start + width) for start, width in zip(starts, target, strict=True))]
    return np.maximum(shifted, 0.0)


def adapter_grid(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    measurement = config["measurement"]
    grid = measurement["adapter_development_grids"]
    output = []
    for radius in grid["background_opening_radius_um"]:
        for scales in grid["ridge_scales_um"]:
            for quantile in grid["foreground_quantile"]:
                for minimum_length in grid["minimum_component_length_um"]:
                    output.append(
                        {
                            "background_opening_radius_um": float(radius),
                            "ridge_scales_um": tuple(float(value) for value in scales),
                            "foreground_quantile": float(quantile),
                            "minimum_component_length_um": float(minimum_length),
                        }
                    )
    return output


def _measure_core(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    params: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    measurement = config["measurement"]
    adapter = shg_fiber_adapter(
        image,
        spacing_um=spacing_um,
        background_opening_radius_um=float(params["background_opening_radius_um"]),
        ridge_scales_um=tuple(float(value) for value in params["ridge_scales_um"]),
        foreground_quantile=float(params["foreground_quantile"]),
        minimum_object_area_pixels=int(measurement["minimum_object_area_pixels"]),
        normalization_percentiles=tuple(float(value) for value in measurement["normalization_percentiles"]),
    )
    tensor = structure_tensor_response(
        adapter.background_corrected_image,
        spacing_um=spacing_um,
        scales_um=tuple(float(value) for value in measurement["tensor_scales_um"]),
    )
    geometry = skeleton_geometry_response(
        adapter.mask,
        spacing_um=spacing_um,
        minimum_segment_length_um=float(params["minimum_component_length_um"]),
    )
    endpoints = {
        "axial_resultant": float(np.median(tensor.orientation_resultant)),
        "foreground_occupancy": float(adapter.foreground_fraction),
        "median_segment_straightness": geometry.median_segment_straightness,
        "median_segment_length_um": geometry.median_segment_length_um,
        "median_local_width_um": geometry.median_local_width_um,
    }
    complete = all(value is not None and np.isfinite(value) for value in endpoints.values())
    return {
        "endpoints": endpoints,
        "complete": bool(complete),
        "adapter_status": adapter.status,
        "adapter_flags": list(adapter.flags),
        "foreground_fraction": adapter.foreground_fraction,
        "segment_count": geometry.segment_count,
        "tensor_scales_um": list(tensor.scales_um),
        "tensor_orientation_degrees": list(tensor.orientation_degrees),
        "tensor_coherency": list(tensor.coherency),
        "tensor_resultant": list(tensor.orientation_resultant),
        "method": {
            "adapter": "physical_bright_ridge_v1",
            "tensor": "physical_structure_tensor_v1",
            "geometry": geometry.method,
        },
    }


def _endpoint_drift(first: Mapping[str, float | None], second: Mapping[str, float | None]) -> float:
    values = []
    for endpoint in ENDPOINTS:
        a, b = first.get(endpoint), second.get(endpoint)
        if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
            return float("inf")
        if endpoint in {"axial_resultant", "median_segment_straightness"}:
            values.append(abs(float(a) - float(b)) / 0.10)
        else:
            values.append(abs(float(a) - float(b)) / max(abs(float(a)), np.finfo(float).eps) / 0.25)
    return float(max(values))


def _acquisition_score(qc: Mapping[str, Any]) -> float:
    if qc["status"] == "abstain":
        return 10.0
    residual = 3.0 / max(float(qc["contrast_to_residual"]), np.finfo(float).eps)
    endpoints = float(qc["observed_endpoint_fraction"]) / 0.20
    focus = 1.0 / (1.0 + 20.0 * math.sqrt(max(float(qc["tenengrad_focus_v2"]), 0.0)))
    return float(max(residual, endpoints, focus))


def measure_shg_field(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    params: Mapping[str, Any],
    config: Mapping[str, Any],
    internal_checks: bool = True,
) -> dict[str, Any]:
    """Measure one field and emit input-only validity scores."""

    core = _measure_core(image, spacing_um=spacing_um, params=params, config=config)
    if not internal_checks:
        return core
    normalized = shg_fiber_adapter(
        image,
        spacing_um=spacing_um,
        background_opening_radius_um=float(params["background_opening_radius_um"]),
        ridge_scales_um=tuple(float(value) for value in params["ridge_scales_um"]),
        foreground_quantile=float(params["foreground_quantile"]),
        minimum_object_area_pixels=int(config["measurement"]["minimum_object_area_pixels"]),
        normalization_percentiles=tuple(float(value) for value in config["measurement"]["normalization_percentiles"]),
    ).normalized_image
    qc = acquisition_qc_on_support(normalized, np.ones(normalized.shape, dtype=bool))
    scale_angles = core["tensor_orientation_degrees"]
    scale_resultants = core["tensor_resultant"]
    scale_score = max(
        max(_axial_difference(float(a), float(b)) for a, b in zip(scale_angles[:-1], scale_angles[1:], strict=True)) / 20.0,
        (max(scale_resultants) - min(scale_resultants)) / 0.15,
    )
    support = float(core["foreground_fraction"])
    support_score = max(0.01 / max(support, np.finfo(float).eps), support / 0.60)
    segment_score = 10.0 / max(int(core["segment_count"]), 1)

    threshold_scores = []
    for delta in (-0.05, 0.05):
        neighbour = dict(params)
        neighbour["foreground_quantile"] = float(np.clip(float(params["foreground_quantile"]) + delta, 0.01, 0.99))
        measured = _measure_core(image, spacing_um=spacing_um, params=neighbour, config=config)
        threshold_scores.append(_endpoint_drift(core["endpoints"], measured["endpoints"]))
    threshold_score = max(threshold_scores)

    height, width = image.shape
    dy, dx = int(round(height * 0.125)), int(round(width * 0.125))
    nested_image = np.asarray(image)[dy : height - dy, dx : width - dx]
    nested = _measure_core(nested_image, spacing_um=spacing_um, params=params, config=config)
    nested_score = _endpoint_drift(core["endpoints"], nested["endpoints"])
    components = {
        "acquisition_qc": _acquisition_score(qc),
        "endpoint_support": float(max(support_score, segment_score)),
        "scale_consistency": float(scale_score),
        "threshold_consistency": float(threshold_score),
        "nested_support_consistency": float(nested_score),
    }
    scores = {
        "always_emit": 0.0,
        "acquisition_qc": components["acquisition_qc"],
        "endpoint_qc": max(components["acquisition_qc"], components["endpoint_support"]),
        "without_scale_consistency": max(value for key, value in components.items() if key != "scale_consistency"),
        "without_threshold_consistency": max(value for key, value in components.items() if key != "threshold_consistency"),
        "without_nested_consistency": max(value for key, value in components.items() if key != "nested_support_consistency"),
        "full_contract": max(components.values()),
    }
    hard_abstention = bool(not core["complete"] or core["adapter_status"] == "abstain")
    return {
        **core,
        "acquisition_qc": qc,
        "risk_components": components,
        "scores": scores,
        "hard_abstention": hard_abstention,
    }


__all__ = [
    "ENDPOINTS",
    "adapter_grid",
    "apply_condition",
    "measure_shg_field",
    "select_perturbation_fields",
]

