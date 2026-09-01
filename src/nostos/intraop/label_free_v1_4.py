"""Release-candidate PSHG production path with collision-free artifact provenance."""

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
from nostos.intraop.label_free_v1_3 import analyze_unstained_field as analyze_unstained_field_v1_3


SCHEMA_VERSION = "nostos-intraop-label-free-result/1.4"


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
    result = analyze_unstained_field_v1_3(
        image,
        pixel_size_um=pixel_size_um,
        modality=modality,
        profile=profile,
        verified_stack_frame_count=verified_stack_frame_count,
        r2_map=r2_map,
        snr_map=snr_map,
        reference_fi_map=reference_fi_map,
    )
    payload = dict(result.payload)
    payload["schema_version"] = SCHEMA_VERSION
    return IntraopResult(
        payload,
        result.orientation_degrees,
        result.coherence,
        result.energy,
        result.eligible,
        result.source_image,
    )


def export_case_artifacts(result: IntraopResult, output: Path) -> dict[str, dict[str, Any]]:
    """Export every numerical and visual product under a unique provenance key."""

    output.mkdir(parents=True, exist_ok=True)
    arrays = {
        "orientation_array": ("orientation_degrees.npy", result.orientation_degrees.astype(np.float32)),
        "coherence_array": ("coherence.npy", result.coherence.astype(np.float32)),
        "eligible_array": ("eligible.npy", result.eligible.astype(np.uint8)),
    }
    images = {
        "source_image": ("source.png", np.repeat(_unit_image(result.source_image)[..., None], 3, axis=-1)),
        "orientation_image": ("orientation.png", orientation_visual(result)),
        "coherence_image": ("coherence.png", coherence_visual(result)),
        "support_image": ("support.png", np.repeat((255 * result.eligible.astype(np.uint8))[..., None], 3, axis=-1)),
    }
    artifacts: dict[str, dict[str, Any]] = {}
    for key, (name, array) in arrays.items():
        path = output / name
        np.save(path, array, allow_pickle=False)
        artifacts[key] = {"path": path.name, "media_type": "application/x-npy", "bytes": path.stat().st_size, "sha256": _sha256(path)}
    for key, (name, array) in images.items():
        path = output / name
        Image.fromarray(array).save(path, format="PNG", optimize=True)
        artifacts[key] = {"path": path.name, "media_type": "image/png", "bytes": path.stat().st_size, "sha256": _sha256(path)}
    paths = [item["path"] for item in artifacts.values()]
    if len(paths) != len(set(paths)):
        raise RuntimeError("Artifact provenance paths must be unique.")
    return artifacts


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
    artifacts = export_case_artifacts(result, output)
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
    payload["artifact_manifest"] = {
        "schema_version": "nostos-artifact-manifest/1.0",
        "expected_count": 7,
        "unique_keys": True,
        "unique_paths": True,
    }
    payload["artifacts"] = artifacts
    (output / "intraop_result.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload
