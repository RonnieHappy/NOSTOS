"""Frozen orientation contract ablation on paired SHG/TPF mouse bone images."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import gaussian_filter, shift
from skimage.transform import resize

from nostos.features.response_modules import structure_tensor_response
from nostos.validation.metrics import axial_angular_error_degrees


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _normalize(image: np.ndarray) -> np.ndarray:
    image = np.asarray(image, dtype=float)
    lo, hi = np.percentile(image, [1, 99])
    return np.clip((image - lo) / max(hi - lo, np.finfo(float).eps), 0, 1)


def _measure(tile: np.ndarray, scales: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    result = structure_tensor_response(tile, spacing_um=(1.0, 1.0), scales_um=scales)
    return np.asarray(result.orientation_degrees), np.asarray(result.coherency)


def _tiles(image: np.ndarray, *, size: int, count: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    h, w = image.shape
    if h < size or w < size:
        return [resize(image, (size, size), preserve_range=True, anti_aliasing=True)]
    candidates = [(y, x) for y in range(0, h - size + 1, size) for x in range(0, w - size + 1, size)]
    selected = rng.choice(len(candidates), size=min(count, len(candidates)), replace=False)
    return [image[candidates[i][0]:candidates[i][0] + size, candidates[i][1]:candidates[i][1] + size] for i in selected]


def _perturbed(tile: np.ndarray, config: dict) -> list[np.ndarray]:
    factor = float(config["perturbations"]["resample_factor"])
    small = resize(tile, (round(tile.shape[0] * factor), round(tile.shape[1] * factor)), preserve_range=True, anti_aliasing=True)
    restored = resize(small, tile.shape, preserve_range=True, anti_aliasing=True)
    gamma = np.power(np.clip(tile, 0, 1), float(config["perturbations"]["contrast_gamma"]))
    moved = shift(tile, config["perturbations"]["translation_pixels"], mode="nearest")
    blurred = gaussian_filter(tile, float(config["perturbations"]["gaussian_blur_sigma"]))
    return [blurred, gamma, moved, restored]


def _conditions(dynamic_range: float, coherence: float, max_drift: float, interscale: float, config: dict) -> dict[str, bool]:
    signal = dynamic_range >= config["minimum_dynamic_range_fraction"]
    endpoint = signal and coherence >= config["endpoint_qc_minimum_coherence"]
    full = (signal and coherence >= config["full_contract_minimum_coherence"]
            and max_drift <= config["maximum_perturbation_axial_drift_degrees"]
            and interscale <= config["maximum_interscale_axial_drift_degrees"])
    return {
        "always_emit": True,
        "endpoint_qc": endpoint,
        "partial_no_stability": signal and coherence >= config["full_contract_minimum_coherence"] and interscale <= config["maximum_interscale_axial_drift_degrees"],
        "partial_no_interscale": signal and coherence >= config["full_contract_minimum_coherence"] and max_drift <= config["maximum_perturbation_axial_drift_degrees"],
        "full_contract": full,
    }


def run(data_dir: Path, config_path: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    files = sorted(data_dir.glob("*.tif"))
    rows = []
    for path in files:
        match = re.match(r"MosaicJ_(.+?)_(SHG|TPF)_", path.name)
        if not match:
            continue
        specimen, modality = match.groups()
        image = _normalize(tifffile.imread(path))
        seed = int(hashlib.sha256(specimen.encode()).hexdigest()[:8], 16)
        for index, tile in enumerate(_tiles(image, size=config["tile_size_pixels"], count=config["tiles_per_specimen"], seed=seed)):
            angles, coherences = _measure(tile, tuple(config["tensor_scales_pixels"]))
            reference = float(angles[0])
            perturbed_angles = [float(_measure(p, (config["tensor_scales_pixels"][0],))[0][0]) for p in _perturbed(tile, config)]
            drifts = [axial_angular_error_degrees(reference, value) for value in perturbed_angles]
            max_drift = float(max(drifts))
            interscale = float(axial_angular_error_degrees(angles[0], angles[1]))
            dynamic = float(np.percentile(tile, 99) - np.percentile(tile, 1))
            invalid = bool(max_drift > config["maximum_perturbation_axial_drift_degrees"])
            accepts = {name: False for name in ("always_emit", "endpoint_qc", "partial_no_stability", "partial_no_interscale", "full_contract")}
            if modality == "SHG":
                accepts = _conditions(dynamic, float(coherences[0]), max_drift, interscale, config)
            rows.append({"specimen": specimen, "modality": modality, "tile": index, "dynamic_range": dynamic,
                         "orientation_degrees": reference, "coherence": float(coherences[0]),
                         "max_perturbation_drift_degrees": max_drift, "interscale_drift_degrees": interscale,
                         "invalid": invalid, "accept": accepts})

    conditions = list(rows[0]["accept"])
    summaries = {}
    for modality in ("SHG", "TPF"):
        subset = [r for r in rows if r["modality"] == modality]
        summaries[modality] = {}
        for condition in conditions:
            accepted = [r for r in subset if r["accept"][condition]]
            summaries[modality][condition] = {
                "tiles": len(subset), "accepted": len(accepted),
                "coverage": len(accepted) / len(subset) if subset else 0,
                "silent_invalid": sum(r["invalid"] for r in accepted),
                "silent_invalid_risk": sum(r["invalid"] for r in accepted) / len(accepted) if accepted else None,
            }
    mouse = {}
    for specimen in sorted({r["specimen"] for r in rows}):
        subset = [r for r in rows if r["specimen"] == specimen and r["modality"] == "SHG"]
        mouse[specimen] = {condition: {
            "coverage": sum(r["accept"][condition] for r in subset) / len(subset),
            "risk": (sum(r["invalid"] and r["accept"][condition] for r in subset) / max(1, sum(r["accept"][condition] for r in subset)))
        } for condition in conditions}
    payload = {
        "protocol_version": config["protocol_version"], "status": "confirmation_complete",
        "config_sha256": _hash(config_path), "dataset": "figshare-20765659",
        "independent_units": len(mouse), "rows": len(rows), "summary": summaries,
        "mouse_level": mouse,
        "gates": {
            "shg_full_coverage_at_least_0_70": summaries["SHG"]["full_contract"]["coverage"] >= 0.70,
            "shg_full_risk_below_always_emit": (
                summaries["SHG"]["full_contract"]["silent_invalid_risk"] is not None
                and summaries["SHG"]["full_contract"]["silent_invalid_risk"]
                < summaries["SHG"]["always_emit"]["silent_invalid_risk"]
            ),
            "tpf_orientation_abstains": summaries["TPF"]["full_contract"]["coverage"] == 0,
        },
        "claim_boundary": config["claim_boundary"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "case_rows.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "bone_orientation_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
