"""Comprehensive deterministic physical-truth benchmark for NOSTOS modules."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import spearmanr

from nostos.features.response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    local_thickness_response,
    structure_tensor_response,
)
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import (
    axial_angular_error_degrees,
    relative_scale_error,
    should_abstain,
)
from nostos.validation.phantoms import Phantom, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.0"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_PROTOCOL.md"
ORIENTATIONS = (7.0, 31.0, 67.0, 113.0, 151.0)
WAVELENGTHS = (8.0, 12.0, 24.0, 40.0)
ISOTROPIC_SPACINGS = (0.5, 1.0, 1.5)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _percentile(values: list[float], quantile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), quantile))


def _snr(image: np.ndarray) -> float:
    residual = image - gaussian_filter(image, sigma=0.7)
    noise = np.median(np.abs(residual - np.median(residual))) * 1.4826
    return float(np.std(image) / max(float(noise), 1e-6))


def _fft(phantom: Phantom) -> dict[str, Any]:
    wavelength = float(phantom.truth.parameters["wavelength_um"])
    pixels_per_scale = wavelength / max(phantom.truth.spacing_um)
    signal_to_noise = _snr(phantom.image)
    abstained, reasons = should_abstain(
        pixels_per_scale=pixels_per_scale,
        signal_to_noise=signal_to_noise,
    )
    if abstained:
        return {
            "abstained": True,
            "reasons": list(reasons),
            "pixels_per_scale": pixels_per_scale,
            "signal_to_noise": signal_to_noise,
        }
    measured = extract_spatial_fft(
        phantom.image,
        pixel_size_um=float(phantom.truth.spacing_um[0]),
    )
    return {
        "abstained": False,
        "reasons": [],
        "pixels_per_scale": pixels_per_scale,
        "signal_to_noise": signal_to_noise,
        "orientation_degrees": measured.orientation_degrees,
        "wavelength_um": 1000.0 / measured.characteristic_frequency_cycles_per_mm,
        "anisotropy": measured.anisotropy,
    }


def _spectral_tensor_grid() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    case_index = 0
    for spacing in ISOTROPIC_SPACINGS:
        for wavelength in WAVELENGTHS:
            for angle in ORIENTATIONS:
                phantom = generate_phantom(
                    "orientation",
                    shape=(192, 192),
                    spacing_um=(spacing, spacing),
                    seed=310000 + case_index,
                    angle_degrees=angle,
                    scale_um=wavelength,
                )
                fft = _fft(phantom)
                tensor = structure_tensor_response(
                    phantom.image,
                    spacing_um=(spacing, spacing),
                    scales_um=(1.0, 2.0, 4.0),
                )
                tensor_errors = [
                    axial_angular_error_degrees(estimate, angle)
                    for estimate in tensor.orientation_degrees
                ]
                output.append(
                    {
                        "case_id": f"organization-{case_index:03d}",
                        "truth": {
                            "orientation_degrees": angle,
                            "wavelength_um": wavelength,
                            "spacing_um": spacing,
                            "pixels_per_wavelength": wavelength / spacing,
                        },
                        "fft": fft,
                        "fft_orientation_error_degrees": None
                        if fft["abstained"]
                        else axial_angular_error_degrees(
                            float(fft["orientation_degrees"]), angle
                        ),
                        "fft_wavelength_relative_error": None
                        if fft["abstained"]
                        else relative_scale_error(float(fft["wavelength_um"]), wavelength),
                        "tensor": {
                            "scales_um": list(tensor.scales_um),
                            "orientation_degrees": list(tensor.orientation_degrees),
                            "coherency": list(tensor.coherency),
                            "orientation_resultant": list(tensor.orientation_resultant),
                            "maximum_orientation_error_degrees": max(tensor_errors),
                        },
                    }
                )
                case_index += 1
    return output


def _hessian_grid() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for morphology in ("blob", "tube", "sheet"):
        for radius in (4.0, 6.0, 8.0):
            for spacing in ((1.0, 1.0, 1.0), (1.0, 1.0, 2.0)):
                phantom = generate_phantom(
                    morphology,  # type: ignore[arg-type]
                    shape=(48, 48, 48),
                    spacing_um=spacing,
                    scale_um=2.0 * radius,
                )
                scales = tuple(radius * factor for factor in (0.5, 0.75, 1.0, 1.25, 1.5))
                response = hessian_morphology_response(
                    phantom.image,
                    spacing_um=spacing,
                    scales_um=scales,
                )
                output.append(
                    {
                        "case_id": f"{morphology}-r{radius:g}-s{'x'.join(str(v) for v in spacing)}",
                        "truth_class": morphology,
                        "truth_radius_um": radius,
                        "spacing_um": list(spacing),
                        "scales_um": list(scales),
                        "estimated_class": response.winning_class,
                        "winning_scale_um": response.winning_scale_um,
                        "scale_relative_error": relative_scale_error(
                            response.winning_scale_um, radius
                        ),
                        "correct_class": response.winning_class == morphology,
                        "anisotropic": len(set(spacing)) > 1,
                    }
                )
    return output


def _thickness_grid() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for diameter in (8.0, 16.0, 24.0, 32.0):
        for spacing in ((0.5, 0.5), (1.0, 1.0), (1.0, 2.0)):
            phantom = generate_phantom(
                "thickness",
                shape=(192, 192),
                spacing_um=spacing,
                scale_um=diameter,
            )
            response = local_thickness_response(
                phantom.mask,
                spacing_um=spacing,
                size_bins=32,
            )
            output.append(
                {
                    "case_id": f"sheet2d-d{diameter:g}-s{'x'.join(str(v) for v in spacing)}",
                    "dimension": 2,
                    "morphology": "sheet",
                    "truth_diameter_um": diameter,
                    "spacing_um": list(spacing),
                    "estimated_p95_um": response.p95_thickness_um,
                    "relative_error": relative_scale_error(response.p95_thickness_um, diameter),
                    "anisotropic": len(set(spacing)) > 1,
                }
            )
    for morphology in ("tube", "sheet"):
        for diameter in (8.0, 12.0, 16.0):
            for spacing in ((1.0, 1.0, 1.0), (1.0, 1.0, 2.0)):
                phantom = generate_phantom(
                    morphology,  # type: ignore[arg-type]
                    shape=(48, 48, 48),
                    spacing_um=spacing,
                    scale_um=diameter,
                )
                response = local_thickness_response(
                    phantom.mask,
                    spacing_um=spacing,
                    size_bins=32,
                )
                output.append(
                    {
                        "case_id": f"{morphology}3d-d{diameter:g}-s{'x'.join(str(v) for v in spacing)}",
                        "dimension": 3,
                        "morphology": morphology,
                        "truth_diameter_um": diameter,
                        "spacing_um": list(spacing),
                        "estimated_p95_um": response.p95_thickness_um,
                        "relative_error": relative_scale_error(response.p95_thickness_um, diameter),
                        "anisotropic": len(set(spacing)) > 1,
                    }
                )
    return output


def _network_grid() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for full_width in (4.8, 8.0, 12.0):
        for spacing in ((0.5, 0.5), (1.0, 1.0), (1.0, 2.0)):
            scale = full_width * 2.5
            phantom = generate_phantom(
                "network",
                shape=(192, 192),
                spacing_um=spacing,
                scale_um=scale,
            )
            half_width = full_width / 2.0
            thresholds = tuple(
                float(half_width * factor) for factor in np.arange(0, 1.51, 0.25)
            )
            response = erosion_survival_response(
                phantom.mask,
                spacing_um=spacing,
                thresholds_um=thresholds,
                boundary_corrected=True,
            )
            truth_failure = 1.25 * half_width
            estimated = response.fragmentation_threshold
            output.append(
                {
                    "case_id": f"network-w{full_width:g}-s{'x'.join(str(v) for v in spacing)}",
                    "truth_full_width_um": full_width,
                    "truth_fragmentation_threshold_um": truth_failure,
                    "spacing_um": list(spacing),
                    "thresholds_um": list(thresholds),
                    "surviving_fraction": list(response.surviving_fraction),
                    "percolates": list(response.percolates),
                    "estimated_fragmentation_threshold_um": estimated,
                    "fragmentation_relative_error": None
                    if estimated is None
                    else relative_scale_error(estimated, truth_failure),
                    "monotone_survival": all(
                        left >= right
                        for left, right in zip(
                            response.surviving_fraction,
                            response.surviving_fraction[1:],
                        )
                    ),
                }
            )
    return output


def _spatial_grid() -> list[dict[str, Any]]:
    separations = (2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0)
    output: list[dict[str, Any]] = []
    for correlation_length in (8.0, 16.0, 24.0):
        for anisotropy in (1.0, 2.0, 3.0):
            for seed_offset in range(5):
                phantom = generate_phantom(
                    "heterogeneity",
                    shape=(192, 192),
                    spacing_um=(1.0, 1.0),
                    seed=420000 + int(correlation_length) * 100 + int(anisotropy) * 10 + seed_offset,
                    correlation_length_um=correlation_length,
                    anisotropy_ratio=anisotropy,
                )
                response = directional_variogram(
                    phantom.image,
                    spacing_um=(1.0, 1.0),
                    separations_um=separations,
                )
                recovered = max(
                    response.estimated_range_horizontal_um,
                    response.estimated_range_vertical_um,
                ) / min(
                    response.estimated_range_horizontal_um,
                    response.estimated_range_vertical_um,
                )
                output.append(
                    {
                        "case_id": f"spatial-c{correlation_length:g}-a{anisotropy:g}-seed{seed_offset}",
                        "truth_correlation_length_um": correlation_length,
                        "truth_anisotropy_ratio": anisotropy,
                        "estimated_horizontal_range_um": response.estimated_range_horizontal_um,
                        "estimated_vertical_range_um": response.estimated_range_vertical_um,
                        "recovered_anisotropy_ratio": recovered,
                        "anisotropy_relative_error": relative_scale_error(recovered, anisotropy),
                    }
                )
    return output


def _perturbation_grid() -> list[dict[str, Any]]:
    reference = generate_phantom(
        "orientation",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=1729,
        angle_degrees=31.0,
        scale_um=24.0,
    )
    perturbations = (
        Perturbation("rotation", 17.0),
        Perturbation("resampling", 0.75),
        Perturbation("crop", 0.8),
        Perturbation("blur", 1.0),
        Perturbation("noise", 0.1),
        Perturbation("contrast", 0.65),
        Perturbation("psf", 0.75),
        Perturbation("partial_volume", 0.7),
    )
    output: list[dict[str, Any]] = []
    for perturbation in perturbations:
        candidate = apply_perturbation(reference, perturbation)
        measurement = _fft(candidate)
        expected_angle = (
            (31.0 - perturbation.magnitude) % 180.0
            if perturbation.kind == "rotation"
            else 31.0
        )
        angle_error = None
        scale_error = None
        if not measurement["abstained"]:
            angle_error = axial_angular_error_degrees(
                float(measurement["orientation_degrees"]), expected_angle
            )
            scale_error = relative_scale_error(
                float(measurement["wavelength_um"]), 24.0
            )
        passed = bool(
            measurement["abstained"]
            or (float(angle_error) <= 5.0 and float(scale_error) <= 0.20)
        )
        output.append(
            {
                "perturbation": {
                    "kind": perturbation.kind,
                    "magnitude": perturbation.magnitude,
                    "seed": perturbation.seed,
                },
                "measurement": measurement,
                "expected_orientation_degrees": expected_angle,
                "orientation_error_degrees": angle_error,
                "wavelength_relative_error": scale_error,
                "passed": passed,
            }
        )
    return output


def _mask_sensitivity() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for spacing in ((0.5, 0.5), (1.0, 1.0), (1.0, 2.0)):
        reference = generate_phantom(
            "thickness",
            shape=(192, 192),
            spacing_um=spacing,
            scale_um=20.0,
        )
        baseline = local_thickness_response(reference.mask, spacing_um=spacing).p95_thickness_um
        for magnitude, expectation in ((-2.0, "decrease"), (2.0, "increase")):
            changed = apply_perturbation(reference, Perturbation("mask_error", magnitude))
            estimate = local_thickness_response(changed.mask, spacing_um=spacing).p95_thickness_um
            passed = estimate < baseline if expectation == "decrease" else estimate > baseline
            output.append(
                {
                    "spacing_um": list(spacing),
                    "mask_error_pixels": magnitude,
                    "expectation": expectation,
                    "baseline_p95_um": baseline,
                    "changed_p95_um": estimate,
                    "passed": bool(passed),
                }
            )
    return output


def _abstention_challenges() -> list[dict[str, Any]]:
    challenges = (
        ("undersampled", 3.0, 10.0, 1.0, True, "fewer than four"),
        ("low_snr", 8.0, 2.99, 1.0, True, "below 3"),
        ("low_mask_coverage", 8.0, 10.0, 0.049, True, "below 5 percent"),
        ("exact_support_boundaries", 4.0, 3.0, 0.05, False, None),
    )
    output = []
    for name, pixels, snr, coverage, expected, fragment in challenges:
        abstained, reasons = should_abstain(
            pixels_per_scale=pixels,
            signal_to_noise=snr,
            mask_coverage=coverage,
        )
        reason_match = fragment is None or any(fragment in reason for reason in reasons)
        output.append(
            {
                "challenge": name,
                "inputs": {
                    "pixels_per_scale": pixels,
                    "signal_to_noise": snr,
                    "mask_coverage": coverage,
                },
                "expected_abstention": expected,
                "observed_abstention": abstained,
                "reasons": list(reasons),
                "passed": abstained == expected and reason_match,
            }
        )
    return output


def build_synthetic_physical_truth_v2(root: Path) -> dict[str, Any]:
    protocol = root / PROTOCOL_PATH
    organization = _spectral_tensor_grid()
    hessian = _hessian_grid()
    thickness = _thickness_grid()
    network = _network_grid()
    spatial = _spatial_grid()
    perturbations = _perturbation_grid()
    mask_sensitivity = _mask_sensitivity()
    abstention = _abstention_challenges()

    fft_orientation = [
        float(item["fft_orientation_error_degrees"])
        for item in organization
        if item["fft_orientation_error_degrees"] is not None
    ]
    fft_scale = [
        float(item["fft_wavelength_relative_error"])
        for item in organization
        if item["fft_wavelength_relative_error"] is not None
    ]
    tensor_errors = [
        float(error)
        for item in organization
        for error in [item["tensor"]["maximum_orientation_error_degrees"]]
    ]
    tensor_coherency = [
        float(value) for item in organization for value in item["tensor"]["coherency"]
    ]
    classes = ("blob", "tube", "sheet")
    recalls = {
        label: float(
            np.mean(
                [item["correct_class"] for item in hessian if item["truth_class"] == label]
            )
        )
        for label in classes
    }
    hessian_scale = [float(item["scale_relative_error"]) for item in hessian]
    thickness_error = [float(item["relative_error"]) for item in thickness]
    anisotropic_thickness = [
        float(item["relative_error"]) for item in thickness if item["anisotropic"]
    ]
    network_error = [
        float(item["fragmentation_relative_error"])
        for item in network
        if item["fragmentation_relative_error"] is not None
    ]
    declared_anisotropy = np.asarray(
        [item["truth_anisotropy_ratio"] for item in spatial], dtype=float
    )
    recovered_anisotropy = np.asarray(
        [item["recovered_anisotropy_ratio"] for item in spatial], dtype=float
    )
    spatial_rho = float(spearmanr(declared_anisotropy, recovered_anisotropy).statistic)
    spatial_error = [float(item["anisotropy_relative_error"]) for item in spatial]
    isotropic_ratios = [
        float(item["recovered_anisotropy_ratio"])
        for item in spatial
        if item["truth_anisotropy_ratio"] == 1.0
    ]
    metrics = {
        "spectral_orientation": {
            "cases": len(fft_orientation),
            "abstentions": sum(bool(item["fft"]["abstained"]) for item in organization),
            "median_error_degrees": float(np.median(fft_orientation)),
            "p95_error_degrees": _percentile(fft_orientation, 95),
        },
        "spectral_wavelength": {
            "median_relative_error": float(np.median(fft_scale)),
            "p95_relative_error": _percentile(fft_scale, 95),
        },
        "tensor_orientation": {
            "median_maximum_case_error_degrees": float(np.median(tensor_errors)),
            "p95_maximum_case_error_degrees": _percentile(tensor_errors, 95),
            "p05_coherency": _percentile(tensor_coherency, 5),
        },
        "hessian": {
            "balanced_accuracy": float(np.mean(list(recalls.values()))),
            "per_class_recall": recalls,
            "anisotropic_accuracy": float(
                np.mean([item["correct_class"] for item in hessian if item["anisotropic"]])
            ),
            "median_scale_relative_error": float(np.median(hessian_scale)),
            "p95_scale_relative_error": _percentile(hessian_scale, 95),
        },
        "thickness": {
            "median_relative_error": float(np.median(thickness_error)),
            "p95_relative_error": _percentile(thickness_error, 95),
            "anisotropic_p95_relative_error": _percentile(anisotropic_thickness, 95),
        },
        "network": {
            "median_fragmentation_relative_error": float(np.median(network_error)),
            "p95_fragmentation_relative_error": _percentile(network_error, 95),
            "all_survival_curves_monotone": all(item["monotone_survival"] for item in network),
        },
        "spatial": {
            "spearman_rho": spatial_rho,
            "median_anisotropy_relative_error": float(np.median(spatial_error)),
            "isotropic_min_ratio": min(isotropic_ratios),
            "isotropic_max_ratio": max(isotropic_ratios),
        },
    }
    gates = {
        "spectral_orientation_median_le_1_and_p95_le_3": (
            metrics["spectral_orientation"]["median_error_degrees"] <= 1.0
            and metrics["spectral_orientation"]["p95_error_degrees"] <= 3.0
        ),
        "spectral_wavelength_median_le_0_08_and_p95_le_0_20": (
            metrics["spectral_wavelength"]["median_relative_error"] <= 0.08
            and metrics["spectral_wavelength"]["p95_relative_error"] <= 0.20
        ),
        "tensor_orientation_and_coherency": (
            metrics["tensor_orientation"]["median_maximum_case_error_degrees"] <= 1.0
            and metrics["tensor_orientation"]["p95_maximum_case_error_degrees"] <= 2.5
            and metrics["tensor_orientation"]["p05_coherency"] >= 0.75
        ),
        "hessian_classification": (
            metrics["hessian"]["balanced_accuracy"] >= 0.90
            and min(metrics["hessian"]["per_class_recall"].values()) >= 0.80
            and metrics["hessian"]["anisotropic_accuracy"] >= 0.80
        ),
        "hessian_scale": (
            metrics["hessian"]["median_scale_relative_error"] <= 0.35
            and metrics["hessian"]["p95_scale_relative_error"] <= 0.50
        ),
        "thickness": (
            metrics["thickness"]["median_relative_error"] <= 0.10
            and metrics["thickness"]["p95_relative_error"] <= 0.20
            and metrics["thickness"]["anisotropic_p95_relative_error"] <= 0.25
        ),
        "network": (
            metrics["network"]["median_fragmentation_relative_error"] <= 0.20
            and metrics["network"]["p95_fragmentation_relative_error"] <= 0.35
            and metrics["network"]["all_survival_curves_monotone"]
        ),
        "spatial": (
            metrics["spatial"]["spearman_rho"] >= 0.80
            and metrics["spatial"]["median_anisotropy_relative_error"] <= 0.35
            and metrics["spatial"]["isotropic_min_ratio"] >= 0.75
            and metrics["spatial"]["isotropic_max_ratio"] <= 1.33
        ),
        "orientation_perturbations": all(item["passed"] for item in perturbations),
        "mask_error_directionality": all(item["passed"] for item in mask_sensitivity),
        "abstention_challenges": all(item["passed"] for item in abstention),
    }
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": PROTOCOL_PATH,
        "protocol_sha256": _sha256_file(protocol),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "success_gates_before_repeat": gates,
        "metrics": metrics,
        "cases": {
            "organization": organization,
            "hessian": hessian,
            "thickness": thickness,
            "network": network,
            "spatial": spatial,
            "orientation_perturbations": perturbations,
            "mask_sensitivity": mask_sensitivity,
            "abstention": abstention,
        },
        "scope": (
            "Analytic 2D/3D physical-truth and controlled-perturbation validation; "
            "not biological, segmentation, clinical, mechanical or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["build_synthetic_physical_truth_v2"]
