"""Outcome-aware v2.2 development on the opened v2.1 confirmation failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from nostos.validation.phantoms import generate_phantom


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-1-confirmation/validation.json"
OUTPUT = ROOT / "outputs/nostos0-synthetic-repair-development-v2-2/development.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _gradient_ratio(image: np.ndarray) -> float:
    gy, gx = np.gradient(np.asarray(image, dtype=float))
    matrix = np.asarray(
        [
            [np.mean(gx * gx), np.mean(gx * gy)],
            [np.mean(gx * gy), np.mean(gy * gy)],
        ]
    )
    eigenvalues = np.maximum(np.linalg.eigvalsh(matrix), np.finfo(float).eps)
    return float(np.sqrt(eigenvalues[-1] / eigenvalues[0]))


def _spectral_moment_ratio(image: np.ndarray) -> float:
    data = np.asarray(image, dtype=float)
    data = data - np.mean(data)
    window = np.outer(np.hanning(data.shape[0]), np.hanning(data.shape[1]))
    power = np.abs(np.fft.fftshift(np.fft.fft2(data * window))) ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(data.shape[0]))
    fx = np.fft.fftshift(np.fft.fftfreq(data.shape[1]))
    xx, yy = np.meshgrid(fx, fy)
    radius = np.hypot(xx, yy)
    keep = (radius > 1.0 / max(data.shape)) & (radius < 0.35)
    weights = power[keep]
    coordinates = np.column_stack((xx[keep], yy[keep]))
    covariance = (coordinates * weights[:, None]).T @ coordinates / np.sum(weights)
    eigenvalues = np.maximum(np.linalg.eigvalsh(covariance), np.finfo(float).eps)
    return float(np.sqrt(eigenvalues[-1] / eigenvalues[0]))


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    hessian = source["cases"]["hessian"]
    hessian_candidates = []
    for boundary in (3.5, 4.0, 4.25, 4.5, 5.0, 6.0):
        accepted = [
            row
            for row in hessian
            if float(row["measurement"]["samples_per_winning_scale"]) >= boundary
        ]
        recalls = {}
        for label in ("blob", "tube", "sheet"):
            class_rows = [row for row in accepted if row["truth"]["class"] == label]
            recalls[label] = None if not class_rows else float(
                np.mean([not row["invalid"] for row in class_rows])
            )
        hessian_candidates.append(
            {
                "minimum_samples_per_winning_scale": boundary,
                "accepted": len(accepted),
                "coverage": len(accepted) / len(hessian),
                "invalid": sum(row["invalid"] for row in accepted),
                "risk": None if not accepted else float(np.mean([row["invalid"] for row in accepted])),
                "per_class_recall": recalls,
            }
        )

    spatial = source["cases"]["spatial"]
    moment_rows = []
    for row in spatial:
        correlation = float(row["truth"]["correlation_length_um"])
        anisotropy = float(row["truth"]["anisotropy_ratio"])
        seed_offset = int(str(row["case_id"]).rsplit("seed", 1)[1])
        seed = 810000 + int(correlation) * 100 + int(anisotropy * 10) + seed_offset
        phantom = generate_phantom(
            "heterogeneity",
            shape=(192, 192),
            spacing_um=(1.0, 1.0),
            seed=seed,
            correlation_length_um=correlation,
            anisotropy_ratio=anisotropy,
        )
        moment_rows.append(
            {
                "case_id": row["case_id"],
                "truth": anisotropy,
                "gradient_ratio": _gradient_ratio(phantom.image),
                "spectral_moment_ratio": _spectral_moment_ratio(phantom.image),
            }
        )
    moment_endpoints = {}
    for endpoint in ("gradient_ratio", "spectral_moment_ratio"):
        anisotropic_moments = [item for item in moment_rows if item["truth"] > 1.0]
        isotropic_moments = [item for item in moment_rows if item["truth"] == 1.0]
        truth = [item["truth"] for item in anisotropic_moments]
        estimate = [item[endpoint] for item in anisotropic_moments]
        errors = [abs(a - b) / b for a, b in zip(estimate, truth, strict=True)]
        moment_endpoints[endpoint] = {
            "spearman_rho": float(spearmanr(truth, estimate).statistic),
            "median_relative_error": float(np.median(errors)),
            "p95_relative_error": float(np.percentile(errors, 95)),
            "isotropic_median": float(np.median([item[endpoint] for item in isotropic_moments])),
            "isotropic_p95": float(np.percentile([item[endpoint] for item in isotropic_moments], 95)),
        }
    anisotropic_all = [
        row for row in spatial if row["truth"]["anisotropy_ratio"] > 1.0
    ]
    angular_anisotropy_endpoint = {
        "cases": len(anisotropic_all),
        "spearman_rho": float(
            spearmanr(
                [row["truth"]["anisotropy_ratio"] for row in anisotropic_all],
                [row["measurement"]["median_angular_anisotropy"] for row in anisotropic_all],
            ).statistic
        ),
        "interpretation": "dimensionless response amplitude, not a calibrated ratio estimate",
    }
    spatial_candidates = []
    for anisotropy_boundary in (0.20, 0.25, 0.30, 0.35):
        for minimum_fov_ranges in (0.0, 6.0, 8.0, 10.0):
            evaluated = []
            for row in spatial:
                measurement = row["measurement"]
                major = measurement["major_e_fold_range_um"]
                minor = measurement["minor_e_fold_range_um"]
                range_ready = major is not None and minor is not None
                fov_ranges = None if not range_ready else 192.0 / max(float(major), float(minor))
                supported = bool(
                    range_ready
                    and float(measurement["median_angular_anisotropy"]) >= anisotropy_boundary
                    and float(fov_ranges) >= minimum_fov_ranges
                )
                evaluated.append((row, supported, fov_ranges))
            anisotropic = [item for item in evaluated if item[0]["truth"]["anisotropy_ratio"] > 1.0]
            isotropic = [item for item in evaluated if item[0]["truth"]["anisotropy_ratio"] == 1.0]
            accepted = [item[0] for item in anisotropic if item[1]]
            truth = [float(row["truth"]["anisotropy_ratio"]) for row in accepted]
            estimate = [float(row["measurement"]["anisotropy_ratio"]) for row in accepted]
            errors = [abs(a - b) / b for a, b in zip(estimate, truth, strict=True)]
            rho = None if len(set(truth)) < 2 else float(spearmanr(truth, estimate).statistic)
            spatial_candidates.append(
                {
                    "minimum_median_angular_anisotropy": anisotropy_boundary,
                    "minimum_fov_per_major_range": minimum_fov_ranges,
                    "anisotropic_accepted": len(accepted),
                    "anisotropic_coverage": len(accepted) / len(anisotropic),
                    "isotropic_abstention": float(np.mean([not item[1] for item in isotropic])),
                    "spearman_rho": rho,
                    "median_relative_error": None if not errors else float(np.median(errors)),
                    "p95_relative_error": None if not errors else float(np.percentile(errors, 95)),
                }
            )
    deployable = [
        item
        for item in spatial_candidates
        if item["anisotropic_coverage"] >= 0.40
        and item["isotropic_abstention"] >= 0.80
        and item["spearman_rho"] is not None
        and item["spearman_rho"] >= 0.75
        and item["median_relative_error"] <= 0.35
    ]
    selected_spatial = None
    if deployable:
        selected_spatial = max(
            deployable,
            key=lambda item: (
                item["anisotropic_coverage"],
                item["spearman_rho"],
                -item["minimum_median_angular_anisotropy"],
                -item["minimum_fov_per_major_range"],
            ),
        )
    payload = {
        "protocol_version": "nostos-synthetic-repair-development/2.2",
        "evidence_status": "opened_failed_v2_1_development_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "hessian_candidates": hessian_candidates,
        "spatial_candidates": spatial_candidates,
        "selected_spatial_by_frozen_rule": selected_spatial,
        "angular_anisotropy_endpoint": angular_anisotropy_endpoint,
        "moment_endpoints": moment_endpoints,
        "moment_cases": moment_rows,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "hessian_candidates": hessian_candidates,
                "selected_spatial_by_frozen_rule": selected_spatial,
                "angular_anisotropy_endpoint": angular_anisotropy_endpoint,
                "moment_endpoints": moment_endpoints,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
