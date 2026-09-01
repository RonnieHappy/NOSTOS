"""Disjoint confirmation of the boundary-robust v2.6 spatial contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from nostos.features.validated_responses_v2_6 import (
    validated_boundary_robust_gradient_anisotropy_2d,
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
)


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.6-confirmation"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_6_CONFIRMATION_PROTOCOL.md"
DEVELOPMENT_PATH = "outputs/nostos0-spatial-estimator-development-v2-6/development.json"
IMPLEMENTATION_PATH = "src/nostos/features/validated_responses_v2_6.py"
EVALUATOR_PATH = "src/nostos/validation/synthetic_physical_truth_v2_6.py"
METRIC_HELPER_PATH = "src/nostos/validation/synthetic_physical_truth_v2_4.py"


def _hessian_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for morphology in ("blob", "tube", "sheet"):
        for radius in (8.0, 10.0, 12.0):
            for spacing in (
                (0.85, 0.85, 0.85),
                (1.25, 1.25, 1.25),
                (1.25, 1.25, 2.50),
                (1.90, 1.90, 1.90),
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
                            f"hessian-v26-{morphology}-r{radius:g}-"
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


def _seed(shape: int, correlation: float, ratio: float, offset: int) -> int:
    return (
        2460000
        + shape * 10000
        + int(correlation) * 100
        + int(round(ratio * 10.0)) * 10
        + offset
    )


def _phantom(
    shape: int, correlation: float, ratio: float, offset: int
) -> Phantom:
    return generate_phantom(
        "heterogeneity",
        shape=(shape, shape),
        spacing_um=(1.0, 1.0),
        seed=_seed(shape, correlation, ratio, offset),
        correlation_length_um=correlation,
        anisotropy_ratio=ratio,
    )


def _measure_spatial(phantom: Phantom) -> dict[str, Any]:
    response = validated_boundary_robust_gradient_anisotropy_2d(
        phantom.image,
        spacing_um=(
            float(phantom.truth.spacing_um[0]),
            float(phantom.truth.spacing_um[1]),
        ),
    )
    return {
        "ratio": response.response.ratio,
        "major_axis_degrees": response.response.major_axis_degrees,
        "axis_identifiable": response.response.axis_identifiable,
        "full_field_eigenvalues": list(response.response.full_field_eigenvalues),
        "tapered_eigenvalues": list(response.response.tapered_eigenvalues),
        "tapered_ratio": response.response.tapered_ratio,
        "characteristic_wavelength_um": response.characteristic_wavelength_um,
        "characteristic_spans": response.characteristic_spans,
        "quadrant_median_log_drift": response.quadrant_median_log_drift,
        "nested_log_drift": response.nested_log_drift,
        "stability_score": response.stability_score,
        "supported": response.supported,
        "abstention_reasons": list(response.abstention_reasons),
    }


def _spatial_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shape in (192, 288, 384):
        for correlation in (20.0, 28.0, 36.0):
            for ratio in (1.0, 1.8, 2.3, 2.8, 3.3):
                for offset in range(6):
                    measured = _measure_spatial(
                        _phantom(shape, correlation, ratio, offset)
                    )
                    error = relative_scale_error(float(measured["ratio"]), ratio)
                    rows.append(
                        {
                            "case_id": (
                                f"spatial-v26-n{shape}-c{correlation:g}-"
                                f"a{ratio:g}-seed{offset}"
                            ),
                            "truth": {
                                "shape": [shape, shape],
                                "correlation_length_um": correlation,
                                "anisotropy_ratio": ratio,
                            },
                            "measurement": measured,
                            "supported": bool(measured["supported"]),
                            "axis_identifiable": bool(
                                measured["axis_identifiable"]
                            ),
                            "abstention_reasons": measured["abstention_reasons"],
                            "relative_ratio_error": error,
                            "invalid": error > 0.25,
                        }
                    )
    return rows


def _equivariance_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for correlation in (20.0, 28.0, 36.0):
        for ratio in (1.8, 2.3, 2.8, 3.3):
            for offset in (0, 1):
                phantom = _phantom(384, correlation, ratio, offset)
                reference = _measure_spatial(phantom)
                rotated = _measure_spatial(
                    apply_perturbation(phantom, Perturbation("rotation", 39.0))
                )
                resampled = _measure_spatial(
                    apply_perturbation(phantom, Perturbation("resampling", 0.82))
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
                    turn_error = abs(turn - 39.0)
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
                            f"equivariance-v26-n384-c{correlation:g}-"
                            f"a{ratio:g}-seed{offset}"
                        ),
                        "truth": {
                            "shape": [384, 384],
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


def _spatial_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in rows if row["supported"]]
    anisotropic = [row for row in rows if row["truth"]["anisotropy_ratio"] > 1.0]
    accepted_anisotropic = [row for row in anisotropic if row["supported"]]
    isotropic = [row for row in rows if row["truth"]["anisotropy_ratio"] == 1.0]
    accepted_isotropic = [row for row in isotropic if row["supported"]]
    high = [
        row
        for row in accepted
        if row["truth"]["anisotropy_ratio"] >= 2.0
    ]
    errors = [row["relative_ratio_error"] for row in accepted_anisotropic]
    raw_errors = [row["relative_ratio_error"] for row in anisotropic]
    truth = [row["truth"]["anisotropy_ratio"] for row in accepted_anisotropic]
    estimate = [row["measurement"]["ratio"] for row in accepted_anisotropic]
    coverage_by_shape = {
        str(shape): float(
            np.mean(
                [
                    row["supported"]
                    for row in rows
                    if row["truth"]["shape"][0] == shape
                ]
            )
        )
        for shape in (192, 288, 384)
    }
    low_span = [
        row for row in rows if row["measurement"]["characteristic_spans"] < 2.25
    ]
    return {
        "cases": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "coverage_by_shape": coverage_by_shape,
        "anisotropic_cases": len(anisotropic),
        "accepted_anisotropic": len(accepted_anisotropic),
        "anisotropic_coverage": len(accepted_anisotropic) / len(anisotropic),
        "accepted_isotropic": len(accepted_isotropic),
        "gradient_spearman_rho": float(spearmanr(truth, estimate).statistic),
        "gradient_median_relative_error": float(np.median(errors)),
        "gradient_p95_relative_error": float(np.percentile(errors, 95)),
        "always_emit_p95_relative_error": float(np.percentile(raw_errors, 95)),
        "accepted_invalid_risk": float(
            np.mean([row["invalid"] for row in accepted_anisotropic])
        ),
        "always_emit_invalid_risk": float(
            np.mean([row["invalid"] for row in anisotropic])
        ),
        "isotropic_median_ratio": float(
            np.median([row["measurement"]["ratio"] for row in accepted_isotropic])
        ),
        "isotropic_p95_ratio": float(
            np.percentile(
                [row["measurement"]["ratio"] for row in accepted_isotropic], 95
            )
        ),
        "isotropic_axis_abstention": float(
            np.mean([not row["axis_identifiable"] for row in accepted_isotropic])
        ),
        "ratio_ge_2_axis_retention": float(
            np.mean([row["axis_identifiable"] for row in high])
        ),
        "low_span_cases": len(low_span),
        "low_span_rejection": float(
            np.mean([not row["supported"] for row in low_span])
        ),
        "all_emitted_meet_span_floor": all(
            row["measurement"]["characteristic_spans"] >= 2.25
            for row in accepted
        ),
    }


def build_synthetic_physical_truth_v2_6(root: Path) -> dict[str, Any]:
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
            spatial_metrics["coverage"] >= 0.50
            and spatial_metrics["anisotropic_coverage"] >= 0.50
            and spatial_metrics["accepted_isotropic"] >= 15
            and spatial_metrics["coverage_by_shape"]["384"] >= 0.70
            and spatial_metrics["coverage_by_shape"]["384"]
            >= spatial_metrics["coverage_by_shape"]["192"]
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
        "field_support_integrity": (
            spatial_metrics["low_span_rejection"] == 1.0
            and spatial_metrics["all_emitted_meet_span_floor"]
        ),
        "equivariance_support": equivariance_metrics["coverage"] >= 0.60,
        "rotation_axis_availability": (
            equivariance_metrics["rotation_axis_coverage"] >= 0.70
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
        "metric_helper": METRIC_HELPER_PATH,
        "metric_helper_sha256": _hash(root / METRIC_HELPER_PATH),
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
            "responses and finite-field abstention; not biological, segmentation, "
            "clinical, mechanical, acquisition-transfer or intraoperative validation."
        ),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["build_synthetic_physical_truth_v2_6"]
