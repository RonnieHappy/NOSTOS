"""Frozen 3D lacunar-canalicular network contract-ablation benchmark."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import convolve, label
from skimage.morphology import skeletonize


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _central_crop(volume: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    starts = tuple(max(0, (current - target) // 2) for current, target in zip(volume.shape, shape))
    slices = tuple(slice(start, min(current, start + target))
                   for start, current, target in zip(starts, volume.shape, shape))
    return np.asarray(volume[slices])


def _edge_length(skeleton: np.ndarray, spacing: tuple[float, float, float]) -> float:
    total = 0.0
    zmax, ymax, xmax = skeleton.shape
    offsets = [(dz, dy, dx) for dz in (-1, 0, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
               if (dz, dy, dx) != (0, 0, 0) and (dz, dy, dx) > (0, 0, 0)]
    for dz, dy, dx in offsets:
        a = skeleton[max(0, dz):min(zmax, zmax + dz),
                     max(0, dy):min(ymax, ymax + dy),
                     max(0, dx):min(xmax, xmax + dx)]
        b = skeleton[max(0, -dz):min(zmax, zmax - dz),
                     max(0, -dy):min(ymax, ymax - dy),
                     max(0, -dx):min(xmax, xmax - dx)]
        total += float(np.count_nonzero(a & b)) * float(np.linalg.norm(np.asarray((dz, dy, dx)) * spacing))
    return total


def measure_network(segmentation: np.ndarray, spacing: tuple[float, float, float]) -> dict:
    canaliculi = np.asarray(segmentation == 1)
    lacunae = np.asarray(segmentation == 2)
    skeleton = skeletonize(canaliculi)
    structure = np.ones((3, 3, 3), dtype=np.uint8)
    components, count = label(skeleton, structure=structure)
    sizes = np.bincount(components.ravel())[1:] if count else np.asarray([], dtype=int)
    degree = convolve(skeleton.astype(np.uint8), structure, mode="constant") - skeleton
    volume_um3 = float(np.prod(segmentation.shape) * np.prod(spacing))
    _, lacuna_count = label(lacunae, structure=structure)
    foreground = int(canaliculi.sum())
    boundary = np.zeros(canaliculi.shape, dtype=bool)
    boundary[[0, -1], :, :] = True; boundary[:, [0, -1], :] = True; boundary[:, :, [0, -1]] = True
    return {
        "canalicular_volume_fraction": foreground / segmentation.size,
        "skeleton_length_density_per_um2": _edge_length(skeleton, spacing) / volume_um3,
        "largest_component_fraction": float(sizes.max() / max(1, skeleton.sum())) if sizes.size else 0.0,
        "branch_density_per_1000_um3": float(np.count_nonzero(skeleton & (degree >= 3))) / volume_um3 * 1000.0,
        "lacuna_density_per_1000_um3": float(lacuna_count) / volume_um3 * 1000.0,
        "boundary_contact_fraction": float(np.count_nonzero(canaliculi & boundary)) / max(1, foreground),
    }


ENDPOINTS = ("skeleton_length_density_per_um2", "largest_component_fraction",
             "branch_density_per_1000_um3", "lacuna_density_per_1000_um3")


def _relative_error(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), np.finfo(float).eps)


def _perturb(segmentation: np.ndarray, count: int, block: tuple[int, int, int], seed: int) -> np.ndarray:
    result = np.asarray(segmentation).copy()
    if count == 0:
        return result
    rng = np.random.default_rng(seed + count)
    for _ in range(count):
        starts = [int(rng.integers(0, max(1, size - width + 1))) for size, width in zip(result.shape, block)]
        slices = tuple(slice(start, min(size, start + width)) for start, size, width in zip(starts, result.shape, block))
        view = result[slices]
        view[view == 1] = 0
    return result


def _nested(segmentation: np.ndarray, fraction: float) -> np.ndarray:
    shape = tuple(max(8, round(size * fraction)) for size in segmentation.shape)
    return _central_crop(segmentation, shape)


def _conditions(metrics: dict, nested_drift: float, config: dict) -> tuple[dict, dict]:
    low, high = config["endpoint_qc_occupancy_range"]
    occupancy_ok = low <= metrics["canalicular_volume_fraction"] <= high
    topology_ok = metrics["largest_component_fraction"] >= config["topology_qc_minimum_largest_component_fraction"]
    boundary_ok = metrics["boundary_contact_fraction"] <= config["full_maximum_boundary_contact_fraction"]
    nested_ok = nested_drift <= config["full_maximum_nested_relative_drift"]
    accepts = {
        "always_emit": True,
        "endpoint_qc": occupancy_ok,
        "topology_qc": occupancy_ok and topology_ok,
        "partial_no_boundary": occupancy_ok and topology_ok and nested_ok,
        "partial_no_nested": occupancy_ok and topology_ok and boundary_ok,
        "full_contract": occupancy_ok and topology_ok and boundary_ok and nested_ok,
    }
    scores = {
        "endpoint_qc": 0.0 if occupancy_ok else 1.0,
        "topology_qc": max(0.0, config["topology_qc_minimum_largest_component_fraction"] - metrics["largest_component_fraction"]),
        "full_contract": max(
            nested_drift / config["full_maximum_nested_relative_drift"],
            metrics["boundary_contact_fraction"] / config["full_maximum_boundary_contact_fraction"],
            max(0.0, config["topology_qc_minimum_largest_component_fraction"] - metrics["largest_component_fraction"]),
        ),
    }
    return accepts, scores


def _risk_coverage_auc(rows: list[dict], score_name: str) -> float:
    ordered = sorted(rows, key=lambda row: (row["scores"][score_name], row["case_id"]))
    risks = np.cumsum([row["invalid"] for row in ordered]) / np.arange(1, len(ordered) + 1)
    return float(np.trapezoid(risks, dx=1 / len(ordered)))


def run(data_root: Path, config_path: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    spacing = tuple(float(value) for value in config["spacing_um_zyx"])
    shape = tuple(int(value) for value in config["crop_shape_zyx"])
    block = tuple(int(value) for value in config["perturbation_block_shape_zyx"])
    rows = []
    seg_paths = sorted(data_root.glob("*_seg.tif"))
    for path in seg_paths:
        sample = path.stem.removesuffix("_seg")
        rat = sample.split("-", 1)[0]
        original = _central_crop(tifffile.memmap(path), shape)
        reference = measure_network(original, spacing)
        seed = int(hashlib.sha256(sample.encode()).hexdigest()[:8], 16)
        for blocks in config["perturbation_deleted_block_counts"]:
            perturbed = _perturb(original, int(blocks), block, seed)
            metrics = measure_network(perturbed, spacing)
            nested_metrics = measure_network(_nested(perturbed, float(config["nested_fraction"])), spacing)
            nested_drift = max(_relative_error(nested_metrics[key], metrics[key]) for key in ENDPOINTS)
            endpoint_errors = {key: _relative_error(metrics[key], reference[key]) for key in ENDPOINTS}
            invalid = max(endpoint_errors.values()) > config["maximum_endpoint_relative_error"]
            accepts, scores = _conditions(metrics, nested_drift, config)
            rows.append({"case_id": f"{sample}:blocks={blocks}", "sample": sample, "rat": rat,
                         "location": sample.split("-", 1)[1], "deleted_blocks": int(blocks),
                         "metrics": metrics, "nested_max_relative_drift": nested_drift,
                         "endpoint_relative_errors": endpoint_errors, "invalid": bool(invalid),
                         "accept": accepts, "scores": scores})
    conditions = list(rows[0]["accept"])
    summary = {}
    for condition in conditions:
        accepted = [row for row in rows if row["accept"][condition]]
        summary[condition] = {"cases": len(rows), "accepted": len(accepted),
                              "coverage": len(accepted) / len(rows),
                              "silent_invalid": sum(row["invalid"] for row in accepted),
                              "silent_invalid_risk": float(np.mean([row["invalid"] for row in accepted])) if accepted else None,
                              "accepted_rats": len({row["rat"] for row in accepted})}
    payload = {"protocol_version": config["protocol_version"], "config_sha256": _sha256(config_path),
               "dataset_doi": config["dataset_doi"], "segmentation_provenance": "source U-Net plus post-processing correction",
               "independent_rats": len({row["rat"] for row in rows}), "paired_volumes": len(seg_paths),
               "stress_cases": len(rows), "summary": summary,
               "risk_coverage_auc": {name: _risk_coverage_auc(rows, name) for name in ("endpoint_qc", "topology_qc", "full_contract")},
               "status": "complete", "claim_boundary": config["claim_boundary"]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "case_rows.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "bone_network_3d.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload

