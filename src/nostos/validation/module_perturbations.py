"""Prospective perturbation matrix for each interpretable NOSTOS module."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from nostos.features.response_modules import (
    directional_variogram,
    erosion_survival_response,
    hessian_morphology_response,
    local_thickness_response,
    structure_tensor_response,
)

from .metrics import axial_angular_error_degrees, normalized_curve_distance, relative_scale_error
from .phantoms import generate_phantom
from .perturbations import Perturbation, apply_perturbation


def run_module_perturbation_matrix(output: Path) -> dict:
    results = []

    orientation = generate_phantom("orientation", angle_degrees=37, scale_um=24)
    tensor_perturbations = (
        Perturbation("rotation", 19), Perturbation("resampling", 0.7),
        Perturbation("blur", 1.2), Perturbation("noise", 0.12), Perturbation("contrast", 0.6),
    )
    for perturbation in tensor_perturbations:
        sample = apply_perturbation(orientation, perturbation)
        scales = tuple(sample.truth.spacing_um[0] * value for value in (2, 4, 8))
        response = structure_tensor_response(sample.image, spacing_um=sample.truth.spacing_um, scales_um=scales)
        expected = (37 - 19) % 180 if perturbation.kind == "rotation" else 37
        error = max(axial_angular_error_degrees(value, expected) for value in response.orientation_degrees)
        passed = error <= 5 and min(response.coherency) >= 0.70
        results.append({"module": "tensor", "perturbation": asdict(perturbation), "angular_error_degrees": error, "minimum_coherency": min(response.coherency), "passed": passed})

    for morphology in ("blob", "tube", "sheet"):
        base = generate_phantom(morphology, shape=(48, 48, 48), spacing_um=(1, 1, 1), scale_um=12)  # type: ignore[arg-type]
        for perturbation in (Perturbation("resampling", 0.75), Perturbation("blur", 0.8), Perturbation("noise", 0.05), Perturbation("contrast", 0.6)):
            sample = apply_perturbation(base, perturbation)
            response = hessian_morphology_response(sample.image, spacing_um=sample.truth.spacing_um, scales_um=(1.5, 3, 4.5, 6))
            scale_error = relative_scale_error(response.winning_scale_um, 6.0)
            results.append({"module": "hessian", "truth": morphology, "perturbation": asdict(perturbation), "estimated_class": response.winning_class, "scale_error": scale_error, "passed": response.winning_class == morphology and scale_error <= 0.50})

    thickness_base = generate_phantom("thickness", scale_um=20)
    baseline_thickness = local_thickness_response(thickness_base.mask, spacing_um=(1, 1)).p95_thickness_um
    for perturbation in (Perturbation("rotation", 17), Perturbation("resampling", 0.7)):
        sample = apply_perturbation(thickness_base, perturbation)
        estimate = local_thickness_response(sample.mask, spacing_um=sample.truth.spacing_um).p95_thickness_um
        error = relative_scale_error(estimate, baseline_thickness)
        results.append({"module": "geometry", "perturbation": asdict(perturbation), "relative_error": error, "passed": error <= 0.15})
    for magnitude in (-2, 2):
        sample = apply_perturbation(thickness_base, Perturbation("mask_error", magnitude))
        estimate = local_thickness_response(sample.mask, spacing_um=sample.truth.spacing_um).p95_thickness_um
        results.append({"module": "geometry", "perturbation": asdict(Perturbation("mask_error", magnitude)), "relative_change": (estimate - baseline_thickness) / baseline_thickness, "passed": True, "interpretation": "sensitivity measurement; invariance is not expected"})

    network_base = generate_phantom("network", scale_um=20)
    thresholds = (0.0, 2.0, 4.0, 8.0)
    network_reference = erosion_survival_response(network_base.mask, spacing_um=(1, 1), thresholds_um=thresholds)
    sample = apply_perturbation(network_base, Perturbation("resampling", 0.75))
    network_changed = erosion_survival_response(sample.mask, spacing_um=sample.truth.spacing_um, thresholds_um=thresholds)
    network_distance = normalized_curve_distance(np.asarray(network_reference.surviving_fraction), np.asarray(network_changed.surviving_fraction))
    results.append({"module": "network", "perturbation": asdict(Perturbation("resampling", 0.75)), "curve_distance": network_distance, "passed": network_distance <= 0.25})

    spatial_base = generate_phantom("heterogeneity", correlation_length_um=12, anisotropy_ratio=3)
    separations = (1.0, 2.0, 4.0, 8.0, 12.0, 16.0, 24.0, 32.0)
    spatial_reference = directional_variogram(
        spatial_base.image,
        spacing_um=spatial_base.truth.spacing_um,
        separations_um=separations,
    )
    reference_ratio = spatial_reference.estimated_range_horizontal_um / spatial_reference.estimated_range_vertical_um
    for perturbation in (Perturbation("resampling", 0.75), Perturbation("noise", 0.10), Perturbation("contrast", 0.6), Perturbation("blur", 0.8)):
        sample = apply_perturbation(spatial_base, perturbation)
        spatial = directional_variogram(sample.image, spacing_um=sample.truth.spacing_um, separations_um=separations)
        observed_ratio = spatial.estimated_range_horizontal_um / spatial.estimated_range_vertical_um
        ordering_preserved = observed_ratio > 1.0
        ratio_error = relative_scale_error(observed_ratio, reference_ratio)
        results.append({
            "module": "spatial",
            "perturbation": asdict(perturbation),
            "horizontal_range": spatial.estimated_range_horizontal_um,
            "vertical_range": spatial.estimated_range_vertical_um,
            "reference_anisotropy_ratio": reference_ratio,
            "observed_anisotropy_ratio": observed_ratio,
            "anisotropy_ratio_relative_error": ratio_error,
            "passed": ordering_preserved and ratio_error <= 0.50,
        })

    required = [item for item in results if item.get("interpretation") is None]
    payload = {
        "protocol_version": "nostos-module-perturbations/1.0",
        "status": "pass" if all(item["passed"] for item in required) else "fail",
        "results": results,
        "summary": {
            "required_tests": len(required),
            "passed": sum(bool(item["passed"]) for item in required),
            "failed": sum(not bool(item["passed"]) for item in required),
            "mask_sensitivity_tests": 2,
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "module_perturbation_matrix.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
