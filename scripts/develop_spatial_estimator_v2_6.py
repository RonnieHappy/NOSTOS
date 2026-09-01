"""Develop a field-support gate and boundary-robust axis on opened failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.phantoms import Phantom, generate_phantom
from nostos.validation.perturbations import Perturbation, apply_perturbation


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/nostos0-spatial-estimator-development-v2-6/development.json"
SOURCES = (
    {
        "name": "v2.4",
        "path": "outputs/nostos0-synthetic-physical-truth-v2-4-confirmation/validation.json",
        "correlations": (16.0, 24.0, 32.0),
        "ratios": (1.0, 1.6, 2.1, 2.6, 3.1),
        "seed_base": 1640000,
        "rotation_degrees": 37.0,
    },
    {
        "name": "v2.5",
        "path": "outputs/nostos0-synthetic-physical-truth-v2-5-confirmation/validation.json",
        "correlations": (18.0, 26.0, 34.0),
        "ratios": (1.0, 1.7, 2.2, 2.7, 3.2),
        "seed_base": 2050000,
        "rotation_degrees": 43.0,
    },
)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _phantom(source: dict, correlation: float, ratio: float, offset: int) -> Phantom:
    seed = (
        int(source["seed_base"])
        + int(correlation) * 1000
        + int(ratio * 100)
        + offset
    )
    return generate_phantom(
        "heterogeneity",
        shape=(192, 192),
        spacing_um=(1.0, 1.0),
        seed=seed,
        correlation_length_um=correlation,
        anisotropy_ratio=ratio,
    )


def _characteristic_spans(image: np.ndarray) -> float:
    response = extract_spatial_fft(image, pixel_size_um=1.0)
    wavelength_um = 1000.0 / response.characteristic_frequency_cycles_per_mm
    return min(image.shape) / wavelength_um


def _gradient_axis(image: np.ndarray, *, tapered: bool) -> tuple[float, float]:
    data = np.asarray(image, dtype=float)
    gy, gx = np.gradient(data)
    weights = np.ones_like(data)
    if tapered:
        weights = np.outer(np.hanning(data.shape[0]), np.hanning(data.shape[1]))
    weights /= float(np.sum(weights))
    covariance = np.asarray(
        [
            [np.sum(weights * gx * gx), np.sum(weights * gx * gy)],
            [np.sum(weights * gx * gy), np.sum(weights * gy * gy)],
        ]
    )
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    ratio = float(np.sqrt(eigenvalues[-1] / eigenvalues[0]))
    vector = eigenvectors[:, 0]
    axis = float(np.mod(np.degrees(np.arctan2(vector[1], vector[0])), 180.0))
    return ratio, axis


def _spatial_rows(source: dict, receipt: dict) -> list[dict]:
    stored = {row["case_id"]: row for row in receipt["cases"]["spatial"]}
    rows = []
    prefix = str(source["name"]).replace(".", "")
    for correlation in source["correlations"]:
        for ratio in source["ratios"]:
            for offset in range(10):
                case_id = (
                    f"spatial-{prefix}-c{correlation:g}-a{ratio:g}-seed{offset}"
                )
                row = stored[case_id]
                phantom = _phantom(source, correlation, ratio, offset)
                rows.append(
                    {
                        "case_id": case_id,
                        "truth_ratio": ratio,
                        "estimated_ratio": row["measurement"]["ratio"],
                        "relative_error": row["relative_ratio_error"],
                        "base_supported": row["supported"],
                        "characteristic_spans": _characteristic_spans(phantom.image),
                    }
                )
    return rows


def _support_metrics(rows: list[dict], threshold: float) -> dict:
    accepted = [
        row
        for row in rows
        if row["base_supported"] and row["characteristic_spans"] >= threshold
    ]
    anisotropic = [row for row in accepted if row["truth_ratio"] > 1.0]
    isotropic = [row for row in accepted if row["truth_ratio"] == 1.0]
    errors = [row["relative_error"] for row in anisotropic]
    return {
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "anisotropic_coverage": len(anisotropic)
        / sum(row["truth_ratio"] > 1.0 for row in rows),
        "accepted_isotropic": len(isotropic),
        "median_relative_error": float(np.median(errors)),
        "p95_relative_error": float(np.percentile(errors, 95)),
        "invalid_risk": float(np.mean(np.asarray(errors) > 0.25)),
        "isotropic_p95_ratio": None
        if not isotropic
        else float(np.percentile([row["estimated_ratio"] for row in isotropic], 95)),
    }


def _axis_rows(source: dict, receipt: dict, support_threshold: float) -> list[dict]:
    stored = {row["case_id"]: row for row in receipt["cases"]["equivariance"]}
    rows = []
    prefix = str(source["name"]).replace(".", "")
    for correlation in source["correlations"]:
        for ratio in source["ratios"]:
            if ratio == 1.0:
                continue
            for offset in (0, 1):
                case_id = (
                    f"equivariance-{prefix}-c{correlation:g}-a{ratio:g}-seed{offset}"
                )
                stored_row = stored[case_id]
                phantom = _phantom(source, correlation, ratio, offset)
                rotated = apply_perturbation(
                    phantom,
                    Perturbation("rotation", float(source["rotation_degrees"])),
                )
                supported = bool(
                    stored_row["supported"]
                    and _characteristic_spans(phantom.image) >= support_threshold
                    and _characteristic_spans(rotated.image) >= support_threshold
                )
                record = {
                    "case_id": case_id,
                    "supported": supported,
                    "truth_ratio": ratio,
                    "uniform": {},
                    "hann_tapered": {},
                }
                for name, tapered in (("uniform", False), ("hann_tapered", True)):
                    reference_ratio, reference_axis = _gradient_axis(
                        phantom.image, tapered=tapered
                    )
                    rotated_ratio, rotated_axis = _gradient_axis(
                        rotated.image, tapered=tapered
                    )
                    axis_available = bool(
                        min(reference_ratio, rotated_ratio) >= 1.65
                    )
                    turn_error = abs(
                        axial_angular_error_degrees(reference_axis, rotated_axis)
                        - float(source["rotation_degrees"])
                    )
                    record[name] = {
                        "reference_ratio": reference_ratio,
                        "rotated_ratio": rotated_ratio,
                        "axis_available": axis_available,
                        "turn_error_degrees": turn_error,
                    }
                rows.append(record)
    return rows


def main() -> None:
    opened = []
    spatial_by_source = {}
    for source in SOURCES:
        path = ROOT / source["path"]
        receipt = json.loads(path.read_text(encoding="utf-8"))
        opened.append(
            {
                "name": source["name"],
                "path": source["path"],
                "sha256": _hash(path),
            }
        )
        spatial_by_source[source["name"]] = _spatial_rows(source, receipt)

    support_candidates = []
    for threshold in (2.00, 2.25, 2.50, 2.75, 3.00):
        metrics = {
            name: _support_metrics(rows, threshold)
            for name, rows in spatial_by_source.items()
        }
        support_candidates.append(
            {
                "minimum_characteristic_spans": threshold,
                "by_opened_receipt": metrics,
                "deployable": all(
                    value["p95_relative_error"] <= 0.25
                    and value["invalid_risk"] <= 0.05
                    and (
                        value["isotropic_p95_ratio"] is None
                        or value["isotropic_p95_ratio"] <= 1.50
                    )
                    for value in metrics.values()
                ),
            }
        )
    deployable_support = [row for row in support_candidates if row["deployable"]]
    selected_support = min(
        deployable_support,
        key=lambda row: row["minimum_characteristic_spans"],
        default=None,
    )
    if selected_support is None:
        raise RuntimeError("No deployable field-support candidate")

    axis_rows = []
    for source in SOURCES:
        receipt = json.loads((ROOT / source["path"]).read_text(encoding="utf-8"))
        axis_rows.extend(
            _axis_rows(
                source,
                receipt,
                float(selected_support["minimum_characteristic_spans"]),
            )
        )
    axis_candidates = []
    supported_axis_rows = [row for row in axis_rows if row["supported"]]
    for method in ("uniform", "hann_tapered"):
        available = [
            row for row in supported_axis_rows if row[method]["axis_available"]
        ]
        axis_candidates.append(
            {
                "method": method,
                "supported_cases": len(supported_axis_rows),
                "axis_cases": len(available),
                "axis_coverage": len(available) / len(supported_axis_rows),
                "median_turn_error_degrees": float(
                    np.median([row[method]["turn_error_degrees"] for row in available])
                ),
                "p95_turn_error_degrees": float(
                    np.percentile(
                        [row[method]["turn_error_degrees"] for row in available], 95
                    )
                ),
            }
        )
    deployable_axis = [
        row
        for row in axis_candidates
        if row["axis_coverage"] >= 0.60 and row["p95_turn_error_degrees"] <= 3.0
    ]
    selected_axis = max(
        deployable_axis,
        key=lambda row: (row["axis_coverage"], -row["p95_turn_error_degrees"]),
        default=None,
    )
    payload = {
        "protocol_version": "nostos-spatial-estimator-development/2.6",
        "evidence_status": "opened_failed_v2_4_and_v2_5_development_only",
        "opened_receipts": opened,
        "support_candidates": support_candidates,
        "selected_support_by_frozen_rule": selected_support,
        "axis_candidates": axis_candidates,
        "selected_axis_by_frozen_rule": selected_axis,
        "selection_rules": {
            "support": (
                "Choose the lowest characteristic-span threshold for which each "
                "opened receipt separately has p95 error <=0.25, invalid risk "
                "<=0.05 and isotropic p95 ratio <=1.50 when estimable."
            ),
            "axis": (
                "Among methods with axis coverage >=0.60 and p95 turn error <=3 "
                "degrees, maximize coverage then minimize p95 error."
            ),
        },
        "axis_cases": axis_rows,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
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
                "selected_support": selected_support,
                "axis_candidates": axis_candidates,
                "selected_axis": selected_axis,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
