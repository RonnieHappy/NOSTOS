"""PSHG production-path amendment for non-finite support-domain pixels."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from nostos.intraop.label_free import (
    IntraopResult,
    _sha256,
    _unit_image,
    analyze_unstained_field as analyze_unstained_field_v1,
    coherence_visual,
    load_intraop_profile,
    load_pshg_directory,
    orientation_visual,
)


SCHEMA_VERSION = "nostos-intraop-label-free-result/1.1"


def sanitize_support_maps(
    r2_map: np.ndarray,
    snr_map: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    """Make unsupported pixels explicitly subthreshold without imputation."""

    r2 = np.asarray(r2_map, dtype=np.float64)
    snr = np.asarray(snr_map, dtype=np.float64)
    if r2.shape != snr.shape:
        raise ValueError("R2 and SNR support maps must be shape matched.")
    r2_finite = np.isfinite(r2)
    snr_finite = np.isfinite(snr)
    joint = r2_finite & snr_finite
    if not np.any(joint):
        raise ValueError("R2 and SNR contain no jointly finite support pixels.")
    sanitized_r2 = np.where(r2_finite, r2, -1.0)
    sanitized_snr = np.where(snr_finite, snr, -1.0e6)
    return sanitized_r2, sanitized_snr, {
        "pixels": int(r2.size),
        "r2_nonfinite_pixels": int(np.sum(~r2_finite)),
        "snr_nonfinite_pixels": int(np.sum(~snr_finite)),
        "joint_finite_pixels": int(np.sum(joint)),
        "joint_nonfinite_pixels": int(np.sum(~joint)),
    }


def analyze_unstained_field(
    image: np.ndarray,
    *,
    pixel_size_um: float,
    modality: str,
    profile: dict[str, Any],
    verified_stack_frame_count: int,
    r2_map: np.ndarray,
    snr_map: np.ndarray,
    reference_fi_map: np.ndarray | None = None,
) -> IntraopResult:
    sanitized_r2, sanitized_snr, diagnostic = sanitize_support_maps(r2_map, snr_map)
    result = analyze_unstained_field_v1(
        image,
        pixel_size_um=pixel_size_um,
        modality=modality,
        profile=profile,
        verified_stack_frame_count=verified_stack_frame_count,
        r2_map=sanitized_r2,
        snr_map=sanitized_snr,
        reference_fi_map=reference_fi_map,
    )
    payload = dict(result.payload)
    payload["schema_version"] = SCHEMA_VERSION
    payload["support_map_handling"] = {
        **diagnostic,
        "policy": "non-finite support values are excluded without interpolation",
        "interface_sentinels": {"R2": -1.0, "SNR": -1000000.0},
        "scientific_measurement_use": False,
    }
    return IntraopResult(
        payload,
        result.orientation_degrees,
        result.coherence,
        result.energy,
        result.eligible,
        result.source_image,
    )


def analyze_pshg_directory(
    directory: Path,
    output: Path,
    *,
    profile_path: Path,
    pixel_size_um: float = 1.0,
    include_reference_evaluation: bool = False,
) -> dict[str, Any]:
    total_started = time.perf_counter()
    load_started = time.perf_counter()
    profile = load_intraop_profile(profile_path)
    loaded = load_pshg_directory(directory)
    mean_image = np.mean(loaded["frames"], axis=0)
    load_seconds = time.perf_counter() - load_started

    tracemalloc.start()
    analysis_started = time.perf_counter()
    result = analyze_unstained_field(
        mean_image,
        pixel_size_um=pixel_size_um,
        modality=str(profile["modality"]),
        profile=profile,
        verified_stack_frame_count=int(loaded["frames"].shape[0]),
        r2_map=loaded["r2"],
        snr_map=loaded["snr"],
        reference_fi_map=(loaded["fi"] if include_reference_evaluation else None),
    )
    analysis_seconds = time.perf_counter() - analysis_started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    export_started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    arrays = {
        "orientation_degrees": result.orientation_degrees.astype(np.float32),
        "coherence": result.coherence.astype(np.float32),
        "eligible": result.eligible.astype(np.uint8),
    }
    artifacts: dict[str, dict[str, Any]] = {}
    for name, array in arrays.items():
        path = output / f"{name}.npy"
        np.save(path, array, allow_pickle=False)
        artifacts[name] = {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
    images = {
        "source": np.repeat(_unit_image(result.source_image)[..., None], 3, axis=-1),
        "orientation": orientation_visual(result),
        "coherence": coherence_visual(result),
        "support": np.repeat((255 * result.eligible.astype(np.uint8))[..., None], 3, axis=-1),
    }
    for name, array in images.items():
        path = output / f"{name}.png"
        Image.fromarray(array).save(path, format="PNG", optimize=True)
        artifacts[name] = {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
    export_seconds = time.perf_counter() - export_started

    payload = dict(result.payload)
    payload["case_id"] = directory.name
    payload["source_files"] = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in [*loaded["frame_paths"], *loaded["support_paths"]]
    ]
    if include_reference_evaluation and loaded["reference_path"] is not None:
        path = loaded["reference_path"]
        payload["evaluation_reference_file"] = {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "deployment_input": False,
        }
    payload["runtime"] = {
        "load_seconds": float(load_seconds),
        "analysis_seconds": float(analysis_seconds),
        "export_seconds": float(export_seconds),
        "end_to_end_seconds": float(time.perf_counter() - total_started),
        "peak_python_memory_mb": float(peak_bytes / (1024.0**2)),
        "acquisition_time_included": False,
    }
    payload["artifacts"] = artifacts
    (output / "intraop_result.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload
