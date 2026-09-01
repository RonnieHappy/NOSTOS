"""Terminal disjoint confirmation for physical-truth repairs v2.2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.stats import spearmanr

from nostos.features.validated_responses import (
    gradient_moment_anisotropy_2d,
    validated_hessian_morphology,
    validated_intrinsic_variogram_2d,
)
from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.phantoms import Phantom, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.2-confirmation"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_2_CONFIRMATION_PROTOCOL.md"
DEVELOPMENT_PATH = "outputs/nostos0-synthetic-repair-development-v2-2/development.json"
IMPLEMENTATION_PATH = "src/nostos/features/validated_responses.py"
SEPARATIONS = (2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, 80.0)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    geometry = [
        {
            "case_id": row["case_id"],
            "supported": row.get("supported"),
            "axis_identifiable": row.get("axis_identifiable"),
            "measurement": row["measurement"],
        }
        for row in rows
    ]
    return hashlib.sha256(
        json.dumps(geometry, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _hessian_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spacings = (
        (0.6, 0.6, 0.6),
        (0.9, 0.9, 0.9),
        (0.9, 0.9, 1.8),
        (1.4, 1.4, 1.4),
    )
    for morphology in ("blob", "tube", "sheet"):
        for radius in (5.5, 7.5, 9.5):
            for spacing in spacings:
                phantom = generate_phantom(
                    morphology,  # type: ignore[arg-type]
                    shape=(64, 64, 64),
                    spacing_um=spacing,
                    scale_um=2.0 * radius,
                )
                scales = tuple(radius * factor for factor in (0.5, 0.75, 1.0, 1.25, 1.5))
                response = validated_hessian_morphology(
                    phantom.image,
                    spacing_um=spacing,
                    scales_um=scales,
                    minimum_samples_per_winning_scale=4.25,
                )
                invalid = response.hessian.winning_class != morphology
                rows.append(
                    {
                        "case_id": f"hessian-v22-{morphology}-r{radius:g}-s{'x'.join(str(v) for v in spacing)}",
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


def _spatial_seed(correlation: float, ratio: float, seed_offset: int) -> int:
    return 1010000 + int(correlation) * 1000 + int(ratio * 100) + seed_offset


def _spatial_phantom(correlation: float, ratio: float, seed_offset: int) -> Phantom:
    return generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=_spatial_seed(correlation, ratio, seed_offset),
        correlation_length_um=correlation,
        anisotropy_ratio=ratio,
    )


def _spatial_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for correlation in (12.0, 20.0, 28.0):
        for ratio in (1.0, 1.5, 2.0, 2.5, 3.0):
            for seed_offset in range(10):
                phantom = _spatial_phantom(correlation, ratio, seed_offset)
                gradient = gradient_moment_anisotropy_2d(
                    phantom.image,
                    spacing_um=(1.0, 1.0),
                )
                intrinsic = validated_intrinsic_variogram_2d(
                    phantom.image,
                    spacing_um=(1.0, 1.0),
                    separations_um=SEPARATIONS,
                )
                error = relative_scale_error(gradient.ratio, ratio)
                rows.append(
                    {
                        "case_id": f"spatial-v22-c{correlation:g}-a{ratio:g}-seed{seed_offset}",
                        "truth": {
                            "correlation_length_um": correlation,
                            "anisotropy_ratio": ratio,
                        },
                        "measurement": {
                            "gradient_moment_ratio": gradient.ratio,
                            "gradient_major_axis_degrees": gradient.major_axis_degrees,
                            "gradient_eigenvalues": list(gradient.eigenvalues),
                            "intrinsic_range_ratio": intrinsic.anisotropy_ratio,
                            "intrinsic_supported": intrinsic.supported,
                        },
                        "supported": True,
                        "axis_identifiable": gradient.axis_identifiable,
                        "relative_ratio_error": error,
                        "invalid": error > 0.25,
                    }
                )
    return rows


def _equivariance_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for correlation in (12.0, 20.0, 28.0):
        for ratio in (1.5, 2.0, 2.5, 3.0):
            for seed_offset in (0, 1):
                phantom = _spatial_phantom(correlation, ratio, seed_offset)
                reference = gradient_moment_anisotropy_2d(
                    phantom.image,
                    spacing_um=(1.0, 1.0),
                )
                rotated_phantom = apply_perturbation(
                    phantom, Perturbation("rotation", 37.0)
                )
                rotated = gradient_moment_anisotropy_2d(
                    rotated_phantom.image,
                    spacing_um=(1.0, 1.0),
                )
                resampled_phantom = apply_perturbation(
                    phantom, Perturbation("resampling", 0.75)
                )
                resampled = gradient_moment_anisotropy_2d(
                    resampled_phantom.image,
                    spacing_um=(
                        float(resampled_phantom.truth.spacing_um[0]),
                        float(resampled_phantom.truth.spacing_um[1]),
                    ),
                )
                turn_error = None
                if reference.major_axis_degrees is not None and rotated.major_axis_degrees is not None:
                    observed_turn = axial_angular_error_degrees(
                        reference.major_axis_degrees,
                        rotated.major_axis_degrees,
                    )
                    turn_error = abs(observed_turn - 37.0)
                rows.append(
                    {
                        "case_id": f"equivariance-c{correlation:g}-a{ratio:g}-seed{seed_offset}",
                        "truth": {"correlation_length_um": correlation, "anisotropy_ratio": ratio},
                        "measurement": {
                            "reference_ratio": reference.ratio,
                            "rotated_ratio": rotated.ratio,
                            "resampled_ratio": resampled.ratio,
                            "reference_axis_degrees": reference.major_axis_degrees,
                            "rotated_axis_degrees": rotated.major_axis_degrees,
                            "rotation_turn_error_degrees": turn_error,
                            "rotation_ratio_relative_drift": relative_scale_error(
                                rotated.ratio, reference.ratio
                            ),
                            "resampling_ratio_relative_drift": relative_scale_error(
                                resampled.ratio, reference.ratio
                            ),
                        },
                        "supported": True,
                        "axis_identifiable": reference.axis_identifiable,
                        "invalid": (
                            relative_scale_error(rotated.ratio, reference.ratio) > 0.20
                            or relative_scale_error(resampled.ratio, reference.ratio) > 0.20
                            or turn_error is not None
                            and turn_error > 3.0
                        ),
                    }
                )
    return rows


def build_synthetic_physical_truth_v2_2(root: Path) -> dict[str, Any]:
    hessian = _hessian_cases()
    spatial = _spatial_cases()
    equivariance = _equivariance_cases()

    accepted_hessian = [row for row in hessian if row["supported"]]
    recalls = {}
    for label in ("blob", "tube", "sheet"):
        class_rows = [row for row in accepted_hessian if row["truth"]["class"] == label]
        recalls[label] = float(np.mean([not row["invalid"] for row in class_rows]))
    hessian_scale = [float(row["measurement"]["scale_relative_error"]) for row in accepted_hessian]
    anisotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] > 1.0]
    isotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] == 1.0]
    truth = [float(row["truth"]["anisotropy_ratio"]) for row in anisotropic]
    gradient_estimate = [float(row["measurement"]["gradient_moment_ratio"]) for row in anisotropic]
    gradient_errors = [float(row["relative_ratio_error"]) for row in anisotropic]
    intrinsic_subset = [
        row for row in anisotropic if row["measurement"]["intrinsic_supported"]
    ]
    intrinsic_truth = [float(row["truth"]["anisotropy_ratio"]) for row in intrinsic_subset]
    intrinsic_estimate = [float(row["measurement"]["intrinsic_range_ratio"]) for row in intrinsic_subset]
    gradient_subset = [float(row["measurement"]["gradient_moment_ratio"]) for row in intrinsic_subset]
    rotation_drift = [float(row["measurement"]["rotation_ratio_relative_drift"]) for row in equivariance]
    resampling_drift = [float(row["measurement"]["resampling_ratio_relative_drift"]) for row in equivariance]
    turn_errors = [
        float(row["measurement"]["rotation_turn_error_degrees"])
        for row in equivariance
        if row["measurement"]["rotation_turn_error_degrees"] is not None
    ]
    metrics = {
        "hessian": {
            "cases": len(hessian),
            "accepted": len(accepted_hessian),
            "coverage": len(accepted_hessian) / len(hessian),
            "raw_invalid": sum(row["invalid"] for row in hessian),
            "accepted_invalid": sum(row["invalid"] for row in accepted_hessian),
            "accepted_risk": float(np.mean([row["invalid"] for row in accepted_hessian])),
            "all_raw_misclassifications_rejected": all(
                not row["supported"] for row in hessian if row["invalid"]
            ),
            "balanced_accuracy": float(np.mean(list(recalls.values()))),
            "per_class_recall": recalls,
            "median_scale_relative_error": float(np.median(hessian_scale)),
            "p95_scale_relative_error": float(np.percentile(hessian_scale, 95)),
        },
        "spatial": {
            "anisotropic_cases": len(anisotropic),
            "gradient_spearman_rho": float(spearmanr(truth, gradient_estimate).statistic),
            "gradient_median_relative_error": float(np.median(gradient_errors)),
            "gradient_p95_relative_error": float(np.percentile(gradient_errors, 95)),
            "isotropic_median_ratio": float(
                np.median([row["measurement"]["gradient_moment_ratio"] for row in isotropic])
            ),
            "isotropic_p95_ratio": float(
                np.percentile([row["measurement"]["gradient_moment_ratio"] for row in isotropic], 95)
            ),
            "isotropic_axis_abstention": float(
                np.mean([not row["axis_identifiable"] for row in isotropic])
            ),
            "ratio_ge_2_axis_retention": float(
                np.mean(
                    [
                        row["axis_identifiable"]
                        for row in spatial
                        if row["truth"]["anisotropy_ratio"] >= 2.0
                    ]
                )
            ),
            "intrinsic_comparator_cases": len(intrinsic_subset),
            "intrinsic_comparator_spearman_rho": None
            if len(set(intrinsic_truth)) < 2
            else float(spearmanr(intrinsic_truth, intrinsic_estimate).statistic),
            "gradient_on_intrinsic_subset_spearman_rho": None
            if len(set(intrinsic_truth)) < 2
            else float(spearmanr(intrinsic_truth, gradient_subset).statistic),
        },
        "equivariance": {
            "cases": len(equivariance),
            "rotation_median_ratio_drift": float(np.median(rotation_drift)),
            "rotation_p95_ratio_drift": float(np.percentile(rotation_drift, 95)),
            "rotation_axis_cases": len(turn_errors),
            "rotation_p95_turn_error_degrees": float(np.percentile(turn_errors, 95)),
            "resampling_median_ratio_drift": float(np.median(resampling_drift)),
            "resampling_p95_ratio_drift": float(np.percentile(resampling_drift, 95)),
        },
    }
    comparator_rho = metrics["spatial"]["intrinsic_comparator_spearman_rho"]
    gradient_subset_rho = metrics["spatial"]["gradient_on_intrinsic_subset_spearman_rho"]
    gates = {
        "hessian_classification": (
            metrics["hessian"]["coverage"] >= 0.60
            and metrics["hessian"]["balanced_accuracy"] >= 0.95
            and min(metrics["hessian"]["per_class_recall"].values()) >= 0.90
            and metrics["hessian"]["accepted_risk"] <= 0.05
            and metrics["hessian"]["all_raw_misclassifications_rejected"]
        ),
        "hessian_scale": (
            metrics["hessian"]["median_scale_relative_error"] <= 0.35
            and metrics["hessian"]["p95_scale_relative_error"] <= 0.50
        ),
        "gradient_ratio": (
            metrics["spatial"]["gradient_spearman_rho"] >= 0.80
            and metrics["spatial"]["gradient_median_relative_error"] <= 0.10
            and metrics["spatial"]["gradient_p95_relative_error"] <= 0.25
        ),
        "isotropic_behavior": (
            metrics["spatial"]["isotropic_median_ratio"] <= 1.20
            and metrics["spatial"]["isotropic_p95_ratio"] <= 1.50
            and metrics["spatial"]["isotropic_axis_abstention"] >= 0.90
        ),
        "anisotropic_axis_retention": metrics["spatial"]["ratio_ge_2_axis_retention"] >= 0.80,
        "rotation_equivariance": (
            metrics["equivariance"]["rotation_median_ratio_drift"] <= 0.10
            and metrics["equivariance"]["rotation_p95_ratio_drift"] <= 0.20
            and metrics["equivariance"]["rotation_p95_turn_error_degrees"] <= 3.0
        ),
        "resampling_equivariance": (
            metrics["equivariance"]["resampling_median_ratio_drift"] <= 0.10
            and metrics["equivariance"]["resampling_p95_ratio_drift"] <= 0.20
        ),
        "intrinsic_comparator_noninferiority": (
            comparator_rho is not None
            and gradient_subset_rho is not None
            and gradient_subset_rho >= comparator_rho - 0.05
        ),
    }
    fingerprint_rows = hessian + spatial + equivariance
    fingerprint = _fingerprint(fingerprint_rows)
    complemented = [dict(row, invalid=not bool(row["invalid"])) for row in fingerprint_rows]
    complement_fingerprint = _fingerprint(complemented)
    gates["label_complement_geometry_unchanged"] = fingerprint == complement_fingerprint
    protocol = root / PROTOCOL_PATH
    development = root / DEVELOPMENT_PATH
    implementation = root / IMPLEMENTATION_PATH
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": PROTOCOL_PATH,
        "protocol_sha256": _hash(protocol),
        "development": DEVELOPMENT_PATH,
        "development_sha256": _hash(development),
        "implementation": IMPLEMENTATION_PATH,
        "implementation_sha256": _hash(implementation),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "success_gates_before_repeat": gates,
        "label_blindness": {
            "geometry_sha256": fingerprint,
            "label_complement_geometry_sha256": complement_fingerprint,
            "unchanged": fingerprint == complement_fingerprint,
        },
        "metrics": metrics,
        "cases": {"hessian": hessian, "spatial": spatial, "equivariance": equivariance},
        "scope": (
            "Disjoint analytic confirmation of fail-closed Hessian support and untrained "
            "gradient-moment anisotropy; not biological, segmentation, clinical, mechanical "
            "or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["build_synthetic_physical_truth_v2_2"]
