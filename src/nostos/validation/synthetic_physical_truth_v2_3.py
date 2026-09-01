"""Disjoint terminal confirmation for physical-truth support v2.3."""

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
)
from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.phantoms import Phantom, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


PROTOCOL_VERSION = "nostos-synthetic-physical-truth/2.3-confirmation"
PROTOCOL_PATH = "docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_3_CONFIRMATION_PROTOCOL.md"
DEVELOPMENT_PATH = "outputs/nostos0-synthetic-repair-development-v2-3/development.json"
IMPLEMENTATION_PATH = "src/nostos/features/validated_responses.py"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    data = [
        {
            "case_id": row["case_id"],
            "supported": row.get("supported"),
            "axis_identifiable": row.get("axis_identifiable"),
            "measurement": row["measurement"],
        }
        for row in rows
    ]
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _hessian_cases() -> list[dict[str, Any]]:
    rows = []
    for morphology in ("blob", "tube", "sheet"):
        for radius in (6.5, 8.5, 10.5):
            for spacing in (
                (0.7, 0.7, 0.7),
                (1.1, 1.1, 1.1),
                (1.1, 1.1, 2.2),
                (1.6, 1.6, 1.6),
            ):
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
                    minimum_samples_per_winning_scale=4.75,
                )
                invalid = response.hessian.winning_class != morphology
                rows.append(
                    {
                        "case_id": f"hessian-v23-{morphology}-r{radius:g}-s{'x'.join(str(v) for v in spacing)}",
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


def _seed(correlation: float, ratio: float, offset: int) -> int:
    return 1210000 + int(correlation) * 1000 + int(ratio * 100) + offset


def _phantom(correlation: float, ratio: float, offset: int) -> Phantom:
    return generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=_seed(correlation, ratio, offset),
        correlation_length_um=correlation,
        anisotropy_ratio=ratio,
    )


def _spatial_cases() -> list[dict[str, Any]]:
    rows = []
    for correlation in (14.0, 22.0, 30.0):
        for ratio in (1.0, 1.4, 1.8, 2.2, 2.8, 3.2):
            for offset in range(10):
                phantom = _phantom(correlation, ratio, offset)
                response = gradient_moment_anisotropy_2d(
                    phantom.image,
                    spacing_um=(1.0, 1.0),
                    minimum_axis_ratio=1.55,
                )
                error = relative_scale_error(response.ratio, ratio)
                rows.append(
                    {
                        "case_id": f"spatial-v23-c{correlation:g}-a{ratio:g}-seed{offset}",
                        "truth": {"correlation_length_um": correlation, "anisotropy_ratio": ratio},
                        "measurement": {
                            "gradient_moment_ratio": response.ratio,
                            "major_axis_degrees": response.major_axis_degrees,
                            "eigenvalues": list(response.eigenvalues),
                        },
                        "supported": True,
                        "axis_identifiable": response.axis_identifiable,
                        "relative_ratio_error": error,
                        "invalid": error > 0.25,
                    }
                )
    return rows


def _equivariance_cases() -> list[dict[str, Any]]:
    rows = []
    for correlation in (14.0, 22.0, 30.0):
        for ratio in (1.4, 1.8, 2.2, 2.8, 3.2):
            for offset in (0, 1):
                phantom = _phantom(correlation, ratio, offset)
                reference = gradient_moment_anisotropy_2d(
                    phantom.image, spacing_um=(1.0, 1.0), minimum_axis_ratio=1.55
                )
                rotated_phantom = apply_perturbation(
                    phantom, Perturbation("rotation", 41.0)
                )
                rotated = gradient_moment_anisotropy_2d(
                    rotated_phantom.image,
                    spacing_um=(1.0, 1.0),
                    minimum_axis_ratio=1.55,
                )
                resampled_phantom = apply_perturbation(
                    phantom, Perturbation("resampling", 0.8)
                )
                resampled = gradient_moment_anisotropy_2d(
                    resampled_phantom.image,
                    spacing_um=(
                        float(resampled_phantom.truth.spacing_um[0]),
                        float(resampled_phantom.truth.spacing_um[1]),
                    ),
                    minimum_axis_ratio=1.55,
                )
                turn_error = None
                if reference.major_axis_degrees is not None and rotated.major_axis_degrees is not None:
                    turn = axial_angular_error_degrees(
                        reference.major_axis_degrees, rotated.major_axis_degrees
                    )
                    turn_error = abs(turn - 41.0)
                rotation_drift = relative_scale_error(rotated.ratio, reference.ratio)
                resampling_drift = relative_scale_error(resampled.ratio, reference.ratio)
                rows.append(
                    {
                        "case_id": f"equivariance-v23-c{correlation:g}-a{ratio:g}-seed{offset}",
                        "truth": {"correlation_length_um": correlation, "anisotropy_ratio": ratio},
                        "measurement": {
                            "reference_ratio": reference.ratio,
                            "rotated_ratio": rotated.ratio,
                            "resampled_ratio": resampled.ratio,
                            "reference_axis_degrees": reference.major_axis_degrees,
                            "rotated_axis_degrees": rotated.major_axis_degrees,
                            "rotation_turn_error_degrees": turn_error,
                            "rotation_ratio_relative_drift": rotation_drift,
                            "resampling_ratio_relative_drift": resampling_drift,
                        },
                        "supported": True,
                        "axis_identifiable": reference.axis_identifiable,
                        "invalid": (
                            rotation_drift > 0.20
                            or resampling_drift > 0.20
                            or turn_error is not None
                            and turn_error > 3.0
                        ),
                    }
                )
    return rows


def build_synthetic_physical_truth_v2_3(root: Path) -> dict[str, Any]:
    hessian = _hessian_cases()
    spatial = _spatial_cases()
    equivariance = _equivariance_cases()
    accepted = [row for row in hessian if row["supported"]]
    recalls = {}
    for label in ("blob", "tube", "sheet"):
        class_rows = [row for row in accepted if row["truth"]["class"] == label]
        recalls[label] = float(np.mean([not row["invalid"] for row in class_rows]))
    scale_errors = [row["measurement"]["scale_relative_error"] for row in accepted]
    anisotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] > 1.0]
    isotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] == 1.0]
    truth = [row["truth"]["anisotropy_ratio"] for row in anisotropic]
    estimate = [row["measurement"]["gradient_moment_ratio"] for row in anisotropic]
    errors = [row["relative_ratio_error"] for row in anisotropic]
    rotation = [row["measurement"]["rotation_ratio_relative_drift"] for row in equivariance]
    resampling = [row["measurement"]["resampling_ratio_relative_drift"] for row in equivariance]
    turns = [
        row["measurement"]["rotation_turn_error_degrees"]
        for row in equivariance
        if row["measurement"]["rotation_turn_error_degrees"] is not None
    ]
    metrics = {
        "hessian": {
            "cases": len(hessian),
            "accepted": len(accepted),
            "coverage": len(accepted) / len(hessian),
            "raw_invalid": sum(row["invalid"] for row in hessian),
            "accepted_invalid": sum(row["invalid"] for row in accepted),
            "accepted_risk": float(np.mean([row["invalid"] for row in accepted])),
            "all_raw_misclassifications_rejected": all(
                not row["supported"] for row in hessian if row["invalid"]
            ),
            "balanced_accuracy": float(np.mean(list(recalls.values()))),
            "per_class_recall": recalls,
            "median_scale_relative_error": float(np.median(scale_errors)),
            "p95_scale_relative_error": float(np.percentile(scale_errors, 95)),
        },
        "spatial": {
            "gradient_spearman_rho": float(spearmanr(truth, estimate).statistic),
            "gradient_median_relative_error": float(np.median(errors)),
            "gradient_p95_relative_error": float(np.percentile(errors, 95)),
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
        },
        "equivariance": {
            "cases": len(equivariance),
            "rotation_median_ratio_drift": float(np.median(rotation)),
            "rotation_p95_ratio_drift": float(np.percentile(rotation, 95)),
            "rotation_axis_cases": len(turns),
            "rotation_p95_turn_error_degrees": float(np.percentile(turns, 95)),
            "resampling_median_ratio_drift": float(np.median(resampling)),
            "resampling_p95_ratio_drift": float(np.percentile(resampling, 95)),
        },
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
    }
    rows = hessian + spatial + equivariance
    fingerprint = _fingerprint(rows)
    complement = _fingerprint([dict(row, invalid=not row["invalid"]) for row in rows])
    gates["label_complement_geometry_unchanged"] = fingerprint == complement
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": PROTOCOL_PATH,
        "protocol_sha256": _hash(root / PROTOCOL_PATH),
        "development": DEVELOPMENT_PATH,
        "development_sha256": _hash(root / DEVELOPMENT_PATH),
        "implementation": IMPLEMENTATION_PATH,
        "implementation_sha256": _hash(root / IMPLEMENTATION_PATH),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "success_gates_before_repeat": gates,
        "label_blindness": {
            "geometry_sha256": fingerprint,
            "label_complement_geometry_sha256": complement,
            "unchanged": fingerprint == complement,
        },
        "metrics": metrics,
        "cases": {"hessian": hessian, "spatial": spatial, "equivariance": equivariance},
        "scope": (
            "Disjoint terminal analytic confirmation; not biological, segmentation, clinical, "
            "mechanical, acquisition-transfer or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["build_synthetic_physical_truth_v2_3"]
