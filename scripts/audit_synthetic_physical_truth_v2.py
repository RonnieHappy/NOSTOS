"""Independent arithmetic/provenance audit of synthetic physical truth v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-synthetic-physical-truth-v2/validation.json"
REPEAT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-repeat/validation.json"
OUTPUT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-audit/audit.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _close(a: float, b: float, tolerance: float = 1e-12) -> bool:
    return bool(abs(a - b) <= tolerance)


def _axial(a: float, b: float) -> float:
    difference = abs((a - b) % 180.0)
    return float(min(difference, 180.0 - difference))


def _relative(a: float, b: float) -> float:
    return float(abs(a - b) / b)


def main() -> None:
    payload: dict[str, Any] = json.loads(SOURCE.read_text(encoding="utf-8"))
    cases = payload["cases"]
    checks: dict[str, bool] = {}
    protocol = ROOT / payload["protocol"]
    checks["protocol_hash"] = _hash(protocol) == payload["protocol_sha256"]
    checks["repeat_byte_identical"] = SOURCE.read_bytes() == REPEAT.read_bytes()
    expected_counts = {
        "organization": 60,
        "hessian": 18,
        "thickness": 24,
        "network": 9,
        "spatial": 45,
        "orientation_perturbations": 8,
        "mask_sensitivity": 6,
        "abstention": 4,
    }
    checks["case_counts"] = all(len(cases[name]) == count for name, count in expected_counts.items())
    for name in ("organization", "hessian", "thickness", "network", "spatial"):
        identifiers = [item["case_id"] for item in cases[name]]
        checks[f"unique_{name}_ids"] = len(identifiers) == len(set(identifiers))

    organization_arithmetic = []
    fft_orientation: list[float] = []
    fft_scale: list[float] = []
    tensor_error: list[float] = []
    coherency: list[float] = []
    for item in cases["organization"]:
        truth = item["truth"]
        tensor_values = [
            _axial(float(value), float(truth["orientation_degrees"]))
            for value in item["tensor"]["orientation_degrees"]
        ]
        okay = _close(
            max(tensor_values),
            float(item["tensor"]["maximum_orientation_error_degrees"]),
        )
        tensor_error.append(max(tensor_values))
        coherency.extend(float(value) for value in item["tensor"]["coherency"])
        if not item["fft"]["abstained"]:
            angle_error = _axial(
                float(item["fft"]["orientation_degrees"]),
                float(truth["orientation_degrees"]),
            )
            scale_error = _relative(
                float(item["fft"]["wavelength_um"]),
                float(truth["wavelength_um"]),
            )
            okay &= _close(angle_error, float(item["fft_orientation_error_degrees"]))
            okay &= _close(scale_error, float(item["fft_wavelength_relative_error"]))
            fft_orientation.append(angle_error)
            fft_scale.append(scale_error)
        organization_arithmetic.append(okay)
    checks["organization_arithmetic"] = all(organization_arithmetic)

    hessian_arithmetic = []
    recalls = {}
    hessian_scale = []
    for label in ("blob", "tube", "sheet"):
        rows = [item for item in cases["hessian"] if item["truth_class"] == label]
        recalls[label] = float(np.mean([item["estimated_class"] == label for item in rows]))
    for item in cases["hessian"]:
        expected_correct = item["estimated_class"] == item["truth_class"]
        expected_error = _relative(
            float(item["winning_scale_um"]), float(item["truth_radius_um"])
        )
        hessian_arithmetic.append(
            bool(item["correct_class"]) == expected_correct
            and _close(expected_error, float(item["scale_relative_error"]))
        )
        hessian_scale.append(expected_error)
    checks["hessian_arithmetic"] = all(hessian_arithmetic)

    thickness_error = []
    checks["thickness_arithmetic"] = all(
        _close(
            _relative(float(item["estimated_p95_um"]), float(item["truth_diameter_um"])),
            float(item["relative_error"]),
        )
        for item in cases["thickness"]
    )
    thickness_error = [float(item["relative_error"]) for item in cases["thickness"]]
    anisotropic_thickness = [
        float(item["relative_error"]) for item in cases["thickness"] if item["anisotropic"]
    ]

    network_error = []
    network_arithmetic = []
    for item in cases["network"]:
        survival = [float(value) for value in item["surviving_fraction"]]
        monotone = all(left >= right for left, right in zip(survival, survival[1:]))
        observed = item["estimated_fragmentation_threshold_um"]
        expected_error = None if observed is None else _relative(
            float(observed), float(item["truth_fragmentation_threshold_um"])
        )
        network_arithmetic.append(
            monotone == bool(item["monotone_survival"])
            and (
                expected_error is None
                and item["fragmentation_relative_error"] is None
                or expected_error is not None
                and _close(expected_error, float(item["fragmentation_relative_error"]))
            )
        )
        if expected_error is not None:
            network_error.append(expected_error)
    checks["network_arithmetic"] = all(network_arithmetic)

    declared = np.asarray([item["truth_anisotropy_ratio"] for item in cases["spatial"]])
    recovered = np.asarray([item["recovered_anisotropy_ratio"] for item in cases["spatial"]])
    checks["spatial_arithmetic"] = all(
        _close(
            max(
                float(item["estimated_horizontal_range_um"]),
                float(item["estimated_vertical_range_um"]),
            )
            / min(
                float(item["estimated_horizontal_range_um"]),
                float(item["estimated_vertical_range_um"]),
            ),
            float(item["recovered_anisotropy_ratio"]),
        )
        and _close(
            _relative(
                float(item["recovered_anisotropy_ratio"]),
                float(item["truth_anisotropy_ratio"]),
            ),
            float(item["anisotropy_relative_error"]),
        )
        for item in cases["spatial"]
    )

    metrics = payload["metrics"]
    recomputed = {
        "fft_orientation_median": float(np.median(fft_orientation)),
        "fft_orientation_p95": float(np.percentile(fft_orientation, 95)),
        "fft_scale_median": float(np.median(fft_scale)),
        "fft_scale_p95": float(np.percentile(fft_scale, 95)),
        "tensor_median": float(np.median(tensor_error)),
        "tensor_p95": float(np.percentile(tensor_error, 95)),
        "tensor_coherency_p05": float(np.percentile(coherency, 5)),
        "hessian_balanced_accuracy": float(np.mean(list(recalls.values()))),
        "hessian_scale_median": float(np.median(hessian_scale)),
        "hessian_scale_p95": float(np.percentile(hessian_scale, 95)),
        "thickness_median": float(np.median(thickness_error)),
        "thickness_p95": float(np.percentile(thickness_error, 95)),
        "anisotropic_thickness_p95": float(np.percentile(anisotropic_thickness, 95)),
        "network_median": float(np.median(network_error)),
        "network_p95": float(np.percentile(network_error, 95)),
        "spatial_rho": float(spearmanr(declared, recovered).statistic),
    }
    stored = {
        "fft_orientation_median": metrics["spectral_orientation"]["median_error_degrees"],
        "fft_orientation_p95": metrics["spectral_orientation"]["p95_error_degrees"],
        "fft_scale_median": metrics["spectral_wavelength"]["median_relative_error"],
        "fft_scale_p95": metrics["spectral_wavelength"]["p95_relative_error"],
        "tensor_median": metrics["tensor_orientation"]["median_maximum_case_error_degrees"],
        "tensor_p95": metrics["tensor_orientation"]["p95_maximum_case_error_degrees"],
        "tensor_coherency_p05": metrics["tensor_orientation"]["p05_coherency"],
        "hessian_balanced_accuracy": metrics["hessian"]["balanced_accuracy"],
        "hessian_scale_median": metrics["hessian"]["median_scale_relative_error"],
        "hessian_scale_p95": metrics["hessian"]["p95_scale_relative_error"],
        "thickness_median": metrics["thickness"]["median_relative_error"],
        "thickness_p95": metrics["thickness"]["p95_relative_error"],
        "anisotropic_thickness_p95": metrics["thickness"]["anisotropic_p95_relative_error"],
        "network_median": metrics["network"]["median_fragmentation_relative_error"],
        "network_p95": metrics["network"]["p95_fragmentation_relative_error"],
        "spatial_rho": metrics["spatial"]["spearman_rho"],
    }
    checks["summary_metrics"] = all(
        _close(float(recomputed[name]), float(stored[name])) for name in recomputed
    )
    checks["scientific_status_is_failed"] = payload["status"] == "fail"
    receipt = {
        "audit": "nostos-synthetic-physical-truth-v2-independent-audit/1.0",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "repeat_sha256": _hash(REPEAT),
        "checks": checks,
        "recomputed_metrics": recomputed,
        "status": "pass" if all(checks.values()) else "fail",
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": receipt["status"], "checks": checks}, indent=2, sort_keys=True))
    if receipt["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
