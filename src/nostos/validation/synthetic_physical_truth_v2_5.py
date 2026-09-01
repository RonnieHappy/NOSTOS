"""Disjoint confirmation of v2.5 sampling and axis support thresholds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nostos.features.validated_responses_v2_5 import (
    validated_gradient_moment_anisotropy_2d,
    validated_hessian_morphology,
)
from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.phantoms import Phantom, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation
from nostos.validation.synthetic_physical_truth_v2_4 import (
    _equivariance_metrics,
    _fingerprint,
    _hash,
    _hessian_metrics,
    _spatial_metrics,
)


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.5-confirmation"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_5_CONFIRMATION_PROTOCOL.md"
DEVELOPMENT_PATH = "outputs/nostos0-synthetic-repair-development-v2-5/development.json"
IMPLEMENTATION_PATH = "src/nostos/features/validated_responses_v2_5.py"
EVALUATOR_PATH = "src/nostos/validation/synthetic_physical_truth_v2_5.py"


def _hessian_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for morphology in ("blob", "tube", "sheet"):
        for radius in (7.5, 9.5, 11.5):
            for spacing in (
                (0.80, 0.80, 0.80),
                (1.20, 1.20, 1.20),
                (1.20, 1.20, 2.40),
                (1.80, 1.80, 1.80),
            ):
                phantom = generate_phantom(
                    morphology,  # type: ignore[arg-type]
                    shape=(64, 64, 64),
                    spacing_um=spacing,
                    scale_um=2.0 * radius,
                )
                scales = tuple(
                    radius * factor for factor in (0.50, 0.75, 1.00, 1.25, 1.50)
                )
                response = validated_hessian_morphology(
                    phantom.image,
                    spacing_um=spacing,
                    scales_um=scales,
                )
                invalid = response.hessian.winning_class != morphology
                rows.append(
                    {
                        "case_id": (
                            f"hessian-v25-{morphology}-r{radius:g}-"
                            f"s{'x'.join(str(value) for value in spacing)}"
                        ),
                        "truth": {
                            "class": morphology,
                            "radius_um": radius,
                            "spacing_um": list(spacing),
                        },
                        "measurement": {
                            "estimated_class": response.hessian.winning_class,
                            "winning_scale_um": response.hessian.winning_scale_um,
                            "samples_per_winning_scale": (
                                response.samples_per_winning_scale
                            ),
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


def _seed(correlation: float, ratio: float, offset: int) -> int:
    return 2050000 + int(correlation) * 1000 + int(ratio * 100) + offset


def _phantom(correlation: float, ratio: float, offset: int) -> Phantom:
    return generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=_seed(correlation, ratio, offset),
        correlation_length_um=correlation,
        anisotropy_ratio=ratio,
    )


def _measure_spatial(phantom: Phantom) -> dict[str, Any]:
    response = validated_gradient_moment_anisotropy_2d(
        phantom.image,
        spacing_um=(
            float(phantom.truth.spacing_um[0]),
            float(phantom.truth.spacing_um[1]),
        ),
    )
    return {
        "ratio": response.response.ratio,
        "major_axis_degrees": response.response.major_axis_degrees,
        "eigenvalues": list(response.response.eigenvalues),
        "axis_identifiable": response.response.axis_identifiable,
        "quadrant_median_log_drift": response.quadrant_median_log_drift,
        "nested_log_drift": response.nested_log_drift,
        "stability_score": response.stability_score,
        "supported": response.supported,
        "abstention_reasons": list(response.abstention_reasons),
    }


def _spatial_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for correlation in (18.0, 26.0, 34.0):
        for ratio in (1.0, 1.7, 2.2, 2.7, 3.2):
            for offset in range(10):
                measured = _measure_spatial(_phantom(correlation, ratio, offset))
                error = relative_scale_error(float(measured["ratio"]), ratio)
                rows.append(
                    {
                        "case_id": (
                            f"spatial-v25-c{correlation:g}-a{ratio:g}-seed{offset}"
                        ),
                        "truth": {
                            "correlation_length_um": correlation,
                            "anisotropy_ratio": ratio,
                        },
                        "measurement": measured,
                        "supported": bool(measured["supported"]),
                        "axis_identifiable": bool(measured["axis_identifiable"]),
                        "abstention_reasons": measured["abstention_reasons"],
                        "relative_ratio_error": error,
                        "invalid": error > 0.25,
                    }
                )
    return rows


def _equivariance_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for correlation in (18.0, 26.0, 34.0):
        for ratio in (1.7, 2.2, 2.7, 3.2):
            for offset in (0, 1):
                phantom = _phantom(correlation, ratio, offset)
                reference = _measure_spatial(phantom)
                rotated = _measure_spatial(
                    apply_perturbation(phantom, Perturbation("rotation", 43.0))
                )
                resampled = _measure_spatial(
                    apply_perturbation(phantom, Perturbation("resampling", 0.70))
                )
                turn_error = None
                if (
                    reference["major_axis_degrees"] is not None
                    and rotated["major_axis_degrees"] is not None
                ):
                    turn = axial_angular_error_degrees(
                        float(reference["major_axis_degrees"]),
                        float(rotated["major_axis_degrees"]),
                    )
                    turn_error = abs(turn - 43.0)
                rotation_drift = relative_scale_error(
                    float(rotated["ratio"]), float(reference["ratio"])
                )
                resampling_drift = relative_scale_error(
                    float(resampled["ratio"]), float(reference["ratio"])
                )
                supported = bool(
                    reference["supported"]
                    and rotated["supported"]
                    and resampled["supported"]
                )
                rows.append(
                    {
                        "case_id": (
                            f"equivariance-v25-c{correlation:g}-a{ratio:g}-seed{offset}"
                        ),
                        "truth": {
                            "correlation_length_um": correlation,
                            "anisotropy_ratio": ratio,
                        },
                        "measurement": {
                            "reference": reference,
                            "rotated": rotated,
                            "resampled": resampled,
                            "rotation_turn_error_degrees": turn_error,
                            "rotation_ratio_relative_drift": rotation_drift,
                            "resampling_ratio_relative_drift": resampling_drift,
                        },
                        "supported": supported,
                        "axis_identifiable": bool(
                            reference["axis_identifiable"]
                            and rotated["axis_identifiable"]
                        ),
                        "invalid": (
                            rotation_drift > 0.20
                            or resampling_drift > 0.20
                            or (turn_error is not None and turn_error > 3.0)
                        ),
                    }
                )
    return rows


def build_synthetic_physical_truth_v2_5(root: Path) -> dict[str, Any]:
    hessian = _hessian_cases()
    spatial = _spatial_cases()
    equivariance = _equivariance_cases()
    hessian_metrics = _hessian_metrics(hessian)
    spatial_metrics = _spatial_metrics(spatial)
    equivariance_metrics = _equivariance_metrics(equivariance)
    equivariance_metrics["rotation_axis_coverage"] = (
        equivariance_metrics["rotation_axis_cases"]
        / equivariance_metrics["accepted"]
    )
    metrics = {
        "hessian": hessian_metrics,
        "spatial": spatial_metrics,
        "equivariance": equivariance_metrics,
    }
    gates = {
        "hessian_classification": (
            hessian_metrics["coverage"] >= 0.60
            and hessian_metrics["balanced_accuracy"] >= 0.95
            and min(hessian_metrics["per_class_recall"].values()) >= 0.90
            and hessian_metrics["accepted_risk"] <= 0.05
            and hessian_metrics["all_raw_misclassifications_rejected"]
        ),
        "hessian_scale": (
            hessian_metrics["median_scale_relative_error"] <= 0.35
            and hessian_metrics["p95_scale_relative_error"] <= 0.50
        ),
        "spatial_support": (
            spatial_metrics["coverage"] >= 0.60
            and spatial_metrics["anisotropic_coverage"] >= 0.60
            and spatial_metrics["accepted_isotropic"] >= 10
        ),
        "gradient_ratio": (
            spatial_metrics["gradient_spearman_rho"] >= 0.80
            and spatial_metrics["gradient_median_relative_error"] <= 0.10
            and spatial_metrics["gradient_p95_relative_error"] <= 0.25
            and spatial_metrics["accepted_invalid_risk"] <= 0.05
        ),
        "contract_not_worse_than_always_emit": (
            spatial_metrics["accepted_invalid_risk"]
            <= spatial_metrics["always_emit_invalid_risk"]
            and spatial_metrics["gradient_p95_relative_error"]
            <= spatial_metrics["always_emit_p95_relative_error"]
        ),
        "isotropic_behavior": (
            spatial_metrics["isotropic_median_ratio"] <= 1.20
            and spatial_metrics["isotropic_p95_ratio"] <= 1.50
            and spatial_metrics["isotropic_axis_abstention"] >= 0.90
        ),
        "anisotropic_axis_retention": (
            spatial_metrics["ratio_ge_2_axis_retention"] >= 0.80
        ),
        "equivariance_support": equivariance_metrics["coverage"] >= 0.50,
        "rotation_axis_availability": (
            equivariance_metrics["rotation_axis_coverage"] >= 0.60
        ),
        "rotation_equivariance": (
            equivariance_metrics["rotation_median_ratio_drift"] <= 0.10
            and equivariance_metrics["rotation_p95_ratio_drift"] <= 0.20
            and equivariance_metrics["rotation_p95_turn_error_degrees"] <= 3.0
        ),
        "resampling_equivariance": (
            equivariance_metrics["resampling_median_ratio_drift"] <= 0.10
            and equivariance_metrics["resampling_p95_ratio_drift"] <= 0.20
        ),
    }
    rows = hessian + spatial + equivariance
    fingerprint = _fingerprint(rows)
    complement = _fingerprint(
        [dict(row, invalid=not row["invalid"]) for row in rows]
    )
    gates["label_complement_geometry_unchanged"] = fingerprint == complement
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": PROTOCOL_PATH,
        "protocol_sha256": _hash(root / PROTOCOL_PATH),
        "development": DEVELOPMENT_PATH,
        "development_sha256": _hash(root / DEVELOPMENT_PATH),
        "implementation": IMPLEMENTATION_PATH,
        "implementation_sha256": _hash(root / IMPLEMENTATION_PATH),
        "evaluator": EVALUATOR_PATH,
        "evaluator_sha256": _hash(root / EVALUATOR_PATH),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "success_gates_before_repeat": gates,
        "label_blindness": {
            "geometry_sha256": fingerprint,
            "label_complement_geometry_sha256": complement,
            "unchanged": fingerprint == complement,
        },
        "metrics": metrics,
        "cases": {
            "hessian": hessian,
            "spatial": spatial,
            "equivariance": equivariance,
        },
        "scope": (
            "Disjoint analytic confirmation of calibrated synthetic 2-D/3-D "
            "responses; not biological, segmentation, clinical, mechanical, "
            "acquisition-transfer or intraoperative validation."
        ),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["build_synthetic_physical_truth_v2_5"]
