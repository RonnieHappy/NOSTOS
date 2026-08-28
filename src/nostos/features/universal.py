"""Frozen sample-agnostic NOSTOS-0 analyzer."""
from __future__ import annotations

import hashlib

import numpy as np

from nostos.core.response import Axis, Calibration, ResponseGeometry, ResponseSurface
from nostos.core.qc import acquisition_qc

from .response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    local_thickness_response,
    structure_tensor_response,
)
from .spatial_fft import extract_spatial_fft


def _surface(module: str, measurement: str, axis: Axis, values: tuple[float, ...], *, unit: str = "dimensionless", validity: str = "valid", reasons: tuple[str, ...] = ()) -> ResponseSurface:
    return ResponseSurface(
        module=module,  # type: ignore[arg-type]
        measurement=measurement,
        axes=(axis,),
        values=values,
        shape=(len(values),),
        amplitude_unit=unit,
        validity=validity,  # type: ignore[arg-type]
        validity_reasons=reasons,
    )


def analyze_response_geometry(
    image: np.ndarray,
    *,
    spacing_um: tuple[float, ...],
    mask: np.ndarray | None = None,
    specimen_reference_um: float | None = None,
    specimen_direction_degrees: float = 0.0,
    spatial_unit: str = "um",
    scales_um: tuple[float, ...] | None = None,
    thresholds_um: tuple[float, ...] | None = None,
    separations_um: tuple[float, ...] | None = None,
) -> ResponseGeometry:
    """Measure a calibrated image without assigning tissue-specific meaning."""
    data = np.asarray(image, dtype=float)
    calibration = Calibration(
        spacing=spacing_um,
        spatial_unit=spatial_unit,  # type: ignore[arg-type]
        specimen_reference=specimen_reference_um,
        specimen_reference_name="declared_specimen_reference" if specimen_reference_um else None,
        specimen_direction_degrees=specimen_direction_degrees,
    )
    geometry = ResponseGeometry(
        calibration=calibration,
        input_dimensions=tuple(data.shape),
        provenance={
            "analyzer": "nostos.features.universal/analyze_response_geometry",
            "input_sha256": hashlib.sha256(np.ascontiguousarray(data).tobytes()).hexdigest(),
            "mask_supplied": mask is not None,
        },
    )
    quality = acquisition_qc(data)
    geometry.provenance["acquisition_qc"] = quality
    if quality["status"] == "abstain":
        geometry.abstain("LOW_DYNAMIC_RANGE", "The image has no robust intensity range.", "intensity_dependent_modules")
    minimum_spacing = min(spacing_um)
    if scales_um is None:
        scales_um = tuple(minimum_spacing * value for value in (2.0, 4.0, 8.0, 16.0))
    scale_axis = Axis("scale", scales_um, spatial_unit)

    if data.ndim == 2 and min(data.shape) >= 32:
        try:
            fft = extract_spatial_fft(data, pixel_size_um=float(np.mean(spacing_um)))
            geometry.add(_surface("spectral", "summary", Axis("other", (0, 1, 2, 3), "index"), (
                fft.orientation_degrees,
                fft.anisotropy,
                fft.angular_entropy,
                fft.characteristic_frequency_cycles_per_mm,
            )))
        except ValueError as error:
            geometry.abstain("SPECTRAL_UNSUPPORTED", str(error), "spectral.summary")
        try:
            tensor = structure_tensor_response(data, spacing_um=(spacing_um[0], spacing_um[1]), scales_um=scales_um)
            geometry.add(_surface("tensor", "orientation", scale_axis, tensor.orientation_degrees, unit="degrees"))
            geometry.add(_surface("tensor", "coherency", scale_axis, tensor.coherency))
        except ValueError as error:
            geometry.abstain("TENSOR_UNSUPPORTED", str(error), "tensor")

    try:
        hessian = hessian_morphology_response(data, spacing_um=spacing_um, scales_um=scales_um)
        geometry.add(_surface("hessian", "blob_response", scale_axis, hessian.blob))
        geometry.add(_surface("hessian", "tube_response", scale_axis, hessian.tube))
        geometry.add(_surface("hessian", "sheet_response", scale_axis, hessian.sheet))
    except ValueError as error:
        geometry.abstain("HESSIAN_UNSUPPORTED", str(error), "hessian")

    if mask is not None:
        binary = np.asarray(mask, dtype=bool)
        coverage = float(binary.mean())
        if coverage < 0.05:
            geometry.abstain("MASK_COVERAGE_LOW", "Eligible mask coverage is below 5 percent.", "geometry/network")
        else:
            thickness = local_thickness_response(binary, spacing_um=spacing_um)
            quantiles = tuple(float(v) for v in np.quantile(thickness.local_thickness_values_um, (0.05, 0.25, 0.5, 0.75, 0.95)))
            geometry.add(_surface("geometry", "thickness_quantiles", Axis("threshold", (0.05, 0.25, 0.5, 0.75, 0.95), "quantile"), quantiles, unit=spatial_unit))
            if thresholds_um is None:
                thresholds_um = tuple(minimum_spacing * value for value in (0, 1, 2, 4, 8))
            network = erosion_survival_response(binary, spacing_um=spacing_um, thresholds_um=thresholds_um, boundary_corrected=True)
            threshold_axis = Axis("threshold", thresholds_um, spatial_unit)
            geometry.add(_surface("network", "surviving_fraction_boundary_v2", threshold_axis, network.surviving_fraction))
            geometry.add(_surface("network", "component_count", threshold_axis, tuple(float(v) for v in network.component_count), unit="count"))
    else:
        geometry.abstain("MASK_NOT_SUPPLIED", "Geometry and network measurements require an eligible specimen mask.", "geometry/network")

    if data.ndim == 2:
        if separations_um is None:
            separations_um = tuple(minimum_spacing * value for value in (1, 2, 4, 8, 16, 24))
        try:
            spatial = directional_variogram(data, spacing_um=(spacing_um[0], spacing_um[1]), separations_um=separations_um)
            separation_axis = Axis("separation", separations_um, spatial_unit)
            geometry.add(_surface("spatial", "variogram_horizontal", separation_axis, spatial.horizontal, unit="intensity_squared"))
            geometry.add(_surface("spatial", "variogram_vertical", separation_axis, spatial.vertical, unit="intensity_squared"))
        except ValueError as error:
            geometry.abstain("SPATIAL_UNSUPPORTED", str(error), "spatial.variogram")
    return geometry
