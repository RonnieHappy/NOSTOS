"""NOSTOS v7 support contract for physically scaled tensor measurements."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import ndimage

from nostos.core.qc import acquisition_qc
from nostos.features.physical_tensor import (
    PhysicalTensorResponse,
    axial_circular_wasserstein_degrees,
    physical_structure_tensor_response,
    shift_axial_histogram,
)
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.paired_acquisition_support import PairRegistration, _robust_unit


DERIVATIVE_SCALE_FRACTION = 0.5
INTEGRATION_SCALE_FACTOR = 1.0
MINIMUM_RESULTANT = 0.15
MINIMUM_SPECTRAL_ANISOTROPY = 0.15
MAXIMUM_ESTIMATOR_DISAGREEMENT_DEGREES = 20.0
MAXIMUM_JACKKNIFE_DRIFT_DEGREES = 20.0
MAXIMUM_REFERENCE_ORIENTATION_PROBE_DRIFT_DEGREES = 5.0
MAXIMUM_REFERENCE_COHERENCE_PROBE_DRIFT = 0.10
MINIMUM_SAMPLES_PER_SCALE = 4.0
ORIENTATION_TOLERANCE_DEGREES = 10.0
COHERENCE_TOLERANCE = 0.15
RESOLUTION_MARGIN_SIGMA_EFFECTIVE_INPUT_PIXELS = 2.0


def _qc_risk(qc: Mapping[str, Any]) -> float:
    if qc["status"] == "abstain":
        return 2.0
    endpoint_risk = float(qc["observed_endpoint_fraction"]) / 0.20
    residual_risk = 3.0 / max(
        float(qc["contrast_to_residual"]), np.finfo(float).eps
    )
    focus = max(float(qc["tenengrad_focus_v2"]), 0.0)
    focus_risk = 1.0 / (1.0 + 20.0 * math.sqrt(focus))
    return float(max(endpoint_risk, residual_risk, focus_risk))


def _probe_images(
    image: np.ndarray,
    *,
    grid_spacing_um: float,
    effective_spacing_um: float,
) -> Sequence[tuple[str, float, np.ndarray]]:
    probes: list[tuple[str, float, np.ndarray]] = []
    for angle in (-3.0, 3.0):
        probes.append(
            (
                "rotation",
                angle,
                ndimage.rotate(
                    image,
                    angle,
                    reshape=False,
                    order=1,
                    mode="reflect",
                ),
            )
        )
    sigma = 0.5 * effective_spacing_um / grid_spacing_um
    probes.append(
        (
            "blur",
            0.5,
            ndimage.gaussian_filter(image, sigma=sigma, mode="reflect"),
        )
    )
    shift = effective_spacing_um / grid_spacing_um
    probes.append(
        (
            "translation",
            1.0,
            ndimage.shift(
                image,
                shift=(shift, -shift),
                order=1,
                mode="reflect",
            ),
        )
    )
    for gamma in (0.9, 1.1):
        probes.append(("gamma", gamma, np.power(image, gamma)))
    return probes


def measure_tensor_support(
    image: np.ndarray,
    *,
    grid_spacing_um: float,
    effective_spacing_um: float,
    scales_um: Sequence[float],
    spectral_band_cycles_per_mm: tuple[float, float],
    derivative_scale_fraction: float = DERIVATIVE_SCALE_FRACTION,
    integration_scale_factor: float = INTEGRATION_SCALE_FACTOR,
) -> dict[str, Any]:
    """Measure the selected tensor response and its mild perturbation probes."""

    data = _robust_unit(image)
    scales = tuple(float(value) for value in scales_um)

    def tensor(candidate: np.ndarray) -> PhysicalTensorResponse:
        return physical_structure_tensor_response(
            candidate,
            spacing_um=(grid_spacing_um, grid_spacing_um),
            scales_um=scales,
            derivative_scale_fraction=derivative_scale_fraction,
            integration_scale_factor=integration_scale_factor,
        )

    base = tensor(data)
    fft = extract_spatial_fft(
        data,
        pixel_size_um=grid_spacing_um,
        frequency_band_cycles_per_mm=spectral_band_cycles_per_mm,
    )
    probes = [
        {
            "name": name,
            "magnitude": magnitude,
            "response": tensor(candidate),
        }
        for name, magnitude, candidate in _probe_images(
            data,
            grid_spacing_um=grid_spacing_um,
            effective_spacing_um=effective_spacing_um,
        )
    ]
    return {
        "tensor": base,
        "spectral_orientation": float(fft.orientation_degrees),
        "spectral_anisotropy": float(fft.anisotropy),
        "qc": acquisition_qc(data),
        "probes": probes,
        "derivative_scale_fraction": float(derivative_scale_fraction),
        "integration_scale_factor": float(integration_scale_factor),
    }


def measure_resolution_margin_probe(
    image: np.ndarray,
    *,
    grid_spacing_um: float,
    effective_spacing_um: float,
    scales_um: Sequence[float],
    sigma_effective_input_pixels: float = RESOLUTION_MARGIN_SIGMA_EFFECTIVE_INPUT_PIXELS,
    derivative_scale_fraction: float = DERIVATIVE_SCALE_FRACTION,
    integration_scale_factor: float = INTEGRATION_SCALE_FACTOR,
) -> PhysicalTensorResponse:
    """Return the strong-blur response used by the coherence support margin."""

    if grid_spacing_um <= 0 or effective_spacing_um <= 0:
        raise ValueError("Grid and effective spacing must be positive.")
    if sigma_effective_input_pixels <= 0:
        raise ValueError("Resolution-margin sigma must be positive.")
    data = _robust_unit(image)
    sigma_grid_pixels = (
        sigma_effective_input_pixels * effective_spacing_um / grid_spacing_um
    )
    probe = ndimage.gaussian_filter(
        data,
        sigma=sigma_grid_pixels,
        mode="reflect",
    )
    return physical_structure_tensor_response(
        probe,
        spacing_um=(grid_spacing_um, grid_spacing_um),
        scales_um=tuple(float(value) for value in scales_um),
        derivative_scale_fraction=derivative_scale_fraction,
        integration_scale_factor=integration_scale_factor,
    )


def _probe_instability(
    measurement: Mapping[str, Any],
    *,
    endpoint: str,
    scale_index: int,
) -> float:
    base: PhysicalTensorResponse = measurement["tensor"]
    if endpoint == "tensor_orientation":
        reference = float(base.orientation_degrees[scale_index])
    elif endpoint == "tensor_orientation_distribution":
        reference = np.asarray(base.orientation_histograms[scale_index], dtype=float)
    elif endpoint == "tensor_coherence":
        reference = float(base.coherency[scale_index])
    else:
        raise KeyError(endpoint)
    errors: list[float] = []
    for probe in measurement["probes"]:
        response: PhysicalTensorResponse = probe["response"]
        if endpoint == "tensor_orientation":
            value = float(response.orientation_degrees[scale_index])
            if probe["name"] == "rotation":
                value = (value + float(probe["magnitude"])) % 180.0
            errors.append(axial_angular_error_degrees(value, reference))
        elif endpoint == "tensor_orientation_distribution":
            value = np.asarray(
                response.orientation_histograms[scale_index], dtype=float
            )
            if probe["name"] == "rotation":
                value = shift_axial_histogram(value, float(probe["magnitude"]))
            errors.append(axial_circular_wasserstein_degrees(value, reference))
        else:
            errors.append(abs(float(response.coherency[scale_index]) - reference))
    return float(max(errors, default=0.0))


def evaluate_tensor_pair(
    *,
    pair_id: str,
    reference_group_id: str,
    structure: str,
    effective_input_spacing_um: float,
    registration: PairRegistration,
    input_measurement: Mapping[str, Any],
    reference_measurement: Mapping[str, Any],
    scales_um: Sequence[float],
    input_resolution_margin_response: PhysicalTensorResponse | None = None,
    coherence_resolution_margin_threshold_fraction: float | None = None,
    resolution_margin_sigma_effective_input_pixels: float = RESOLUTION_MARGIN_SIGMA_EFFECTIVE_INPUT_PIXELS,
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit scale-resolved tensor cases with support independent of reference error."""

    input_tensor: PhysicalTensorResponse = input_measurement["tensor"]
    reference_tensor: PhysicalTensorResponse = reference_measurement["tensor"]
    qc_risk = _qc_risk(input_measurement["qc"])
    if (input_resolution_margin_response is None) != (
        coherence_resolution_margin_threshold_fraction is None
    ):
        raise ValueError(
            "Resolution-margin response and coherence threshold must be supplied together."
        )
    if (
        coherence_resolution_margin_threshold_fraction is not None
        and coherence_resolution_margin_threshold_fraction <= 0
    ):
        raise ValueError("Coherence resolution-margin threshold must be positive.")
    rows: list[dict[str, Any]] = []
    for index, scale in enumerate(float(value) for value in scales_um):
        sampling_risk = max(
            0.0,
            (
                MINIMUM_SAMPLES_PER_SCALE
                - scale / effective_input_spacing_um
            )
            / MINIMUM_SAMPLES_PER_SCALE,
        )
        input_resultant = float(input_tensor.orientation_resultant[index])
        reference_resultant = float(reference_tensor.orientation_resultant[index])
        input_jackknife = float(input_tensor.jackknife_axis_drift_degrees[index])
        reference_jackknife = float(
            reference_tensor.jackknife_axis_drift_degrees[index]
        )
        input_spectral_anisotropy = float(input_measurement["spectral_anisotropy"])
        reference_spectral_anisotropy = float(
            reference_measurement["spectral_anisotropy"]
        )
        input_estimator_disagreement = axial_angular_error_degrees(
            float(input_tensor.orientation_degrees[index]),
            float(input_measurement["spectral_orientation"]),
        )
        reference_estimator_disagreement = axial_angular_error_degrees(
            float(reference_tensor.orientation_degrees[index]),
            float(reference_measurement["spectral_orientation"]),
        )

        for endpoint in ("tensor_orientation_distribution", "tensor_coherence"):
            if endpoint == "tensor_orientation_distribution":
                estimate = list(input_tensor.orientation_histograms[index])
                truth = list(reference_tensor.orientation_histograms[index])
                error = axial_circular_wasserstein_degrees(estimate, truth)
                tolerance = ORIENTATION_TOLERANCE_DEGREES
            else:
                estimate = float(input_tensor.coherency[index])
                truth = float(reference_tensor.coherency[index])
                error = abs(estimate - truth)
                tolerance = COHERENCE_TOLERANCE
            input_probe = _probe_instability(
                input_measurement,
                endpoint=endpoint,
                scale_index=index,
            )
            reference_probe = _probe_instability(
                reference_measurement,
                endpoint=endpoint,
                scale_index=index,
            )
            perturbation_risk = input_probe / tolerance
            resolution_margin_drift: float | None = None
            resolution_margin_normalized: float | None = None
            resolution_margin_score = 0.0
            resolution_margin_governs = False
            if input_resolution_margin_response is not None:
                if endpoint == "tensor_orientation_distribution":
                    resolution_margin_drift = axial_circular_wasserstein_degrees(
                        estimate,
                        input_resolution_margin_response.orientation_histograms[
                            index
                        ],
                    )
                else:
                    resolution_margin_drift = abs(
                        float(estimate)
                        - float(input_resolution_margin_response.coherency[index])
                    )
                    resolution_margin_governs = True
                resolution_margin_normalized = (
                    resolution_margin_drift / tolerance
                )
                if resolution_margin_governs:
                    resolution_margin_score = (
                        resolution_margin_normalized
                        / float(coherence_resolution_margin_threshold_fraction)
                    )

            reference_reasons: list[str] = []
            hard_reasons: list[str] = []
            if endpoint == "tensor_orientation_distribution":
                if (
                    reference_probe
                    > MAXIMUM_REFERENCE_ORIENTATION_PROBE_DRIFT_DEGREES
                ):
                    reference_reasons.append(
                        "reference_orientation_probe_drift_above_5_degrees"
                    )
                # A distribution remains a valid estimand for crossing,
                # isotropic and spatially mixed orientations.  Scalar-axis
                # identifiability diagnostics are retained below but do not
                # invalidate the distribution itself.
                identifiability_risk = 0.0
            else:
                if reference_probe > MAXIMUM_REFERENCE_COHERENCE_PROBE_DRIFT:
                    reference_reasons.append(
                        "reference_coherence_probe_drift_above_0.10"
                    )
                identifiability_risk = 0.0

            if scale / effective_input_spacing_um < MINIMUM_SAMPLES_PER_SCALE:
                hard_reasons.append("fewer_than_four_samples_per_response_scale")
            if input_measurement["qc"]["status"] == "abstain":
                hard_reasons.append("acquisition_qc_abstain")
            full_score = float(
                max(
                    qc_risk,
                    sampling_risk,
                    perturbation_risk,
                    identifiability_risk,
                    resolution_margin_score,
                )
            )
            without_jackknife = float(
                max(
                    qc_risk,
                    sampling_risk,
                    perturbation_risk,
                    (
                        max(
                            MINIMUM_RESULTANT
                            / max(input_resultant, np.finfo(float).eps),
                            MINIMUM_SPECTRAL_ANISOTROPY
                            / max(input_spectral_anisotropy, np.finfo(float).eps),
                            input_estimator_disagreement
                            / MAXIMUM_ESTIMATOR_DISAGREEMENT_DEGREES,
                        )
                        if endpoint == "tensor_orientation"
                        else 0.0
                    ),
                )
            )
            rows.append(
                {
                    "case_id": f"{pair_id}|{endpoint}|{scale}",
                    "pair_id": pair_id,
                    "reference_group_id": reference_group_id,
                    "structure": structure,
                    "endpoint": endpoint,
                    "endpoint_family": (
                        "tensor_orientation_distribution"
                        if endpoint == "tensor_orientation_distribution"
                        else "tensor_coherence"
                    ),
                    "requested_scale_um": scale,
                    "pair_registration_eligible": bool(registration.eligible),
                    "pair_registration": {
                        "eligible": registration.eligible,
                        "shift_reference_pixels_yx": list(
                            registration.shift_reference_pixels_yx
                        ),
                        "shift_effective_input_pixels_yx": list(
                            registration.shift_effective_input_pixels_yx
                        ),
                        "peak_ratio": registration.peak_ratio,
                        "error": registration.error,
                        "reasons": list(registration.reasons),
                    },
                    "reference_eligible": not reference_reasons,
                    "reference_eligibility_reasons": reference_reasons,
                    "reference_probe_instability": reference_probe,
                    "estimate": estimate,
                    "reference": truth,
                    "error": error,
                    "invalidity_tolerance": tolerance,
                    "invalid": bool(error > tolerance),
                    "hard_abstention_reasons": hard_reasons,
                    "support_components": {
                        "acquisition_qc": qc_risk,
                        "physical_sampling": sampling_risk,
                        "perturbation_stability": perturbation_risk,
                        "input_probe_instability": input_probe,
                        "orientation_resultant": input_resultant,
                        "spectral_anisotropy": input_spectral_anisotropy,
                        "tensor_fft_disagreement_degrees": input_estimator_disagreement,
                        "quadrant_jackknife_axis_drift_degrees": input_jackknife,
                        "measurement_identifiability": identifiability_risk,
                        "samples_per_scale": scale / effective_input_spacing_um,
                        "resolution_margin": resolution_margin_score,
                    },
                    "resolution_margin": {
                        "operation": "Gaussian blur on normalized input before measurement",
                        "sigma_effective_input_pixels": float(
                            resolution_margin_sigma_effective_input_pixels
                        ),
                        "drift": resolution_margin_drift,
                        "normalized_to_endpoint_tolerance": resolution_margin_normalized,
                        "coherence_threshold_fraction": coherence_resolution_margin_threshold_fraction,
                        "component_score": float(resolution_margin_score),
                        "governs_acceptance": resolution_margin_governs,
                        "family_rule": (
                            "maximum-score contract component"
                            if resolution_margin_governs
                            else "diagnostic_only_no_acceptance_effect"
                        ),
                    },
                    "reference_components": {
                        "orientation_resultant": reference_resultant,
                        "spectral_anisotropy": reference_spectral_anisotropy,
                        "tensor_fft_disagreement_degrees": reference_estimator_disagreement,
                        "quadrant_jackknife_axis_drift_degrees": reference_jackknife,
                    },
                    "derived_axis_diagnostic_only": {
                        "input_degrees": float(
                            input_tensor.orientation_degrees[index]
                        ),
                        "reference_degrees": float(
                            reference_tensor.orientation_degrees[index]
                        ),
                        "error_degrees": axial_angular_error_degrees(
                            float(input_tensor.orientation_degrees[index]),
                            float(reference_tensor.orientation_degrees[index]),
                        ),
                        "input_resultant": input_resultant,
                        "reference_resultant": reference_resultant,
                        "claim_eligible": False,
                    },
                    "scores": {
                        "full_contract": full_score,
                        "conventional_acquisition_qc": qc_risk,
                        "always_emit": 0.0,
                        "full_without_jackknife": without_jackknife,
                        "full_without_perturbation": float(
                            max(qc_risk, sampling_risk, identifiability_risk)
                        ),
                        "full_without_identifiability": float(
                            max(qc_risk, sampling_risk, perturbation_risk)
                        ),
                    },
                    "metadata": dict(metadata or {}),
                }
            )
    return rows


def policy_accepts(row: Mapping[str, Any], condition: str) -> bool:
    """Apply the dimensionless v7 boundary at one without hybrid ablations."""

    reasons = set(str(value) for value in row["hard_abstention_reasons"])
    if condition == "always_emit":
        return True
    if condition == "conventional_acquisition_qc":
        governed = reasons & {"acquisition_qc_abstain"}
    elif condition == "full_without_jackknife":
        governed = reasons - {"input_quadrant_jackknife_drift_above_20_degrees"}
    elif condition == "full_without_perturbation":
        governed = reasons
    elif condition == "full_without_identifiability":
        governed = {
            value
            for value in reasons
            if value
            not in {
                "input_resultant_below_0.15",
                "input_spectral_anisotropy_below_0.15",
                "input_tensor_fft_disagreement_above_20_degrees",
                "input_quadrant_jackknife_drift_above_20_degrees",
            }
        }
    elif condition == "full_contract":
        governed = reasons
    else:
        raise KeyError(condition)
    return not governed and float(row["scores"][condition]) <= 1.0
