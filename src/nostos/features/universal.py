"""Frozen sample-agnostic NOSTOS-0 analyzer."""
from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np

from nostos.core.response import Axis, Calibration, ResponseGeometry, ResponseSurface
from nostos.core.measurement_profile import MeasurementProfile
from nostos.core.qc import acquisition_qc

from .response_modules import (
    directional_variogram,
    erosion_survival_response,
    local_thickness_response,
    structure_tensor_response,
)
from .spatial_fft import extract_spatial_fft
from .validated_responses_v2_6 import (
    validated_boundary_robust_gradient_anisotropy_2d,
    validated_hessian_morphology,
)


_VALIDATED_CORE_V2_6 = {
    "profile": "nostos-validated-responses/2.6",
    "confirmation": "outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json",
    "confirmation_sha256": "f64b85c86f8e415526d2938618cdbda4974bad0094082c44713f52230f2001fc",
    "independent_audit": "outputs/nostos0-synthetic-physical-truth-v2-6-audit/audit.json",
    "independent_audit_sha256": "4bec5fb5ccebf233df61e34908493d1a53d6940ace0e0f9761bccf257ec9f501",
    "claim_boundary": "synthetic_physical_truth_only",
}


def _surface(
    module: str,
    measurement: str,
    axis: Axis,
    values: tuple[float, ...],
    *,
    unit: str = "dimensionless",
    validity: str = "valid",
    reasons: tuple[str, ...] = (),
    validity_mask: tuple[bool, ...] | None = None,
    validity_reasons_by_value: tuple[tuple[str, ...], ...] | None = None,
) -> ResponseSurface:
    return ResponseSurface(
        module=module,  # type: ignore[arg-type]
        measurement=measurement,
        axes=(axis,),
        values=values,
        shape=(len(values),),
        amplitude_unit=unit,
        validity=validity,  # type: ignore[arg-type]
        validity_reasons=reasons,
        validity_mask=validity_mask,
        validity_reasons_by_value=validity_reasons_by_value,
    )


def _scalar_surface(module: str, measurement: str, value: float, *, unit: str = "dimensionless") -> ResponseSurface:
    return _surface(module, measurement, Axis("other", (0.0,), "singleton"), (float(value),), unit=unit)


def _axial_difference(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return float(min(difference, 180.0 - difference))


def _robust_unit(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float64)
    low, high = np.percentile(data, (1.0, 99.0))
    if not np.isfinite((low, high)).all() or high <= low:
        raise ValueError("The image has no robust intensity range.")
    return np.clip((data - low) / (high - low), 0.0, 1.0)


def _l2_shape(values: tuple[float, ...]) -> tuple[float, ...]:
    curve = np.asarray(values, dtype=np.float64)
    norm = float(np.linalg.norm(curve))
    if not np.isfinite(curve).all() or norm <= np.finfo(float).eps:
        return tuple(float(0.0) for _ in curve)
    return tuple(float(value) for value in curve / norm)


def _fft_spacing_um(spacing: tuple[float, ...], spatial_unit: str) -> float:
    mean_spacing = float(np.mean(spacing))
    if spatial_unit == "um":
        return mean_spacing
    if spatial_unit in {"mm", "relative"}:
        return 1000.0 * mean_spacing
    raise ValueError(f"Unsupported spatial unit: {spatial_unit}")


_PROFILE_ENDPOINTS = {
    ("spectral", "anisotropy"): "spectral_anisotropy",
    ("spectral", "angular_entropy"): "spectral_entropy",
    ("spectral", "characteristic_wavelength"): "spectral_scale",
    ("tensor", "orientation"): "tensor_orientation",
    ("tensor", "coherency"): "tensor_coherence",
    ("hessian", "blob_shape"): "hessian_blob_curve",
    ("hessian", "tube_shape"): "hessian_tube_curve",
    ("hessian", "blob_scale"): "hessian_blob_scale",
    ("hessian", "tube_scale"): "hessian_tube_scale",
    ("spatial", "variogram_horizontal_shape"): "variogram_horizontal_curve",
    ("spatial", "variogram_vertical_shape"): "variogram_vertical_curve",
    ("spatial", "variogram_range_horizontal"): "variogram_range_horizontal",
    ("spatial", "variogram_range_vertical"): "variogram_range_vertical",
}


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
    measurement_profile: MeasurementProfile | None = None,
) -> ResponseGeometry:
    """Measure a calibrated image without assigning tissue-specific meaning."""
    data = np.asarray(image, dtype=float)
    minimum_spacing = min(spacing_um)
    if scales_um is None:
        scales_um = (
            measurement_profile.analysis_scales
            if measurement_profile is not None and measurement_profile.analysis_scales is not None
            else tuple(minimum_spacing * value for value in (2.0, 4.0, 8.0, 16.0))
        )
    profile_reasons = (
        ()
        if measurement_profile is None
        else measurement_profile.compatibility_reasons(
            input_dimensions=data.ndim,
            spacing=spacing_um,
            spatial_unit=spatial_unit,
            analysis_scales=scales_um,
        )
    )
    profile_compatible = measurement_profile is not None and not profile_reasons
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
            "validated_core_v2_6": dict(_VALIDATED_CORE_V2_6),
            "measurement_profile": (
                None
                if measurement_profile is None
                else {
                    "profile_id": measurement_profile.profile_id,
                    "status": measurement_profile.status,
                    "source_path": measurement_profile.source_path,
                    "source_sha256": measurement_profile.source_sha256,
                    "verified_artifacts": [
                        {"path": path, "sha256": sha256}
                        for path, sha256 in measurement_profile.verified_artifacts
                    ],
                    "machine_compatibility": (
                        "compatible" if profile_compatible else "incompatible"
                    ),
                    "compatibility_reasons": list(profile_reasons),
                    "unverifiable_requirement": measurement_profile.required_input_construction,
                }
            ),
        },
    )
    if measurement_profile is not None and profile_reasons:
        geometry.abstain(
            "ACQUISITION_PROFILE_INCOMPATIBLE",
            "; ".join(profile_reasons),
            "profile_evidence",
        )

    def add_profiled(surface: ResponseSurface) -> None:
        endpoint = _PROFILE_ENDPOINTS.get((surface.module, surface.measurement))
        disabled_reason = (
            None
            if not profile_compatible or measurement_profile is None
            else measurement_profile.disabled_reason(endpoint)
        )
        if disabled_reason is not None:
            geometry.abstain(
                "ACQUISITION_PROFILE_DISABLED",
                disabled_reason,
                f"{surface.module}.{surface.measurement}",
            )
            return
        evidence_status = (
            "unvalidated"
            if not profile_compatible or measurement_profile is None
            else measurement_profile.evidence_status(endpoint)
        )
        geometry.add(
            replace(
                surface,
                evidence_status=evidence_status,  # type: ignore[arg-type]
                evidence_profile_id=(
                    None
                    if evidence_status == "unvalidated" or measurement_profile is None
                    else measurement_profile.profile_id
                ),
            )
        )

    quality = acquisition_qc(data)
    geometry.provenance["acquisition_qc"] = quality
    try:
        analysis_data = _robust_unit(data)
    except ValueError as error:
        analysis_data = None
        geometry.abstain("LOW_DYNAMIC_RANGE", str(error), "intensity_dependent_modules")
    geometry.provenance["intensity_preprocessing"] = "percentile_1_99_clip_unit_interval"
    scale_axis = Axis("scale", scales_um, spatial_unit)

    fft = None
    if analysis_data is not None and data.ndim == 2 and min(data.shape) >= 32:
        try:
            fft_spacing_um = _fft_spacing_um(spacing_um, spatial_unit)
            spectral_band = None
            if (
                profile_compatible
                and measurement_profile is not None
                and measurement_profile.spectral_band_fraction_of_nyquist is not None
            ):
                low_fraction, high_fraction = (
                    measurement_profile.spectral_band_fraction_of_nyquist
                )
                nyquist_cycles_per_mm = 500.0 / fft_spacing_um
                spectral_band = (
                    low_fraction * nyquist_cycles_per_mm,
                    high_fraction * nyquist_cycles_per_mm,
                )
            fft = extract_spatial_fft(
                analysis_data,
                pixel_size_um=fft_spacing_um,
                frequency_band_cycles_per_mm=spectral_band,
            )
            add_profiled(_scalar_surface("spectral", "orientation", fft.orientation_degrees, unit="degrees"))
            add_profiled(_scalar_surface("spectral", "anisotropy", fft.anisotropy))
            add_profiled(_scalar_surface("spectral", "angular_entropy", fft.angular_entropy))
            add_profiled(_scalar_surface("spectral", "spectral_slope", fft.spectral_slope))
            add_profiled(
                _scalar_surface(
                    "spectral",
                    "characteristic_wavelength",
                    (
                        1000.0 / fft.characteristic_frequency_cycles_per_mm
                        if spatial_unit == "um"
                        else 1.0 / fft.characteristic_frequency_cycles_per_mm
                    ),
                    unit=spatial_unit,
                )
            )
        except ValueError as error:
            geometry.abstain("SPECTRAL_UNSUPPORTED", str(error), "spectral")
        try:
            tensor = structure_tensor_response(
                analysis_data,
                spacing_um=(spacing_um[0], spacing_um[1]),
                scales_um=scales_um,
            )
            orientation_reasons: list[tuple[str, ...]] = []
            for index, resultant in enumerate(tensor.orientation_resultant):
                item_reasons: list[str] = []
                if resultant < 0.15:
                    item_reasons.append("tensor_orientation_resultant_below_0.15")
                if fft is None or fft.anisotropy < 0.15:
                    item_reasons.append("spectral_orientation_anisotropy_below_0.15")
                if fft is not None and _axial_difference(
                    tensor.orientation_degrees[index], fft.orientation_degrees
                ) > 20.0:
                    item_reasons.append("tensor_spectral_orientation_disagreement_above_20_degrees")
                orientation_reasons.append(tuple(item_reasons))
            orientation_mask = tuple(not reasons for reasons in orientation_reasons)
            add_profiled(
                _surface(
                    "tensor",
                    "orientation",
                    scale_axis,
                    tensor.orientation_degrees,
                    unit="degrees",
                    validity="valid" if all(orientation_mask) else "review",
                    reasons=(
                        ()
                        if all(orientation_mask)
                        else ("orientation_consensus_failed_at_one_or_more_scales",)
                    ),
                    validity_mask=orientation_mask,
                    validity_reasons_by_value=tuple(orientation_reasons),
                )
            )
            add_profiled(_surface("tensor", "coherency", scale_axis, tensor.coherency))
            add_profiled(
                _surface(
                    "tensor",
                    "orientation_resultant",
                    scale_axis,
                    tensor.orientation_resultant,
                )
            )
        except ValueError as error:
            geometry.abstain("TENSOR_UNSUPPORTED", str(error), "tensor")

    if analysis_data is not None:
        try:
            validated_hessian = validated_hessian_morphology(
                analysis_data,
                spacing_um=spacing_um,
                scales_um=scales_um,
            )
            hessian = validated_hessian.hessian
            geometry.provenance["validated_hessian_v2_6"] = {
                "supported": validated_hessian.supported,
                "winning_class": hessian.winning_class,
                "winning_scale": hessian.winning_scale_um,
                "samples_per_winning_scale": (
                    validated_hessian.samples_per_winning_scale
                ),
                "abstention_reasons": list(validated_hessian.abstention_reasons),
            }
            add_profiled(_surface("hessian", "blob_response", scale_axis, hessian.blob))
            add_profiled(_surface("hessian", "tube_response", scale_axis, hessian.tube))
            add_profiled(_surface("hessian", "sheet_response", scale_axis, hessian.sheet))
            add_profiled(_surface("hessian", "blob_shape", scale_axis, _l2_shape(hessian.blob)))
            add_profiled(_surface("hessian", "tube_shape", scale_axis, _l2_shape(hessian.tube)))
            add_profiled(_surface("hessian", "sheet_shape", scale_axis, _l2_shape(hessian.sheet)))
            add_profiled(
                _scalar_surface(
                    "hessian",
                    "blob_scale",
                    scales_um[int(np.argmax(hessian.blob))],
                    unit=spatial_unit,
                )
            )
            add_profiled(
                _scalar_surface(
                    "hessian",
                    "tube_scale",
                    scales_um[int(np.argmax(hessian.tube))],
                    unit=spatial_unit,
                )
            )
            if validated_hessian.supported:
                add_profiled(
                    _scalar_surface(
                        "hessian",
                        "validated_winning_scale_v2_6",
                        hessian.winning_scale_um,
                        unit=spatial_unit,
                    )
                )
            else:
                geometry.abstain(
                    "HESSIAN_SCALE_UNDERSAMPLED",
                    "; ".join(validated_hessian.abstention_reasons),
                    "hessian.validated_winning_class_and_scale_v2_6",
                )
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
            add_profiled(_surface("geometry", "thickness_quantiles", Axis("threshold", (0.05, 0.25, 0.5, 0.75, 0.95), "quantile"), quantiles, unit=spatial_unit))
            if thresholds_um is None:
                thresholds_um = tuple(minimum_spacing * value for value in (0, 1, 2, 4, 8))
            network = erosion_survival_response(binary, spacing_um=spacing_um, thresholds_um=thresholds_um, boundary_corrected=True)
            threshold_axis = Axis("threshold", thresholds_um, spatial_unit)
            add_profiled(_surface("network", "surviving_fraction_boundary_v2", threshold_axis, network.surviving_fraction))
            add_profiled(_surface("network", "component_count", threshold_axis, tuple(float(v) for v in network.component_count), unit="count"))
    else:
        geometry.abstain("MASK_NOT_SUPPLIED", "Geometry and network measurements require an eligible specimen mask.", "geometry/network")

    if analysis_data is not None and data.ndim == 2:
        if spatial_unit == "relative":
            geometry.abstain(
                "PHYSICAL_CALIBRATION_REQUIRED",
                "Validated spatial anisotropy requires micrometre or millimetre spacing.",
                "spatial.validated_gradient_anisotropy_v2_6",
            )
        else:
            try:
                spacing_in_um = tuple(
                    float(value) if spatial_unit == "um" else 1000.0 * float(value)
                    for value in spacing_um[:2]
                )
                validated_spatial = (
                    validated_boundary_robust_gradient_anisotropy_2d(
                        analysis_data,
                        spacing_um=(spacing_in_um[0], spacing_in_um[1]),
                    )
                )
                geometry.provenance["validated_spatial_anisotropy_v2_6"] = {
                    "supported": validated_spatial.supported,
                    "axis_identifiable": (
                        validated_spatial.response.axis_identifiable
                    ),
                    "characteristic_wavelength_um": (
                        validated_spatial.characteristic_wavelength_um
                    ),
                    "characteristic_spans": validated_spatial.characteristic_spans,
                    "stability_score": validated_spatial.stability_score,
                    "abstention_reasons": list(
                        validated_spatial.abstention_reasons
                    ),
                }
                add_profiled(
                    _scalar_surface(
                        "spatial",
                        "gradient_characteristic_spans_v2_6",
                        validated_spatial.characteristic_spans,
                    )
                )
                add_profiled(
                    _scalar_surface(
                        "spatial",
                        "gradient_stability_score_v2_6",
                        validated_spatial.stability_score,
                    )
                )
                if validated_spatial.supported:
                    add_profiled(
                        _scalar_surface(
                            "spatial",
                            "gradient_anisotropy_ratio_v2_6",
                            validated_spatial.response.ratio,
                        )
                    )
                    add_profiled(
                        _scalar_surface(
                            "spatial",
                            "gradient_tapered_ratio_v2_6",
                            validated_spatial.response.tapered_ratio,
                        )
                    )
                    if validated_spatial.response.major_axis_degrees is None:
                        geometry.abstain(
                            "SPATIAL_AXIS_UNIDENTIFIABLE",
                            "Both physical-gradient tensors must reach an anisotropy ratio of 1.65.",
                            "spatial.gradient_axis_v2_6",
                        )
                    else:
                        image_axis = validated_spatial.response.major_axis_degrees
                        add_profiled(
                            _scalar_surface(
                                "spatial",
                                "gradient_axis_image_v2_6",
                                image_axis,
                                unit="degrees",
                            )
                        )
                        add_profiled(
                            _scalar_surface(
                                "spatial",
                                "gradient_axis_specimen_v2_6",
                                calibration.specimen_direction(image_axis),
                                unit="degrees",
                            )
                        )
                else:
                    geometry.abstain(
                        "SPATIAL_ANISOTROPY_UNSUPPORTED",
                        "; ".join(validated_spatial.abstention_reasons),
                        "spatial.gradient_anisotropy_v2_6",
                    )
            except ValueError as error:
                geometry.abstain(
                    "SPATIAL_ANISOTROPY_UNSUPPORTED",
                    str(error),
                    "spatial.gradient_anisotropy_v2_6",
                )
        if separations_um is None:
            separations_um = (
                tuple(
                    value
                    for value in scales_um
                    if value / minimum_spacing < min(data.shape) - 1
                )
                if profile_compatible
                else tuple(minimum_spacing * value for value in (1, 2, 4, 8, 16, 24))
            )
        try:
            spatial = directional_variogram(
                analysis_data,
                spacing_um=(spacing_um[0], spacing_um[1]),
                separations_um=separations_um,
            )
            separation_axis = Axis("separation", separations_um, spatial_unit)
            add_profiled(_surface("spatial", "variogram_horizontal", separation_axis, spatial.horizontal, unit="intensity_squared"))
            add_profiled(_surface("spatial", "variogram_vertical", separation_axis, spatial.vertical, unit="intensity_squared"))
            add_profiled(
                _surface(
                    "spatial",
                    "variogram_horizontal_shape",
                    separation_axis,
                    _l2_shape(spatial.horizontal),
                )
            )
            add_profiled(
                _surface(
                    "spatial",
                    "variogram_vertical_shape",
                    separation_axis,
                    _l2_shape(spatial.vertical),
                )
            )
            add_profiled(
                _scalar_surface(
                    "spatial",
                    "variogram_range_horizontal",
                    spatial.estimated_range_horizontal_um,
                    unit=spatial_unit,
                )
            )
            add_profiled(
                _scalar_surface(
                    "spatial",
                    "variogram_range_vertical",
                    spatial.estimated_range_vertical_um,
                    unit=spatial_unit,
                )
            )
        except ValueError as error:
            geometry.abstain("SPATIAL_UNSUPPORTED", str(error), "spatial.variogram")
    return geometry
