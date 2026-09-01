"""Prospective bone-SHG orientation contract with withheld invalidity tests."""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, shift
from skimage.transform import resize

from nostos.features.response_modules import structure_tensor_response
from nostos.validation.metrics import axial_angular_error_degrees


LABELS = {(0, 255, 0): "green", (255, 0, 0): "red", (0, 0, 255): "blue"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise(image: np.ndarray) -> np.ndarray:
    values = np.asarray(image, dtype=np.float32)
    lo, hi = np.percentile(values, (1, 99))
    return np.clip((values - lo) / max(float(hi - lo), np.finfo(np.float32).eps), 0, 1)


def _measure(tile: np.ndarray, scales: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    response = structure_tensor_response(tile, spacing_um=(1.0, 1.0), scales_um=scales)
    return np.asarray(response.orientation_degrees), np.asarray(response.coherency)


def _majority_label(mask: np.ndarray) -> tuple[str, float]:
    flat = np.asarray(mask).reshape(-1, 3)
    counts = {name: int(np.all(flat == colour, axis=1).sum()) for colour, name in LABELS.items()}
    name = max(counts, key=counts.get)
    return name, counts[name] / max(1, len(flat))


def evaluate_tile(tile: np.ndarray, mask: np.ndarray, config: dict) -> dict:
    tile = _normalise(tile)
    scales = tuple(float(value) for value in config["tensor_scales_pixels"])
    angles, coherence = _measure(tile, scales)
    reference = float(angles[0])
    internal = config["internal_probes"]
    probes = [
        gaussian_filter(tile, float(internal["gaussian_blur_sigma"])),
        np.power(tile, float(internal["contrast_gamma"])),
        shift(tile, internal["translation_pixels"], mode="nearest"),
    ]
    internal_drifts = [
        axial_angular_error_degrees(reference, float(_measure(probe, (scales[0],))[0][0]))
        for probe in probes
    ]
    interscale = axial_angular_error_degrees(float(angles[0]), float(angles[1]))
    dynamic = float(np.percentile(tile, 99) - np.percentile(tile, 1))
    # Score terms are all contract-visible. Lower is better.
    score = max(internal_drifts + [interscale])

    withheld = config["withheld_tests"]
    y_factor = float(withheld["anisotropic_y_factor"])
    compressed = resize(tile, (max(8, round(tile.shape[0] * y_factor)), tile.shape[1]),
                        preserve_range=True, anti_aliasing=True)
    restored = resize(compressed, tile.shape, preserve_range=True, anti_aliasing=True)
    anisotropic_drift = axial_angular_error_degrees(
        reference, float(_measure(restored, (scales[0],))[0][0])
    )
    border = int(withheld["crop_border_pixels"])
    cropped = tile[border:-border, border:-border]
    crop_drift = axial_angular_error_degrees(
        reference, float(_measure(cropped, (scales[0],))[0][0])
    )
    label, label_fraction = _majority_label(mask)
    withheld_limit = float(withheld["maximum_axial_drift_degrees"])
    invalid = label != "green" or anisotropic_drift > withheld_limit or crop_drift > withheld_limit
    return {
        "orientation_degrees": reference,
        "coherence": float(coherence[0]),
        "dynamic_range": dynamic,
        "contract_score_degrees": float(score),
        "internal_max_drift_degrees": float(max(internal_drifts)),
        "interscale_drift_degrees": float(interscale),
        "withheld_anisotropic_drift_degrees": float(anisotropic_drift),
        "withheld_crop_drift_degrees": float(crop_drift),
        "majority_label": label,
        "majority_label_fraction": float(label_fraction),
        "invalid": bool(invalid),
    }


def _mouse_from_path(path: Path) -> str:
    match = re.search(r"Mouse(\d+)", str(path))
    if not match:
        raise ValueError(f"No mouse identifier in {path}")
    return f"Mouse{match.group(1)}"


def _sample_paths(mask_root: Path, maximum_slices: int) -> list[Path]:
    selected = []
    groups: dict[Path, list[Path]] = {}
    for path in mask_root.rglob("*.png"):
        groups.setdefault(path.parent, []).append(path)
    for paths in groups.values():
        ordered = sorted(paths)
        indices = np.linspace(0, len(ordered) - 1, min(maximum_slices, len(ordered)), dtype=int)
        selected.extend(ordered[index] for index in sorted(set(indices)))
    return sorted(selected)


def _matching_image(image_root: Path, mask_root: Path, mask_path: Path) -> Path:
    relative = mask_path.relative_to(mask_root)
    candidates = [image_root / relative, image_root / relative.with_suffix(".tif"),
                  image_root / relative.with_suffix(".tiff")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    hits = list(image_root.rglob(mask_path.name))
    if len(hits) == 1:
        return hits[0]
    raise FileNotFoundError(f"No unambiguous image for {mask_path}")


def _cluster_upper(rows: list[dict], threshold: float) -> float:
    groups = sorted({row["mouse"] for row in rows})
    by_group = {group: [row for row in rows if row["mouse"] == group] for group in groups}
    counts = {}
    for group in groups:
        accepted = [row for row in by_group[group]
                    if row["eligible"] and row["contract_score_degrees"] <= threshold]
        counts[group] = (sum(row["invalid"] for row in accepted), len(accepted))
    risks = []
    # With four mice the exact empirical cluster bootstrap has only 4^4=256 draws.
    for sampled in itertools.product(groups, repeat=len(groups)):
        invalid = sum(counts[group][0] for group in sampled)
        accepted = sum(counts[group][1] for group in sampled)
        if accepted:
            risks.append(invalid / accepted)
    return float(np.quantile(risks, 0.975)) if risks else 1.0


def _summary(rows: list[dict], threshold: float) -> dict:
    eligible = [row for row in rows if row["eligible"]]
    accepted = [row for row in eligible if row["contract_score_degrees"] <= threshold]
    return {
        "mice": len({row["mouse"] for row in rows}),
        "tiles": len(rows),
        "eligible": len(eligible),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(eligible) if eligible else 0.0,
        "silent_invalid_risk": float(np.mean([row["invalid"] for row in accepted])) if accepted else None,
        "mouse_cluster_risk_upper95": _cluster_upper(rows, threshold),
    }


def select_threshold(rows: list[dict], config: dict) -> tuple[float | None, dict | None]:
    candidates = sorted({row["contract_score_degrees"] for row in rows if row["eligible"]})
    passing = []
    for threshold in candidates:
        summary = _summary(rows, threshold)
        if (summary["coverage"] >= config["development_minimum_coverage"] and
                summary["mouse_cluster_risk_upper95"] <= config["development_maximum_cluster_risk_upper95"]):
            passing.append((threshold, summary))
    # Largest threshold is least restrictive and maximises coverage among valid choices.
    return max(passing, key=lambda item: item[0]) if passing else (None, None)


def run(image_root: Path, mask_root: Path, config_path: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rows = []
    paths = _sample_paths(mask_root, int(config["maximum_slices_per_scan"]))
    size, stride = int(config["tile_size_pixels"]), int(config["tile_stride_pixels"])
    for mask_path in paths:
        image_path = _matching_image(image_root, mask_root, mask_path)
        with Image.open(image_path) as opened:
            image = np.asarray(opened.convert("L"))
        with Image.open(mask_path) as opened:
            mask = np.asarray(opened.convert("RGB"))
        candidates = [(y, x) for y in range(0, image.shape[0] - size + 1, stride)
                      for x in range(0, image.shape[1] - size + 1, stride)]
        # Deterministic spatial coverage; no label-aware sampling.
        limit = int(config["maximum_tiles_per_slice"])
        if len(candidates) > limit:
            idx = np.linspace(0, len(candidates) - 1, limit, dtype=int)
            candidates = [candidates[index] for index in sorted(set(idx))]
        for y, x in candidates:
            row = evaluate_tile(image[y:y + size, x:x + size], mask[y:y + size, x:x + size], config)
            row.update({"mouse": _mouse_from_path(mask_path), "scan": str(mask_path.parent.relative_to(mask_root)),
                        "slice": mask_path.name, "y": y, "x": x})
            row["eligible"] = bool(row["dynamic_range"] >= config["minimum_dynamic_range_fraction"] and row["coherence"] > 0)
            rows.append(row)
    development = [row for row in rows if row["mouse"] in config["development_mice"]]
    evaluation = [row for row in rows if row["mouse"] in config["evaluation_mice"]]
    threshold, development_summary = select_threshold(development, config)
    evaluation_summary = _summary(evaluation, threshold) if threshold is not None else None
    payload = {
        "protocol_version": config["protocol_version"], "config_sha256": _sha256(config_path),
        "dataset_doi": config["dataset_doi"], "status": "pass" if threshold is not None else "fail_no_promotable_threshold",
        "promoted_threshold_degrees": threshold, "development": development_summary,
        "evaluation": evaluation_summary, "claim_boundary": config["claim_boundary"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "case_rows.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "bone_orientation_v2.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
