"""Production-path structural mapping for unstained 2-D microscopy.

The module deliberately separates a technically supported measurement from a
clinical interpretation.  The only promoted profile in NOSTOS-0 is the exact
ten-frame PSHG-TISS FSHG construction used in the frozen breast-tissue
confirmation.  Every other input remains useful for research visualization but
is labelled unvalidated, and every clinical decision is withheld.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image
from scipy import ndimage

from nostos.core.qc import acquisition_qc


SCHEMA_VERSION = "nostos-intraop-label-free-result/1.0"
PROFILE_SCHEMA = "nostos-intraop-acquisition-profile/1.0"
CLINICAL_WITHHOLDING_REASON = (
    "No locked prospective clinical endpoint, decision-impact study or patient-outcome "
    "evidence is registered for this acquisition profile."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(str(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _project_root(profile_path: Path) -> Path:
    resolved = profile_path.resolve()
    if resolved.parent.name == "configs":
        return resolved.parent.parent
    raise ValueError("The intra-operative profile must be stored in the project configs directory.")


def load_intraop_profile(path: Path) -> dict[str, Any]:
    """Load an acquisition profile and verify every linked evidence artifact."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PROFILE_SCHEMA:
        raise ValueError(f"Unsupported intra-operative profile schema: {path}")
    evidence = payload.get("evidence", {})
    required = ("receipt_path", "receipt_sha256", "receipt_bytes", "receipt_status")
    missing = [name for name in required if name not in evidence]
    if missing:
        raise ValueError(f"Intra-operative profile evidence is incomplete: {missing}")
    root = _project_root(path)
    receipt = root / str(evidence["receipt_path"])
    if not receipt.is_file():
        raise ValueError(f"Profile evidence receipt is missing: {receipt}")
    if receipt.stat().st_size != int(evidence["receipt_bytes"]):
        raise ValueError("Profile evidence receipt byte count does not match.")
    observed_sha256 = _sha256(receipt)
    if observed_sha256 != str(evidence["receipt_sha256"]):
        raise ValueError("Profile evidence receipt SHA-256 does not match.")
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    if receipt_payload.get("status") != evidence["receipt_status"]:
        raise ValueError("Profile evidence receipt status does not match.")
    result = dict(payload)
    result["profile_path"] = str(path.resolve())
    result["profile_sha256"] = _sha256(path)
    result["verified_evidence"] = {
        "path": str(evidence["receipt_path"]),
        "bytes": receipt.stat().st_size,
        "sha256": observed_sha256,
        "status": receipt_payload.get("status"),
    }
    return result


def _as_grayscale(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image)
    if data.ndim == 3 and data.shape[-1] in {3, 4}:
        rgb = data[..., :3].astype(np.float64)
        data = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    if data.ndim != 2 or min(data.shape) < 32:
        raise ValueError(f"Label-free mapping requires one 2-D field at least 32 x 32; received {data.shape}.")
    data = np.asarray(data, dtype=np.float64)
    if not np.isfinite(data).all():
        raise ValueError("Label-free input must contain only finite numeric values.")
    return data


def local_orientation_field(
    image: np.ndarray,
    *,
    sigma_pixels: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return axial direction, coherence and energy using the confirmed estimator."""

    if not np.isfinite(sigma_pixels) or sigma_pixels <= 0:
        raise ValueError("sigma_pixels must be finite and positive.")
    data = _as_grayscale(image)
    gy, gx = np.gradient(data)
    jxx = ndimage.gaussian_filter(gx * gx, sigma=sigma_pixels, mode="reflect")
    jyy = ndimage.gaussian_filter(gy * gy, sigma=sigma_pixels, mode="reflect")
    jxy = ndimage.gaussian_filter(gx * gy, sigma=sigma_pixels, mode="reflect")
    delta = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy**2)
    energy = jxx + jyy
    angle = np.mod(0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + np.pi / 2.0, np.pi)
    orientation = np.degrees(angle)
    coherence = delta / np.maximum(energy, np.finfo(float).eps)
    return orientation, np.clip(coherence, 0.0, 1.0), energy


def _axial_summary(
    orientation: np.ndarray,
    coherence: np.ndarray,
    energy: np.ndarray,
    eligible: np.ndarray,
) -> dict[str, float | int | None]:
    count = int(np.sum(eligible))
    if not count:
        return {
            "eligible_pixels": 0,
            "eligible_fraction": 0.0,
            "mean_axial_orientation_degrees": None,
            "axial_resultant": None,
            "median_coherence": None,
            "p10_coherence": None,
            "p90_coherence": None,
        }
    angles = np.radians(orientation[eligible])
    energy_values = energy[eligible]
    energy_scale = max(float(np.median(energy_values)), np.finfo(float).eps)
    weights = coherence[eligible] * np.sqrt(np.clip(energy_values / energy_scale, 0.0, 100.0))
    weights = np.maximum(weights, np.finfo(float).eps)
    vector = np.sum(weights * np.exp(2j * angles)) / np.sum(weights)
    direction = float((0.5 * np.degrees(np.angle(vector))) % 180.0)
    coherence_values = coherence[eligible]
    return {
        "eligible_pixels": count,
        "eligible_fraction": float(count / eligible.size),
        "mean_axial_orientation_degrees": direction,
        "axial_resultant": float(abs(vector)),
        "median_coherence": float(np.median(coherence_values)),
        "p10_coherence": float(np.percentile(coherence_values, 10.0)),
        "p90_coherence": float(np.percentile(coherence_values, 90.0)),
    }


def _axial_error(measured: np.ndarray, reference: np.ndarray) -> np.ndarray:
    difference = np.abs(measured - reference) % 180.0
    return np.minimum(difference, 180.0 - difference)


@dataclass(frozen=True)
class IntraopResult:
    payload: dict[str, Any]
    orientation_degrees: np.ndarray
    coherence: np.ndarray
    energy: np.ndarray
    eligible: np.ndarray
    source_image: np.ndarray


def analyze_unstained_field(
    image: np.ndarray,
    *,
    pixel_size_um: float,
    modality: str = "generic_label_free",
    mask: np.ndarray | None = None,
    profile: dict[str, Any] | None = None,
    verified_stack_frame_count: int | None = None,
    r2_map: np.ndarray | None = None,
    snr_map: np.ndarray | None = None,
    reference_fi_map: np.ndarray | None = None,
) -> IntraopResult:
    """Map an unstained field while failing closed on evidence and clinical use."""

    if not np.isfinite(pixel_size_um) or pixel_size_um <= 0:
        raise ValueError("pixel_size_um must be finite and positive.")
    source = _as_grayscale(image)
    profile_contract = None if profile is None else profile["input_contract"]
    sigma = (
        2.0
        if profile is None
        else float(profile["measurement_contract"]["integration_sigma_pixels"])
    )
    orientation, coherence, energy = local_orientation_field(source, sigma_pixels=sigma)
    eligible = np.isfinite(orientation) & np.isfinite(coherence) & (energy > np.finfo(float).eps) & (source > 0)
    reasons: list[str] = []

    if mask is not None:
        supplied = np.asarray(mask, dtype=bool)
        if supplied.shape != source.shape:
            raise ValueError("The optional field mask must match the image shape.")
        eligible &= supplied

    support_maps_supplied = r2_map is not None and snr_map is not None
    if (r2_map is None) != (snr_map is None):
        raise ValueError("R2 and SNR support maps must be supplied together.")
    if support_maps_supplied:
        r2 = np.asarray(r2_map, dtype=float)
        snr = np.asarray(snr_map, dtype=float)
        if r2.shape != source.shape or snr.shape != source.shape:
            raise ValueError("R2 and SNR support maps must match the image shape.")
        if not np.isfinite(r2).all() or not np.isfinite(snr).all():
            raise ValueError("R2 and SNR support maps must be finite.")
        minimum_r2 = 0.90 if profile_contract is None else float(profile_contract["minimum_r2"])
        minimum_snr = 3.0 if profile_contract is None else float(profile_contract["minimum_snr_db"])
        eligible &= (r2 >= minimum_r2) & (snr >= minimum_snr)

    edge = 8 if profile_contract is None else int(profile_contract["edge_exclusion_pixels"])
    if edge * 2 >= min(source.shape):
        raise ValueError("The edge exclusion is too large for this field.")
    eligible[:edge] = False
    eligible[-edge:] = False
    eligible[:, :edge] = False
    eligible[:, -edge:] = False

    exact_profile_input = bool(
        profile is not None
        and modality == str(profile["modality"])
        and str(profile["specimen_state"]) == "unstained"
        and verified_stack_frame_count == int(profile_contract["frame_count"])
        and support_maps_supplied
    )
    if profile is None:
        reasons.append("no_verified_acquisition_profile")
    elif modality != str(profile["modality"]):
        reasons.append("modality_does_not_match_profile")
    if verified_stack_frame_count != (None if profile_contract is None else int(profile_contract["frame_count"])):
        reasons.append("exact_frame_construction_not_verified")
    if not support_maps_supplied:
        reasons.append("required_R2_and_SNR_support_maps_not_supplied")

    quality = acquisition_qc(source)
    if quality["status"] == "abstain":
        reasons.append("acquisition_qc_abstain")
    minimum_pixels = 1000 if profile_contract is None else int(profile_contract["minimum_eligible_pixels"])
    summary = _axial_summary(orientation, coherence, energy, eligible)
    if int(summary["eligible_pixels"] or 0) < minimum_pixels:
        reasons.append("insufficient_eligible_pixels")

    if int(summary["eligible_pixels"] or 0) < minimum_pixels or quality["status"] == "abstain":
        technical_status = "abstain"
    elif quality["status"] == "review" or not exact_profile_input:
        technical_status = "review"
    else:
        technical_status = "valid"
    evidence_status = (
        str(profile["measurement_contract"]["evidence_status"])
        if exact_profile_input and technical_status == "valid" and profile is not None
        else "unvalidated"
    )

    evaluation: dict[str, Any] | None = None
    if reference_fi_map is not None:
        reference = np.asarray(reference_fi_map, dtype=float)
        if reference.shape != source.shape or not np.isfinite(reference).all():
            raise ValueError("The optional FI evaluation map must be finite and shape matched.")
        offset = 90.0
        truth = np.mod(reference + offset, 180.0)
        errors = _axial_error(orientation[eligible], truth[eligible])
        evaluation = {
            "role": "evaluation_only_not_available_during_deployment",
            "reference_offset_degrees": offset,
            "eligible_pixels": int(errors.size),
            "median_axial_error_degrees": None if not errors.size else float(np.median(errors)),
            "p75_axial_error_degrees": None if not errors.size else float(np.percentile(errors, 75.0)),
            "axial_alignment": None if not errors.size else float(np.mean(np.cos(2.0 * np.radians(errors)))),
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": technical_status,
        "intended_use": "research_use_only_intraoperative_integration",
        "specimen_state": "unstained",
        "modality": modality,
        "input": {
            "shape": list(source.shape),
            "pixel_size_um": float(pixel_size_um),
            "verified_stack_frame_count": verified_stack_frame_count,
            "support_maps_supplied": support_maps_supplied,
            "mask_supplied": mask is not None,
            "source_array_sha256": _array_sha256(source),
        },
        "profile": (
            None
            if profile is None
            else {
                "profile_id": profile["profile_id"],
                "profile_sha256": profile["profile_sha256"],
                "verified_evidence": profile["verified_evidence"],
                "exact_input_contract_satisfied": exact_profile_input,
                "claim_boundary": profile["claim_boundary"],
            }
        ),
        "measurement": {
            "endpoint": "local_axial_structure_orientation",
            "integration_sigma_pixels": sigma,
            "integration_sigma_um": float(sigma * pixel_size_um),
            "evidence_status": evidence_status,
            "summary": summary,
            "map_hashes": {
                "orientation_degrees": _array_sha256(orientation.astype(np.float32)),
                "coherence": _array_sha256(coherence.astype(np.float32)),
                "eligible": _array_sha256(eligible.astype(np.uint8)),
            },
        },
        "acquisition_qc": quality,
        "validity_reasons": sorted(set(reasons)),
        "reference_evaluation": evaluation,
        "clinical_output": {
            "status": "withheld",
            "diagnosis": None,
            "margin_or_boundary": None,
            "mechanical_property": None,
            "treatment_recommendation": None,
            "reason": CLINICAL_WITHHOLDING_REASON,
        },
    }
    return IntraopResult(payload, orientation, coherence, energy, eligible, source)


def _frame_sort_key(path: Path) -> int:
    try:
        return int(path.stem.rsplit("p", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"Cannot parse PSHG polarization angle from {path.name}.") from error


def load_pshg_directory(directory: Path) -> dict[str, Any]:
    frames = sorted(directory.glob("*_FSHG_p*.tif"), key=_frame_sort_key)
    if len(frames) != 10:
        raise ValueError(f"{directory.name}: expected exactly ten FSHG frames; found {len(frames)}.")
    angles = [_frame_sort_key(path) for path in frames]
    if angles != list(range(0, 181, 20)):
        raise ValueError(f"{directory.name}: expected polarization angles 0:20:180; found {angles}.")
    arrays = [tifffile.imread(path).astype(np.float64) for path in frames]
    shape = arrays[0].shape
    if any(array.shape != shape for array in arrays):
        raise ValueError(f"{directory.name}: PSHG frames are not shape matched.")
    r2_path = directory / "R2.tif"
    snr_path = directory / "SNR.tif"
    if not r2_path.is_file() or not snr_path.is_file():
        raise ValueError(f"{directory.name}: R2.tif and SNR.tif are required.")
    fi_path = directory / "FI.tif"
    return {
        "frames": np.stack(arrays),
        "frame_paths": frames,
        "r2": tifffile.imread(r2_path).astype(np.float64),
        "snr": tifffile.imread(snr_path).astype(np.float64),
        "fi": tifffile.imread(fi_path).astype(np.float64) if fi_path.is_file() else None,
        "support_paths": [r2_path, snr_path],
        "reference_path": fi_path if fi_path.is_file() else None,
    }


def _unit_image(image: np.ndarray) -> np.ndarray:
    low, high = np.percentile(image, (1.0, 99.0))
    if not np.isfinite((low, high)).all() or high <= low:
        return np.zeros(image.shape, dtype=np.uint8)
    return np.rint(255.0 * np.clip((image - low) / (high - low), 0.0, 1.0)).astype(np.uint8)


def orientation_visual(result: IntraopResult) -> np.ndarray:
    hue = np.rint(255.0 * np.mod(result.orientation_degrees, 180.0) / 180.0).astype(np.uint8)
    saturation = np.rint(255.0 * np.clip(result.coherence, 0.0, 1.0)).astype(np.uint8)
    value = _unit_image(result.source_image)
    value = np.where(result.eligible, np.maximum(value, 48), np.rint(0.18 * value)).astype(np.uint8)
    saturation = np.where(result.eligible, saturation, 0).astype(np.uint8)
    hsv = np.stack((hue, saturation, value), axis=-1)
    return np.asarray(Image.fromarray(hsv, mode="HSV").convert("RGB"))


def coherence_visual(result: IntraopResult) -> np.ndarray:
    value = np.clip(result.coherence, 0.0, 1.0)
    red = np.clip(1.8 * value - 0.35, 0.0, 1.0)
    green = np.clip(1.8 - 2.2 * np.abs(value - 0.62), 0.0, 1.0)
    blue = np.clip(1.25 - 1.7 * value, 0.0, 1.0)
    rgb = np.rint(255.0 * np.stack((red, green, blue), axis=-1)).astype(np.uint8)
    return np.where(result.eligible[..., None], rgb, np.rint(0.15 * rgb)).astype(np.uint8)


def analyze_pshg_directory(
    directory: Path,
    output: Path,
    *,
    profile_path: Path,
    pixel_size_um: float = 1.0,
    include_reference_evaluation: bool = False,
) -> dict[str, Any]:
    """Run the exact unstained PSHG production path and persist auditable maps."""

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
    receipt_path = output / "intraop_result.json"
    receipt_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload

