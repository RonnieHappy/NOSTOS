"""Outcome-aware development on the opened physical-truth v2 failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from nostos.features.intrinsic_variogram import intrinsic_variogram_2d
from nostos.validation.phantoms import generate_phantom


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-synthetic-physical-truth-v2/validation.json"
OUTPUT = ROOT / "outputs/nostos0-synthetic-repair-development-v2-1/development.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _hessian_candidates(rows: list[dict]) -> list[dict]:
    output = []
    for boundary in (2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        accepted = []
        for row in rows:
            samples = float(row["winning_scale_um"]) / max(row["spacing_um"])
            if samples >= boundary:
                accepted.append(row)
        output.append(
            {
                "minimum_samples_per_winning_scale": boundary,
                "accepted": len(accepted),
                "coverage": len(accepted) / len(rows),
                "invalid": sum(not bool(row["correct_class"]) for row in accepted),
                "risk": None
                if not accepted
                else float(np.mean([not bool(row["correct_class"]) for row in accepted])),
            }
        )
    return output


def _tensor_candidates(rows: list[dict]) -> list[dict]:
    output = []
    for boundary in (4.0, 5.0, 5.5, 6.0, 7.0, 8.0):
        accepted = [
            row
            for row in rows
            if float(row["truth"]["pixels_per_wavelength"]) >= boundary
        ]
        errors = [float(row["tensor"]["maximum_orientation_error_degrees"]) for row in accepted]
        output.append(
            {
                "minimum_samples_per_characteristic_wavelength": boundary,
                "accepted": len(accepted),
                "coverage": len(accepted) / len(rows),
                "p95_error_degrees": None if not errors else float(np.percentile(errors, 95)),
                "errors_above_2_5_degrees": sum(value > 2.5 for value in errors),
            }
        )
    return output


def _spatial_candidates(rows: list[dict]) -> list[dict]:
    candidates = {
        "coarse": (2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, 80.0),
        "dense": (2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0, 32.0, 40.0, 48.0, 64.0, 80.0),
    }
    output = []
    for name, separations in candidates.items():
        case_results = []
        for row in rows:
            correlation = float(row["truth_correlation_length_um"])
            anisotropy = float(row["truth_anisotropy_ratio"])
            seed_offset = int(str(row["case_id"]).rsplit("seed", 1)[1])
            seed = 420000 + int(correlation) * 100 + int(anisotropy) * 10 + seed_offset
            phantom = generate_phantom(
                "heterogeneity",
                shape=(192, 192),
                spacing_um=(1.0, 1.0),
                seed=seed,
                correlation_length_um=correlation,
                anisotropy_ratio=anisotropy,
            )
            response = intrinsic_variogram_2d(
                phantom.image,
                spacing_um=(1.0, 1.0),
                separations_um=separations,
            )
            recovered = None
            if response.range_identifiable:
                recovered = float(response.major_e_fold_range_um / response.minor_e_fold_range_um)
            case_results.append(
                {
                    "case_id": row["case_id"],
                    "truth": anisotropy,
                    "range_identifiable": response.range_identifiable,
                    "axis_identifiable": response.axis_consensus_degrees is not None,
                    "axis_consensus_resultant": response.axis_consensus_resultant,
                    "median_angular_anisotropy": float(
                        np.median(response.angular_anisotropy_curve)
                    ),
                    "maximum_angular_anisotropy": float(
                        np.max(response.angular_anisotropy_curve)
                    ),
                    "recovered_ratio": recovered,
                    "reasons": list(response.abstention_reasons),
                }
            )
        anisotropic = [item for item in case_results if item["truth"] > 1.0]
        accepted = [item for item in anisotropic if item["recovered_ratio"] is not None]
        errors = [abs(item["recovered_ratio"] - item["truth"]) / item["truth"] for item in accepted]
        rho = None
        if accepted:
            rho = float(
                spearmanr(
                    [item["truth"] for item in accepted],
                    [item["recovered_ratio"] for item in accepted],
                ).statistic
            )
        isotropic = [item for item in case_results if item["truth"] == 1.0]
        identifiability_candidates = []
        for threshold in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40):
            isotropic_abstention = np.mean(
                [item["median_angular_anisotropy"] < threshold for item in isotropic]
            )
            anisotropic_retention = np.mean(
                [item["median_angular_anisotropy"] >= threshold for item in anisotropic]
            )
            identifiability_candidates.append(
                {
                    "minimum_median_angular_anisotropy": threshold,
                    "isotropic_abstention_fraction": float(isotropic_abstention),
                    "anisotropic_retention_fraction": float(anisotropic_retention),
                }
            )
        output.append(
            {
                "candidate": name,
                "separations_um": list(separations),
                "anisotropic_coverage": len(accepted) / len(anisotropic),
                "anisotropic_spearman_rho": rho,
                "median_relative_ratio_error": None if not errors else float(np.median(errors)),
                "p95_relative_ratio_error": None if not errors else float(np.percentile(errors, 95)),
                "isotropic_axis_abstention_fraction": float(
                    np.mean([not item["axis_identifiable"] for item in isotropic])
                ),
                "identifiability_candidates": identifiability_candidates,
                "cases": case_results,
            }
        )
    return output


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    payload = {
        "protocol_version": "nostos-synthetic-repair-development/2.1",
        "evidence_status": "opened_failed_v2_development_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "hessian_candidates": _hessian_candidates(source["cases"]["hessian"]),
        "tensor_candidates": _tensor_candidates(source["cases"]["organization"]),
        "spatial_candidates": _spatial_candidates(source["cases"]["spatial"]),
        "network_truth_correction": {
            "old_target": "first discrete threshold above half-width",
            "correct_continuous_target": "programmed half-width",
            "reason": "a zero-width remnant is not an open spanning component at the half-width",
            "changes_estimator": False,
        },
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
                "hessian_candidates": payload["hessian_candidates"],
                "tensor_candidates": payload["tensor_candidates"],
                "spatial_candidates": [
                    {key: value for key, value in item.items() if key != "cases"}
                    for item in payload["spatial_candidates"]
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
