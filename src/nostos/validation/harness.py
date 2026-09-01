"""Executable CPU validation harness for the first frozen NOSTOS construct."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

from nostos.features.spatial_fft import extract_spatial_fft
from nostos.features.response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    local_thickness_response,
    structure_tensor_response,
)

from .metrics import axial_angular_error_degrees, relative_scale_error, should_abstain
from .phantoms import Phantom, generate_phantom
from .perturbations import Perturbation, apply_perturbation

PROTOCOL_VERSION = "nostos-synthetic/1.1"
PERTURBATIONS = (
    Perturbation("rotation", 17.0),
    Perturbation("resampling", 0.75),
    Perturbation("crop", 0.80),
    Perturbation("blur", 1.0),
    Perturbation("noise", 0.10),
    Perturbation("contrast", 0.65),
    Perturbation("psf", 0.75),
    Perturbation("partial_volume", 0.70),
)


def _fft_measurement(phantom: Phantom) -> dict[str, float | bool | list[str]]:
    truth_scale = float(phantom.truth.parameters["wavelength_um"])
    pixels_per_scale = truth_scale / max(phantom.truth.spacing_um)
    residual = phantom.image - gaussian_filter(phantom.image, sigma=0.7)
    noise = np.median(np.abs(residual - np.median(residual))) * 1.4826
    signal_to_noise = float(np.std(phantom.image) / max(float(noise), 1e-6))
    abstain, reasons = should_abstain(pixels_per_scale=pixels_per_scale, signal_to_noise=signal_to_noise)
    if abstain:
        return {"abstained": True, "reasons": list(reasons), "pixels_per_scale": pixels_per_scale, "signal_to_noise": signal_to_noise}
    features = extract_spatial_fft(phantom.image, pixel_size_um=float(phantom.truth.spacing_um[0]))
    wavelength = 1000.0 / features.characteristic_frequency_cycles_per_mm
    return {
        "abstained": False,
        "orientation_degrees": features.orientation_degrees,
        "wavelength_um": wavelength,
        "anisotropy": features.anisotropy,
        "angular_entropy": features.angular_entropy,
        "pixels_per_scale": pixels_per_scale,
        "signal_to_noise": signal_to_noise,
    }


def run_frozen_validation(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    reference = generate_phantom("orientation", angle_degrees=31.0, scale_um=24.0)
    reference_result = _fft_measurement(reference)
    truth_angle = float(reference.truth.parameters["orientation_degrees"])
    truth_scale = float(reference.truth.parameters["wavelength_um"])
    cases: list[dict] = []
    for perturbation in PERTURBATIONS:
        candidate = apply_perturbation(reference, perturbation)
        result = _fft_measurement(candidate)
        # scipy.ndimage.rotate uses array coordinates (row axis points down),
        # so a positive array rotation subtracts from the Cartesian axial angle.
        expected_angle = (truth_angle - perturbation.magnitude) % 180 if perturbation.kind == "rotation" else truth_angle
        case = {"perturbation": asdict(perturbation), "measurement": result}
        if not result["abstained"]:
            angle_error = axial_angular_error_degrees(float(result["orientation_degrees"]), expected_angle)
            scale_error = relative_scale_error(float(result["wavelength_um"]), truth_scale)
            case["errors"] = {"circular_angular_error_degrees": angle_error, "relative_scale_error": scale_error}
            case["passed"] = angle_error <= 5.0 and scale_error <= 0.35
        else:
            case["errors"] = None
            case["passed"] = True
        cases.append(case)

    constructs = []
    for name in ("orientation", "spectral_scale", "blob", "tube", "sheet", "thickness", "roughness", "network", "heterogeneity"):
        phantom = generate_phantom(name)  # type: ignore[arg-type]
        image_hash = hashlib.sha256(np.ascontiguousarray(phantom.image).tobytes()).hexdigest()
        constructs.append({"truth": asdict(phantom.truth), "shape": list(phantom.image.shape), "image_sha256": image_hash, "has_mask": phantom.mask is not None})

    tensor_phantom = generate_phantom("orientation", angle_degrees=37.0, scale_um=24.0)
    tensor = structure_tensor_response(tensor_phantom.image, spacing_um=(1.0, 1.0), scales_um=(1.0, 2.0, 4.0))
    tensor_errors = [axial_angular_error_degrees(value, 37.0) for value in tensor.orientation_degrees]
    hessian_cases = []
    for morphology in ("blob", "tube", "sheet"):
        phantom = generate_phantom(morphology, shape=(48, 48, 48), spacing_um=(1.0, 1.0, 1.0), scale_um=12.0)  # type: ignore[arg-type]
        response = hessian_morphology_response(phantom.image, spacing_um=(1.0, 1.0, 1.0), scales_um=(1.5, 3.0, 4.5, 6.0))
        hessian_cases.append({"truth": morphology, "estimate": response.winning_class, "winning_scale_um": response.winning_scale_um, "passed": response.winning_class == morphology})
    thickness_phantom = generate_phantom("thickness", scale_um=20.0)
    thickness = local_thickness_response(thickness_phantom.mask, spacing_um=(1.0, 1.0))
    thickness_error = relative_scale_error(thickness.p95_thickness_um, 20.0)
    network_phantom = generate_phantom("network", scale_um=20.0)
    network = erosion_survival_response(network_phantom.mask, spacing_um=(1.0, 1.0), thresholds_um=(0.0, 2.0, 4.0, 8.0))
    network_monotonic = all(a >= b for a, b in zip(network.surviving_fraction, network.surviving_fraction[1:]))
    spatial_phantom = generate_phantom("heterogeneity", correlation_length_um=12.0, anisotropy_ratio=3.0)
    spatial = directional_variogram(spatial_phantom.image, spacing_um=(1.0, 1.0), separations_um=(1.0, 2.0, 4.0, 8.0, 12.0, 16.0, 24.0, 32.0))
    module_gates = {
        "structure_tensor": {"max_circular_error_degrees": max(tensor_errors), "minimum_coherency": min(tensor.coherency), "passed": max(tensor_errors) <= 2.0 and min(tensor.coherency) >= 0.8},
        "hessian_morphology": {"cases": hessian_cases, "passed": all(item["passed"] for item in hessian_cases)},
        "geometry": {"p95_thickness_um": thickness.p95_thickness_um, "relative_error": thickness_error, "passed": thickness_error <= 0.15},
        "network": {"surviving_fraction": list(network.surviving_fraction), "monotonic": network_monotonic, "passed": network_monotonic and network.surviving_fraction[0] == 1.0},
        "spatial": {"range_horizontal_um": spatial.estimated_range_horizontal_um, "range_vertical_um": spatial.estimated_range_vertical_um, "passed": spatial.estimated_range_horizontal_um != spatial.estimated_range_vertical_um},
    }
    module_pass = all(item["passed"] for item in module_gates.values())

    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "pass" if all(case["passed"] for case in cases) and module_pass else "fail",
        "scope": "synthetic truth and perturbation validation for the interpretable NOSTOS-0 CPU core",
        "reference": {"truth": asdict(reference.truth), "measurement": reference_result},
        "construct_registry": constructs,
        "perturbation_results": cases,
        "module_gates": module_gates,
        "summary": {
            "constructs_registered": len(constructs),
            "perturbations_tested": len(cases),
            "passed": sum(bool(case["passed"]) for case in cases),
            "abstentions": sum(bool(case["measurement"]["abstained"]) for case in cases),
            "module_gates_passed": sum(bool(item["passed"]) for item in module_gates.values()),
            "module_gates_total": len(module_gates),
        },
    }
    (output / "validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
