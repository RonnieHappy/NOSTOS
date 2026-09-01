"""Frozen calibrated 3D directional-response transfer on human bone nanoCT."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.transform import resize


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _normalise(volume: np.ndarray) -> np.ndarray:
    values = np.asarray(volume, dtype=np.float32)
    lo, hi = np.percentile(values, (1, 99))
    return np.clip((values - lo) / max(float(hi - lo), np.finfo(np.float32).eps), 0, 1)


def measure_direction(volume: np.ndarray, spacing: tuple[float, float, float]) -> dict:
    data = _normalise(volume)
    gradients = np.gradient(data, *spacing)
    tensor = np.asarray([[float(np.mean(a * b)) for b in gradients] for a in gradients])
    eigenvalues, eigenvectors = np.linalg.eigh(tensor)
    eigenvalues = np.maximum(eigenvalues, 0)
    spectrum = eigenvalues / max(float(eigenvalues.sum()), np.finfo(float).eps)
    axis = eigenvectors[:, 0]
    axis = axis / max(float(np.linalg.norm(axis)), np.finfo(float).eps)
    return {
        "normalised_eigenvalues": spectrum.tolist(),
        "principal_structural_axis_zyx": axis.tolist(),
        "anisotropy": float((eigenvalues[-1] - eigenvalues[0]) / max(float(eigenvalues.sum()), np.finfo(float).eps)),
        "dynamic_range": float(np.percentile(data, 99) - np.percentile(data, 1)),
        "saturation_fraction": float(np.mean((data <= 0) | (data >= 1))),
    }


def axial_error_3d(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    cosine = abs(float(np.dot(x, y))) / max(float(np.linalg.norm(x) * np.linalg.norm(y)), np.finfo(float).eps)
    return float(np.degrees(np.arccos(np.clip(cosine, -1, 1))))


def _relative(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), np.finfo(float).eps)


def _case(volume: np.ndarray, name: str, seed: int) -> np.ndarray:
    if name == "identity": return volume
    if name == "gamma_0.5": return np.sqrt(np.clip(volume, 0, 1))
    if name == "blur_1.0": return gaussian_filter(volume, 1.0)
    if name == "blur_3.0": return gaussian_filter(volume, 3.0)
    if name == "resample_0.5":
        small = resize(volume, tuple(max(16, size // 2) for size in volume.shape), preserve_range=True, anti_aliasing=True)
        return resize(small, volume.shape, preserve_range=True, anti_aliasing=True)
    if name == "noise_0.05":
        return np.clip(volume + np.random.default_rng(seed).normal(0, 0.05, volume.shape), 0, 1)
    raise ValueError(name)


def internal_diagnostics(volume: np.ndarray, spacing: tuple[float, float, float], measurement: dict) -> dict:
    probes = [np.power(np.clip(volume, 0, 1), 1.1), gaussian_filter(volume, 0.5)]
    axis_drifts, anisotropy_drifts = [], []
    for probe in probes:
        result = measure_direction(probe, spacing)
        axis_drifts.append(axial_error_3d(measurement["principal_structural_axis_zyx"], result["principal_structural_axis_zyx"]))
        anisotropy_drifts.append(_relative(result["anisotropy"], measurement["anisotropy"]))
    permutation = (2, 1, 0)
    permuted = measure_direction(np.transpose(volume, permutation), tuple(spacing[index] for index in permutation))
    expected_axis = np.asarray(measurement["principal_structural_axis_zyx"])[list(permutation)]
    axis_drifts.append(axial_error_3d(expected_axis, permuted["principal_structural_axis_zyx"]))
    anisotropy_drifts.append(_relative(permuted["anisotropy"], measurement["anisotropy"]))
    return {"maximum_axis_drift_degrees": float(max(axis_drifts)),
            "maximum_anisotropy_relative_drift": float(max(anisotropy_drifts))}


def _accept(measurement: dict, diagnostics: dict, config: dict) -> tuple[dict, dict]:
    signal = measurement["dynamic_range"] >= config["minimum_dynamic_range_fraction"]
    saturation = measurement["saturation_fraction"] <= config["maximum_saturation_fraction"]
    anisotropy = measurement["anisotropy"] >= config["minimum_anisotropy"]
    axis_stable = diagnostics["maximum_axis_drift_degrees"] <= config["maximum_internal_axis_drift_degrees"]
    response_stable = diagnostics["maximum_anisotropy_relative_drift"] <= config["maximum_internal_anisotropy_relative_drift"]
    accepts = {"always_emit": True, "endpoint_qc": signal and saturation,
               "partial_no_axis": signal and saturation and anisotropy and response_stable,
               "partial_no_response": signal and saturation and anisotropy and axis_stable,
               "full_contract": signal and saturation and anisotropy and axis_stable and response_stable}
    scores = {"endpoint_qc": max(0.0, measurement["saturation_fraction"] - config["maximum_saturation_fraction"]),
              "full_contract": max(diagnostics["maximum_axis_drift_degrees"] / config["maximum_internal_axis_drift_degrees"],
                                   diagnostics["maximum_anisotropy_relative_drift"] / config["maximum_internal_anisotropy_relative_drift"],
                                   config["minimum_anisotropy"] / max(measurement["anisotropy"], np.finfo(float).eps))}
    return accepts, scores


def _cluster_interval(rows: list[dict], condition: str) -> list[float]:
    names = sorted({row["volume"] for row in rows})
    counts = {}
    for name in names:
        accepted = [row for row in rows if row["volume"] == name and row["accept"][condition]]
        counts[name] = (sum(row["invalid"] for row in accepted), len(accepted))
    risks = []
    for sample in itertools.product(names, repeat=len(names)):
        invalid, accepted = sum(counts[x][0] for x in sample), sum(counts[x][1] for x in sample)
        if accepted: risks.append(invalid / accepted)
    return [float(x) for x in np.quantile(risks, (0.025, 0.975))] if risks else [0.0, 1.0]


def run(data_root: Path, config_path: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    shape = tuple(config["volume_shape_zyx"]); crop_shape = tuple(config["crop_shape_zyx"])
    spacing = tuple(config["spacing_um_zyx"]); centers = config["crop_centers_per_axis"]
    rows = []
    for path in sorted(data_root.glob("*.raw")):
        volume = np.memmap(path, dtype=np.dtype(config["dtype"]), mode="r", shape=shape)
        for center in itertools.product(centers, repeat=3):
            slices = tuple(slice(c - size // 2, c - size // 2 + size) for c, size in zip(center, crop_shape))
            clean = _normalise(volume[slices])
            reference = measure_direction(clean, spacing)
            crop_id = "-".join(map(str, center)); seed = int(hashlib.sha256(f"{path.stem}:{crop_id}".encode()).hexdigest()[:8], 16)
            for case_name in config["case_perturbations"]:
                case = _case(clean, case_name, seed)
                measurement = measure_direction(case, spacing); diagnostics = internal_diagnostics(case, spacing, measurement)
                axis_error = axial_error_3d(reference["principal_structural_axis_zyx"], measurement["principal_structural_axis_zyx"])
                anisotropy_error = _relative(measurement["anisotropy"], reference["anisotropy"])
                invalid = axis_error > config["withheld_maximum_axis_drift_degrees"] or anisotropy_error > config["withheld_maximum_anisotropy_relative_error"]
                accepts, scores = _accept(measurement, diagnostics, config)
                rows.append({"case_id": f"{path.stem}:{crop_id}:{case_name}", "volume": path.stem,
                             "crop_center_zyx": center, "perturbation": case_name, "measurement": measurement,
                             "internal_diagnostics": diagnostics, "withheld_axis_error_degrees": axis_error,
                             "withheld_anisotropy_relative_error": anisotropy_error, "invalid": bool(invalid),
                             "accept": accepts, "scores": scores})
    conditions = list(rows[0]["accept"]); summary = {}
    for condition in conditions:
        accepted = [row for row in rows if row["accept"][condition]]
        summary[condition] = {"cases": len(rows), "accepted": len(accepted), "coverage": len(accepted) / len(rows),
                              "silent_invalid": sum(row["invalid"] for row in accepted),
                              "silent_invalid_risk": float(np.mean([row["invalid"] for row in accepted])) if accepted else None,
                              "volume_cluster_risk_95": _cluster_interval(rows, condition)}
    payload = {"protocol_version": config["protocol_version"], "config_sha256": _sha256(config_path),
               "dataset_doi": config["dataset_doi"], "deposited_volumes": len({row["volume"] for row in rows}),
               "spacing_provenance": "50 nm source acquisition, public repository binned by factor two; inferred public spacing 0.10 um isotropic",
               "technical_cases": len(rows), "summary": summary, "status": "complete",
               "claim_boundary": config["claim_boundary"]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "case_rows.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "human_nanoct_transfer.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload

