"""Disjoint terminal confirmation for physical-truth support v2.4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.stats import spearmanr

from nostos.features.validated_responses import (
    validated_gradient_moment_anisotropy_2d,
    validated_hessian_morphology,
)
from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.phantoms import Phantom, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.4-confirmation"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_4_CONFIRMATION_PROTOCOL.md"
DEVELOPMENT_PATH = "outputs/nostos0-synthetic-repair-development-v2-4/development.json"
IMPLEMENTATION_PATH = "src/nostos/features/validated_responses.py"
EVALUATOR_PATH = "src/nostos/validation/synthetic_physical_truth_v2_4.py"


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
        json.dumps(
            geometry, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _hessian_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for morphology in ("blob", "tube", "sheet"):
        for radius in (7.0, 9.0, 11.0):
            for spacing in (
                (0.75, 0.75, 0.75),
                (1.15, 1.15, 1.15),
                (1.15, 1.15, 2.30),
                (1.70, 1.70, 1.70),
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
                    minimum_samples_per_winning_scale=4.75,
                )
                invalid = response.hessian.winning_class != morphology
                rows.append(
                    {
                        "case_id": (
                            f"hessian-v24-{morphology}-r{radius:g}-"
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
    return 1640000 + int(correlation) * 1000 + int(ratio * 100) + offset


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
        minimum_axis_ratio=1.55,
        maximum_stability_score=0.20,
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
    for correlation in (16.0, 24.0, 32.0):
        for ratio in (1.0, 1.6, 2.1, 2.6, 3.1):
            for offset in range(10):
                measured = _measure_spatial(_phantom(correlation, ratio, offset))
                error = relative_scale_error(float(measured["ratio"]), ratio)
                rows.append(
                    {
                        "case_id": (
                            f"spatial-v24-c{correlation:g}-a{ratio:g}-seed{offset}"
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
    for correlation in (16.0, 24.0, 32.0):
        for ratio in (1.6, 2.1, 2.6, 3.1):
            for offset in (0, 1):
                phantom = _phantom(correlation, ratio, offset)
                reference = _measure_spatial(phantom)
                rotated = _measure_spatial(
                    apply_perturbation(phantom, Perturbation("rotation", 37.0))
                )
                resampled = _measure_spatial(
                    apply_perturbation(phantom, Perturbation("resampling", 0.75))
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
                    turn_error = abs(turn - 37.0)
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
                            f"equivariance-v24-c{correlation:g}-a{ratio:g}-seed{offset}"
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


def _hessian_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in rows if row["supported"]]
    recalls: dict[str, float] = {}
    for label in ("blob", "tube", "sheet"):
        class_rows = [row for row in accepted if row["truth"]["class"] == label]
        recalls[label] = float(np.mean([not row["invalid"] for row in class_rows]))
    errors = [row["measurement"]["scale_relative_error"] for row in accepted]
    return {
        "cases": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "raw_invalid": sum(row["invalid"] for row in rows),
        "accepted_invalid": sum(row["invalid"] for row in accepted),
        "accepted_risk": float(np.mean([row["invalid"] for row in accepted])),
        "all_raw_misclassifications_rejected": all(
            not row["supported"] for row in rows if row["invalid"]
        ),
        "balanced_accuracy": float(np.mean(list(recalls.values()))),
        "per_class_recall": recalls,
        "median_scale_relative_error": float(np.median(errors)),
        "p95_scale_relative_error": float(np.percentile(errors, 95)),
    }


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
    truth = [row["truth"]["anisotropy_ratio"] for row in accepted_anisotropic]
    estimate = [row["measurement"]["ratio"] for row in accepted_anisotropic]
    accepted_errors = [row["relative_ratio_error"] for row in accepted_anisotropic]
    raw_errors = [row["relative_ratio_error"] for row in anisotropic]
    return {
        "cases": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "anisotropic_cases": len(anisotropic),
        "accepted_anisotropic": len(accepted_anisotropic),
        "anisotropic_coverage": len(accepted_anisotropic) / len(anisotropic),
        "accepted_isotropic": len(accepted_isotropic),
        "gradient_spearman_rho": float(spearmanr(truth, estimate).statistic),
        "gradient_median_relative_error": float(np.median(accepted_errors)),
        "gradient_p95_relative_error": float(np.percentile(accepted_errors, 95)),
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
        "median_stability_score": float(
            np.median([row["measurement"]["stability_score"] for row in rows])
        ),
    }


def _equivariance_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in rows if row["supported"]]
    rotation = [
        row["measurement"]["rotation_ratio_relative_drift"] for row in accepted
    ]
    resampling = [
        row["measurement"]["resampling_ratio_relative_drift"] for row in accepted
    ]
    turns = [
        row["measurement"]["rotation_turn_error_degrees"]
        for row in accepted
        if row["measurement"]["rotation_turn_error_degrees"] is not None
    ]
    return {
        "cases": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "rotation_median_ratio_drift": float(np.median(rotation)),
        "rotation_p95_ratio_drift": float(np.percentile(rotation, 95)),
        "rotation_axis_cases": len(turns),
        "rotation_p95_turn_error_degrees": float(np.percentile(turns, 95)),
        "resampling_median_ratio_drift": float(np.median(resampling)),
        "resampling_p95_ratio_drift": float(np.percentile(resampling, 95)),
    }


def build_synthetic_physical_truth_v2_4(root: Path) -> dict[str, Any]:
    hessian = _hessian_cases()
    spatial = _spatial_cases()
    equivariance = _equivariance_cases()
    metrics = {
        "hessian": _hessian_metrics(hessian),
        "spatial": _spatial_metrics(spatial),
        "equivariance": _equivariance_metrics(equivariance),
    }
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
        "spatial_support": (
            metrics["spatial"]["coverage"] >= 0.60
            and metrics["spatial"]["anisotropic_coverage"] >= 0.60
            and metrics["spatial"]["accepted_isotropic"] >= 10
        ),
        "gradient_ratio": (
            metrics["spatial"]["gradient_spearman_rho"] >= 0.80
            and metrics["spatial"]["gradient_median_relative_error"] <= 0.10
            and metrics["spatial"]["gradient_p95_relative_error"] <= 0.25
            and metrics["spatial"]["accepted_invalid_risk"] <= 0.05
        ),
        "contract_not_worse_than_always_emit": (
            metrics["spatial"]["accepted_invalid_risk"]
            <= metrics["spatial"]["always_emit_invalid_risk"]
            and metrics["spatial"]["gradient_p95_relative_error"]
            <= metrics["spatial"]["always_emit_p95_relative_error"]
        ),
        "isotropic_behavior": (
            metrics["spatial"]["isotropic_median_ratio"] <= 1.20
            and metrics["spatial"]["isotropic_p95_ratio"] <= 1.50
            and metrics["spatial"]["isotropic_axis_abstention"] >= 0.90
        ),
        "anisotropic_axis_retention": (
            metrics["spatial"]["ratio_ge_2_axis_retention"] >= 0.80
        ),
        "equivariance_support": metrics["equivariance"]["coverage"] >= 0.50,
        "rotation_equivariance": (
            metrics["equivariance"]["rotation_median_ratio_drift"] <= 0.10
            and metrics["equivariance"]["rotation_p95_ratio_drift"] <= 0.20
            and metrics["equivariance"]["rotation_p95_turn_error_degrees"] <= 3.0
        ),
        "resampling_equivariance": (
            metrics["equivariance"]["resampling_median_ratio_drift"] <= 0.10
            and metrics["equivariance"]["resampling_p95_ratio_drift"] <= 0.20
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


__all__ = ["build_synthetic_physical_truth_v2_4"]
