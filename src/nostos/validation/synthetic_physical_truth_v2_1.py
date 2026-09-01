"""Disjoint confirmation of fail-closed synthetic physical-truth repairs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.stats import spearmanr

from nostos.features.response_modules import (
    erosion_survival_response,
    local_thickness_response,
)
from nostos.features.validated_responses import (
    validated_hessian_morphology,
    validated_intrinsic_variogram_2d,
    validated_tensor_orientation_2d,
)
from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.phantoms import Phantom, PhantomTruth, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.1-confirmation"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_1_CONFIRMATION_PROTOCOL.md"
DEVELOPMENT_PATH = "outputs/nostos0-synthetic-repair-development-v2-1/development.json"
VALIDATED_RESPONSES_PATH = "src/nostos/features/validated_responses.py"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _geometry_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    data = [
        {
            "case_id": row["case_id"],
            "supported": row["supported"],
            "abstention_reasons": row["abstention_reasons"],
            "measurement": row["measurement"],
        }
        for row in rows
    ]
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _organization_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    index = 0
    for spacing in (0.75, 1.25, 1.75):
        for wavelength in (9.0, 15.0, 27.0, 36.0):
            for angle in (19.0, 47.0, 83.0, 127.0, 163.0):
                phantom = generate_phantom(
                    "orientation",
                    shape=(192, 192),
                    spacing_um=(spacing, spacing),
                    seed=610000 + index,
                    angle_degrees=angle,
                    scale_um=wavelength,
                )
                response = validated_tensor_orientation_2d(
                    phantom.image,
                    spacing_um=(spacing, spacing),
                    scales_um=(1.0, 2.0, 4.0),
                )
                errors = [
                    axial_angular_error_degrees(value, angle)
                    for value in response.tensor.orientation_degrees
                ]
                maximum_error = max(errors)
                rows.append(
                    {
                        "case_id": f"organization-confirm-{index:03d}",
                        "truth": {
                            "orientation_degrees": angle,
                            "wavelength_um": wavelength,
                            "spacing_um": spacing,
                        },
                        "measurement": {
                            "tensor_orientation_degrees": list(response.tensor.orientation_degrees),
                            "tensor_coherency": list(response.tensor.coherency),
                            "spectral_orientation_degrees": response.spectral.orientation_degrees,
                            "spectral_anisotropy": response.spectral.anisotropy,
                            "characteristic_wavelength_um": response.characteristic_wavelength_um,
                            "samples_per_characteristic_wavelength": response.samples_per_characteristic_wavelength,
                        },
                        "supported": response.supported,
                        "abstention_reasons": list(response.abstention_reasons),
                        "maximum_tensor_error_degrees": maximum_error,
                        "invalid": maximum_error > 2.5,
                    }
                )
                index += 1
    return rows


def _organization_controls() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spacing = (1.0, 1.0)
    for index in range(5):
        image = np.random.default_rng(710000 + index).normal(size=(192, 192)).astype(np.float32)
        response = validated_tensor_orientation_2d(
            image,
            spacing_um=spacing,
            scales_um=(1.0, 2.0, 4.0),
        )
        rows.append(
            {
                "case_id": f"control-white-noise-{index}",
                "control": "white_noise",
                "measurement": {
                    "spectral_anisotropy": response.spectral.anisotropy,
                    "characteristic_wavelength_um": response.characteristic_wavelength_um,
                    "samples_per_characteristic_wavelength": response.samples_per_characteristic_wavelength,
                },
                "supported": response.supported,
                "abstention_reasons": list(response.abstention_reasons),
                "invalid": True,
            }
        )
    for index, first_angle in enumerate((13.0, 29.0, 51.0, 73.0, 101.0)):
        first = generate_phantom(
            "orientation",
            shape=(192, 192),
            spacing_um=spacing,
            seed=720000 + index,
            angle_degrees=first_angle,
            scale_um=24.0,
        )
        second = generate_phantom(
            "orientation",
            shape=(192, 192),
            spacing_um=spacing,
            seed=730000 + index,
            angle_degrees=(first_angle + 90.0) % 180.0,
            scale_um=24.0,
        )
        image = (0.5 * first.image + 0.5 * second.image).astype(np.float32)
        response = validated_tensor_orientation_2d(
            image,
            spacing_um=spacing,
            scales_um=(1.0, 2.0, 4.0),
        )
        rows.append(
            {
                "case_id": f"control-crossed-{index}",
                "control": "orthogonal_crossed_orientation",
                "measurement": {
                    "spectral_anisotropy": response.spectral.anisotropy,
                    "characteristic_wavelength_um": response.characteristic_wavelength_um,
                    "samples_per_characteristic_wavelength": response.samples_per_characteristic_wavelength,
                },
                "supported": response.supported,
                "abstention_reasons": list(response.abstention_reasons),
                "invalid": True,
            }
        )
    return rows


def _hessian_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spacings = (
        (0.75, 0.75, 0.75),
        (0.75, 0.75, 1.5),
        (1.25, 1.25, 1.25),
    )
    for morphology in ("blob", "tube", "sheet"):
        for radius in (5.0, 7.0, 9.0):
            for spacing in spacings:
                phantom = generate_phantom(
                    morphology,  # type: ignore[arg-type]
                    shape=(56, 56, 56),
                    spacing_um=spacing,
                    scale_um=2.0 * radius,
                )
                scales = tuple(radius * factor for factor in (0.5, 0.75, 1.0, 1.25, 1.5))
                response = validated_hessian_morphology(
                    phantom.image,
                    spacing_um=spacing,
                    scales_um=scales,
                )
                invalid = response.hessian.winning_class != morphology
                rows.append(
                    {
                        "case_id": f"hessian-confirm-{morphology}-r{radius:g}-s{'x'.join(str(v) for v in spacing)}",
                        "truth": {"class": morphology, "radius_um": radius, "spacing_um": list(spacing)},
                        "measurement": {
                            "estimated_class": response.hessian.winning_class,
                            "winning_scale_um": response.hessian.winning_scale_um,
                            "samples_per_winning_scale": response.samples_per_winning_scale,
                            "scale_relative_error": relative_scale_error(
                                response.hessian.winning_scale_um, radius
                            ),
                        },
                        "supported": response.supported,
                        "abstention_reasons": list(response.abstention_reasons),
                        "invalid": invalid,
                    }
                )
    return rows


def _thickness_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for diameter in (10.0, 18.0, 30.0):
        for spacing in ((0.75, 0.75), (1.25, 1.25), (0.75, 1.5)):
            phantom = generate_phantom(
                "thickness", shape=(192, 192), spacing_um=spacing, scale_um=diameter
            )
            response = local_thickness_response(phantom.mask, spacing_um=spacing)
            rows.append(
                {
                    "case_id": f"thickness-sheet2d-d{diameter:g}-s{'x'.join(str(v) for v in spacing)}",
                    "truth_diameter_um": diameter,
                    "spacing_um": list(spacing),
                    "anisotropic": len(set(spacing)) > 1,
                    "estimated_p95_um": response.p95_thickness_um,
                    "relative_error": relative_scale_error(response.p95_thickness_um, diameter),
                }
            )
    for morphology in ("tube", "sheet"):
        for diameter in (10.0, 14.0, 18.0):
            for spacing in ((0.75, 0.75, 0.75), (0.75, 0.75, 1.5)):
                phantom = generate_phantom(
                    morphology,  # type: ignore[arg-type]
                    shape=(56, 56, 56),
                    spacing_um=spacing,
                    scale_um=diameter,
                )
                response = local_thickness_response(phantom.mask, spacing_um=spacing)
                rows.append(
                    {
                        "case_id": f"thickness-{morphology}3d-d{diameter:g}-s{'x'.join(str(v) for v in spacing)}",
                        "truth_diameter_um": diameter,
                        "spacing_um": list(spacing),
                        "anisotropic": len(set(spacing)) > 1,
                        "estimated_p95_um": response.p95_thickness_um,
                        "relative_error": relative_scale_error(response.p95_thickness_um, diameter),
                    }
                )
    return rows


def _network_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for full_width in (6.0, 10.0, 14.0):
        for spacing in ((0.75, 0.75), (1.25, 1.25), (0.75, 1.5)):
            phantom = generate_phantom(
                "network",
                shape=(192, 192),
                spacing_um=spacing,
                scale_um=full_width * 2.5,
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
            estimate = response.fragmentation_threshold
            rows.append(
                {
                    "case_id": f"network-confirm-w{full_width:g}-s{'x'.join(str(v) for v in spacing)}",
                    "truth_fragmentation_threshold_um": half_width,
                    "spacing_um": list(spacing),
                    "thresholds_um": list(thresholds),
                    "estimated_fragmentation_threshold_um": estimate,
                    "fragmentation_relative_error": None
                    if estimate is None
                    else relative_scale_error(estimate, half_width),
                    "surviving_fraction": list(response.surviving_fraction),
                    "monotone": all(
                        left >= right
                        for left, right in zip(
                            response.surviving_fraction, response.surviving_fraction[1:]
                        )
                    ),
                }
            )
    return rows


def _spatial_cases() -> list[dict[str, Any]]:
    separations = (2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, 80.0)
    rows: list[dict[str, Any]] = []
    for correlation in (10.0, 18.0, 26.0):
        for anisotropy in (1.0, 1.8, 2.6):
            for seed_offset in range(5):
                seed = 810000 + int(correlation) * 100 + int(anisotropy * 10) + seed_offset
                phantom = generate_phantom(
                    "heterogeneity",
                    shape=(192, 192),
                    spacing_um=(1.0, 1.0),
                    seed=seed,
                    correlation_length_um=correlation,
                    anisotropy_ratio=anisotropy,
                )
                response = validated_intrinsic_variogram_2d(
                    phantom.image,
                    spacing_um=(1.0, 1.0),
                    separations_um=separations,
                )
                invalid = anisotropy == 1.0 or (
                    response.anisotropy_ratio is not None
                    and relative_scale_error(response.anisotropy_ratio, anisotropy) > 0.55
                )
                rows.append(
                    {
                        "case_id": f"spatial-confirm-c{correlation:g}-a{anisotropy:g}-seed{seed_offset}",
                        "truth": {"correlation_length_um": correlation, "anisotropy_ratio": anisotropy},
                        "measurement": {
                            "median_angular_anisotropy": response.median_angular_anisotropy,
                            "anisotropy_ratio": response.anisotropy_ratio,
                            "axis_consensus_degrees": response.variogram.axis_consensus_degrees,
                            "major_e_fold_range_um": response.variogram.major_e_fold_range_um,
                            "minor_e_fold_range_um": response.variogram.minor_e_fold_range_um,
                        },
                        "supported": response.supported,
                        "abstention_reasons": list(response.abstention_reasons),
                        "relative_ratio_error": None
                        if response.anisotropy_ratio is None
                        else relative_scale_error(response.anisotropy_ratio, anisotropy),
                        "invalid": invalid,
                    }
                )
    return rows


def _perturbation_cases() -> list[dict[str, Any]]:
    reference = generate_phantom(
        "orientation",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=910000,
        angle_degrees=47.0,
        scale_um=27.0,
    )
    perturbations = (
        Perturbation("rotation", 23.0),
        Perturbation("resampling", 0.8),
        Perturbation("crop", 0.75),
        Perturbation("blur", 1.2),
        Perturbation("noise", 0.15),
        Perturbation("contrast", 0.5),
        Perturbation("psf", 1.0),
        Perturbation("partial_volume", 0.65),
    )
    rows = []
    for item in perturbations:
        changed = apply_perturbation(reference, item)
        response = validated_tensor_orientation_2d(
            changed.image,
            spacing_um=(float(changed.truth.spacing_um[0]), float(changed.truth.spacing_um[1])),
            scales_um=(1.0, 2.0, 4.0),
        )
        expected = (47.0 - item.magnitude) % 180.0 if item.kind == "rotation" else 47.0
        error = max(
            axial_angular_error_degrees(value, expected)
            for value in response.tensor.orientation_degrees
        )
        rows.append(
            {
                "case_id": f"perturbation-{item.kind}",
                "perturbation": {"kind": item.kind, "magnitude": item.magnitude, "seed": item.seed},
                "measurement": {
                    "maximum_tensor_error_degrees": error,
                    "samples_per_characteristic_wavelength": response.samples_per_characteristic_wavelength,
                    "spectral_anisotropy": response.spectral.anisotropy,
                },
                "supported": response.supported,
                "abstention_reasons": list(response.abstention_reasons),
                "invalid": error > 2.5,
            }
        )
    return rows


def build_synthetic_physical_truth_v2_1(root: Path) -> dict[str, Any]:
    organization = _organization_cases()
    controls = _organization_controls()
    hessian = _hessian_cases()
    thickness = _thickness_cases()
    network = _network_cases()
    spatial = _spatial_cases()
    perturbations = _perturbation_cases()

    accepted_org = [row for row in organization if row["supported"]]
    org_errors = [float(row["maximum_tensor_error_degrees"]) for row in accepted_org]
    accepted_hessian = [row for row in hessian if row["supported"]]
    classes = ("blob", "tube", "sheet")
    hessian_recalls = {
        label: float(
            np.mean(
                [
                    row["measurement"]["estimated_class"] == label
                    for row in accepted_hessian
                    if row["truth"]["class"] == label
                ]
            )
        )
        for label in classes
    }
    hessian_scale = [float(row["measurement"]["scale_relative_error"]) for row in accepted_hessian]
    thickness_errors = [float(row["relative_error"]) for row in thickness]
    anisotropic_thickness = [float(row["relative_error"]) for row in thickness if row["anisotropic"]]
    network_errors = [
        float(row["fragmentation_relative_error"])
        for row in network
        if row["fragmentation_relative_error"] is not None
    ]
    anisotropic_spatial = [row for row in spatial if row["truth"]["anisotropy_ratio"] > 1.0]
    accepted_spatial = [row for row in anisotropic_spatial if row["supported"]]
    spatial_truth = [float(row["truth"]["anisotropy_ratio"]) for row in accepted_spatial]
    spatial_estimate = [float(row["measurement"]["anisotropy_ratio"]) for row in accepted_spatial]
    spatial_errors = [float(row["relative_ratio_error"]) for row in accepted_spatial]
    isotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] == 1.0]
    metrics = {
        "organization": {
            "cases": len(organization),
            "accepted": len(accepted_org),
            "coverage": len(accepted_org) / len(organization),
            "p95_error_degrees": float(np.percentile(org_errors, 95)),
            "invalid": sum(bool(row["invalid"]) for row in accepted_org),
            "risk": float(np.mean([row["invalid"] for row in accepted_org])),
            "all_errors_above_2_5_rejected": all(
                not row["supported"] for row in organization if row["invalid"]
            ),
        },
        "organization_controls": {
            "controls": len(controls),
            "rejected": sum(not row["supported"] for row in controls),
        },
        "hessian": {
            "cases": len(hessian),
            "accepted": len(accepted_hessian),
            "coverage": len(accepted_hessian) / len(hessian),
            "balanced_accuracy": float(np.mean(list(hessian_recalls.values()))),
            "per_class_recall": hessian_recalls,
            "invalid": sum(bool(row["invalid"]) for row in accepted_hessian),
            "risk": float(np.mean([row["invalid"] for row in accepted_hessian])),
            "all_misclassifications_rejected": all(
                not row["supported"] for row in hessian if row["invalid"]
            ),
            "median_scale_relative_error": float(np.median(hessian_scale)),
            "p95_scale_relative_error": float(np.percentile(hessian_scale, 95)),
        },
        "thickness": {
            "median_relative_error": float(np.median(thickness_errors)),
            "p95_relative_error": float(np.percentile(thickness_errors, 95)),
            "anisotropic_p95_relative_error": float(np.percentile(anisotropic_thickness, 95)),
        },
        "network": {
            "median_fragmentation_relative_error": float(np.median(network_errors)),
            "p95_fragmentation_relative_error": float(np.percentile(network_errors, 95)),
            "all_survival_curves_monotone": all(row["monotone"] for row in network),
        },
        "spatial": {
            "anisotropic_cases": len(anisotropic_spatial),
            "accepted": len(accepted_spatial),
            "anisotropic_coverage": len(accepted_spatial) / len(anisotropic_spatial),
            "isotropic_abstention": float(np.mean([not row["supported"] for row in isotropic])),
            "spearman_rho": float(spearmanr(spatial_truth, spatial_estimate).statistic),
            "median_relative_ratio_error": float(np.median(spatial_errors)),
            "p95_relative_ratio_error": float(np.percentile(spatial_errors, 95)),
        },
        "perturbations": {
            "cases": len(perturbations),
            "accepted": sum(row["supported"] for row in perturbations),
            "all_supported_errors_le_2_5": all(
                row["measurement"]["maximum_tensor_error_degrees"] <= 2.5
                for row in perturbations
                if row["supported"]
            ),
        },
    }
    gates = {
        "organization": (
            metrics["organization"]["coverage"] >= 0.75
            and metrics["organization"]["p95_error_degrees"] <= 2.5
            and metrics["organization"]["risk"] <= 0.02
            and metrics["organization"]["all_errors_above_2_5_rejected"]
        ),
        "organization_controls": metrics["organization_controls"]["rejected"] == 10,
        "hessian_classification": (
            metrics["hessian"]["coverage"] >= 0.60
            and metrics["hessian"]["balanced_accuracy"] >= 0.95
            and min(metrics["hessian"]["per_class_recall"].values()) >= 0.90
            and metrics["hessian"]["risk"] <= 0.05
            and metrics["hessian"]["all_misclassifications_rejected"]
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
            metrics["network"]["median_fragmentation_relative_error"] <= 0.15
            and metrics["network"]["p95_fragmentation_relative_error"] <= 0.35
            and metrics["network"]["all_survival_curves_monotone"]
        ),
        "spatial": (
            metrics["spatial"]["anisotropic_coverage"] >= 0.50
            and metrics["spatial"]["isotropic_abstention"] >= 0.80
            and metrics["spatial"]["spearman_rho"] >= 0.75
            and metrics["spatial"]["median_relative_ratio_error"] <= 0.35
            and metrics["spatial"]["p95_relative_ratio_error"] <= 0.55
        ),
        "perturbations": (
            metrics["perturbations"]["accepted"] >= 6
            and metrics["perturbations"]["all_supported_errors_le_2_5"]
        ),
    }
    fingerprint_rows = organization + controls + hessian + spatial + perturbations
    fingerprint = _geometry_fingerprint(fingerprint_rows)
    complemented = [dict(row, invalid=not bool(row["invalid"])) for row in fingerprint_rows]
    complemented_fingerprint = _geometry_fingerprint(complemented)
    gates["label_complement_geometry_unchanged"] = fingerprint == complemented_fingerprint
    protocol = root / PROTOCOL_PATH
    development = root / DEVELOPMENT_PATH
    validated = root / VALIDATED_RESPONSES_PATH
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": PROTOCOL_PATH,
        "protocol_sha256": _sha256_file(protocol),
        "development": DEVELOPMENT_PATH,
        "development_sha256": _sha256_file(development),
        "validated_responses": VALIDATED_RESPONSES_PATH,
        "validated_responses_sha256": _sha256_file(validated),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "success_gates_before_repeat": gates,
        "label_blindness": {
            "geometry_sha256": fingerprint,
            "label_complement_geometry_sha256": complemented_fingerprint,
            "unchanged": fingerprint == complemented_fingerprint,
        },
        "metrics": metrics,
        "cases": {
            "organization": organization,
            "organization_controls": controls,
            "hessian": hessian,
            "thickness": thickness,
            "network": network,
            "spatial": spatial,
            "perturbations": perturbations,
        },
        "scope": (
            "Disjoint analytic confirmation of fail-closed response support; not biological, "
            "segmentation, acquisition-transfer, clinical, mechanical or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["build_synthetic_physical_truth_v2_1"]
