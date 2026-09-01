"""PSHG production-path amendment for missing FI outside acquisition support."""

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
    coherence_visual,
    load_intraop_profile,
    load_pshg_directory,
    orientation_visual,
)
from nostos.intraop.label_free_v1_1 import analyze_unstained_field as analyze_unstained_field_v1_1


SCHEMA_VERSION = "nostos-intraop-label-free-result/1.2"


def sanitize_reference_map(
    reference_fi_map: np.ndarray,
    r2_map: np.ndarray,
    snr_map: np.ndarray,
    profile: dict[str, Any],
) -> tuple[np.ndarray, dict[str, int | float | str | bool]]:
    """Exclude missing evaluation reference only outside locked acquisition support."""

    reference = np.asarray(reference_fi_map, dtype=np.float64)
    r2 = np.asarray(r2_map, dtype=np.float64)
    snr = np.asarray(snr_map, dtype=np.float64)
    if reference.shape != r2.shape or reference.shape != snr.shape:
        raise ValueError("FI, R2 and SNR maps must be shape matched.")
    minimum_r2 = float(profile["input_contract"]["minimum_r2"])
    minimum_snr = float(profile["input_contract"]["minimum_snr_db"])
    supported = (
        np.isfinite(r2)
        & np.isfinite(snr)
        & (r2 >= minimum_r2)
        & (snr >= minimum_snr)
    )
    finite = np.isfinite(reference)
    missing_inside_support = (~finite) & supported
    if np.any(missing_inside_support):
        raise ValueError(
            "The FI evaluation map is non-finite inside locked R2/SNR acquisition support."
        )
    sentinel = 0.0
    sanitized = np.where(finite, reference, sentinel)
    return sanitized, {
        "pixels": int(reference.size),
        "fi_nonfinite_pixels": int(np.sum(~finite)),
        "r2_snr_supported_pixels": int(np.sum(supported)),
        "fi_nonfinite_inside_r2_snr_support": int(np.sum(missing_inside_support)),
        "fi_nonfinite_outside_r2_snr_support": int(np.sum((~finite) & (~supported))),
        "fi_finite_inside_r2_snr_support": int(np.sum(finite & supported)),
        "interface_sentinel_degrees": sentinel,
        "policy": "missing FI is excluded only outside locked R2/SNR support; no interpolation",
        "scientific_measurement_use": False,
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
    reference_diagnostic = None
    sanitized_reference = None
    if reference_fi_map is not None:
        sanitized_reference, reference_diagnostic = sanitize_reference_map(
            reference_fi_map,
            r2_map,
            snr_map,
            profile,
        )
    result = analyze_unstained_field_v1_1(
        image,
        pixel_size_um=pixel_size_um,
        modality=modality,
        profile=profile,
        verified_stack_frame_count=verified_stack_frame_count,
        r2_map=r2_map,
        snr_map=snr_map,
        reference_fi_map=sanitized_reference,
    )
    payload = dict(result.payload)
    payload["schema_version"] = SCHEMA_VERSION
    if reference_diagnostic is not None:
        payload["reference_map_handling"] = reference_diagnostic
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
