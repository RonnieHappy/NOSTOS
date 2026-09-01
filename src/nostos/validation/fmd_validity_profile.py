"""Prospective FMD adapter for the reusable validity-profile compiler."""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image

from nostos.core.qc import acquisition_qc
from nostos.features.response_modules import structure_tensor_response
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.paired_acquisition_support import (
    _probe_images,
    _robust_unit,
    audit_pair_registration,
    evaluate_precomputed_pair,
    shared_spectral_band_cycles_per_mm,
)
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    sha256_file,
    verify_profile,
    write_json,
    write_jsonl,
)


FMD_ADAPTER_VERSION = "nostos-fmd-validity-profile-adapter/1.0"
LEVELS = ("raw", "avg2", "avg4", "avg8", "avg16")
FILENAME = re.compile(
    r"^(?P<group>(?P<modality>Confocal|TwoPhoton|WideField)_(?P<sample>.+))_"
    r"(?P<realization>[1-4])\.png$"
)


@dataclass(frozen=True)
class FMDPairRecord:
    pair_id: str
    reference_group_id: str
    acquisition_modality: str
    sample: str
    noise_realization: int
    acquisition_level: str
    averaged_captures: int
    input_path: str
    reference_path: str
    input_sha256: str
    reference_sha256: str


def _internal_measurement_config(config: Mapping[str, Any]) -> dict[str, Any]:
    measurement = config["measurement"]
    return {
        # The estimator is scale-equivariant. Numeric pixel scales are passed
        # internally, then every physical-unit endpoint is excluded below.
        "physical_scales_um": [float(value) for value in measurement["analysis_scales_px"]],
        "minimum_samples_per_scale": float(measurement["minimum_samples_per_scale"]),
        "reference_eligibility": dict(measurement["reference_eligibility"]),
        "invalidity_tolerances": dict(measurement["invalidity_tolerances"]),
        "spectral_analysis": dict(measurement["spectral_analysis"]),
    }


def _endpoint_family_map(config: Mapping[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family, endpoints in config["measurement"]["endpoint_families"].items():
        for endpoint in endpoints:
            endpoint = str(endpoint)
            if endpoint in mapping:
                raise ValueError(f"Endpoint {endpoint!r} appears in multiple families.")
            mapping[endpoint] = str(family)
    included = {str(value) for value in config["measurement"]["included_endpoints"]}
    if included != set(mapping):
        raise ValueError("Every included FMD endpoint must belong to exactly one family.")
    return mapping


def _verify_source(data_root: Path, config: Mapping[str, Any]) -> tuple[Path, Path]:
    source = config["source"]
    archive = data_root / str(source["archive_name"])
    extracted = data_root / "extracted" / "test_mix"
    if not archive.is_file():
        raise FileNotFoundError(f"FMD archive not found: {archive}")
    if archive.stat().st_size != int(source["archive_bytes"]):
        raise ValueError("FMD archive byte count differs from the prospective lock.")
    if sha256_file(archive) != str(source["archive_sha256"]):
        raise ValueError("FMD archive SHA-256 differs from the prospective lock.")
    if not extracted.is_dir():
        raise FileNotFoundError(f"Extracted FMD test_mix directory not found: {extracted}")
    return archive, extracted


def index_fmd_split(
    data_root: Path,
    config: Mapping[str, Any],
    *,
    split: str,
) -> list[FMDPairRecord]:
    if split not in {"development", "confirmation"}:
        raise ValueError("FMD split must be development or confirmation.")
    _, extracted = _verify_source(data_root, config)
    selected_groups = {
        str(value) for value in config["selection"][f"{split}_groups"]
    }
    captures = {str(key): int(value) for key, value in config["source"]["acquisition_levels"].items()}
    if set(captures) != set(LEVELS):
        raise ValueError("FMD acquisition levels differ from the frozen adapter contract.")
    references: dict[tuple[str, int], Path] = {}
    for path in sorted((extracted / "gt").glob("*.png")):
        match = FILENAME.match(path.name)
        if match and match.group("group") in selected_groups:
            references[(match.group("group"), int(match.group("realization")))] = path
    expected_reference_count = len(selected_groups) * int(
        config["selection"]["expected_noise_realizations_per_group_level"]
    )
    if len(references) != expected_reference_count:
        raise ValueError(
            f"FMD {split} reference count is {len(references)}, expected {expected_reference_count}."
        )
    reference_hashes = {key: sha256_file(path) for key, path in references.items()}
    records: list[FMDPairRecord] = []
    for level in LEVELS:
        folder = extracted / level
        for path in sorted(folder.glob("*.png")):
            match = FILENAME.match(path.name)
            if not match or match.group("group") not in selected_groups:
                continue
            group = match.group("group")
            realization = int(match.group("realization"))
            key = (group, realization)
            reference = references.get(key)
            if reference is None:
                raise ValueError(
                    f"No FMD reference found for {group}, realization {realization}."
                )
            records.append(
                FMDPairRecord(
                    pair_id=f"{group}|r{realization}|{level}",
                    reference_group_id=group,
                    acquisition_modality=match.group("modality"),
                    sample=match.group("sample"),
                    noise_realization=realization,
                    acquisition_level=level,
                    averaged_captures=captures[level],
                    input_path=path.relative_to(data_root).as_posix(),
                    reference_path=reference.relative_to(data_root).as_posix(),
                    input_sha256=sha256_file(path),
                    reference_sha256=reference_hashes[key],
                )
            )
    expected_pairs = int(config["selection"]["expected_pairs_per_split"])
    if len(records) != expected_pairs:
        raise ValueError(f"FMD {split} pair count is {len(records)}, expected {expected_pairs}.")
    observed_groups = {record.reference_group_id for record in records}
    if observed_groups != selected_groups:
        raise ValueError("FMD indexed group set differs from the prospective split.")
    records.sort(key=lambda record: record.pair_id)
    return records


def _read_grayscale(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        image = np.asarray(opened.convert("L"), dtype=np.float64)
    if image.ndim != 2 or image.shape != (512, 512):
        raise ValueError(f"FMD image {path.name} is not a 512 x 512 scalar image.")
    if not np.isfinite(image).all():
        raise ValueError(f"FMD image {path.name} contains non-finite values.")
    return image


def measure_selected_organization(
    image: np.ndarray,
    *,
    scales_px: Sequence[float],
    spectral_band_cycles_per_mm: tuple[float, float],
) -> dict[str, Any]:
    """Compute only the dimensionless endpoints declared by the FMD protocol.

    Compatibility placeholders let the frozen paired-row constructor run while
    avoiding unused Hessian and variogram computation. Placeholder endpoints are
    discarded before evidence rows are written.
    """

    data = _robust_unit(image)
    scales = tuple(float(value) for value in scales_px)
    tensor = structure_tensor_response(
        data,
        spacing_um=(1.0, 1.0),
        scales_um=scales,
    )
    fft = extract_spatial_fft(
        data,
        pixel_size_um=1.0,
        frequency_band_cycles_per_mm=spectral_band_cycles_per_mm,
    )
    middle = len(scales) // 2
    placeholder_curve = [0.5 if index != middle else 1.0 for index in range(len(scales))]
    placeholder_variogram = np.linspace(0.0, 1.0, len(scales)).tolist()
    return {
        "shape": list(data.shape),
        "grid_spacing_um": 1.0,
        "scales_um": list(scales),
        "qc": acquisition_qc(data),
        "tensor_orientation": list(tensor.orientation_degrees),
        "tensor_coherence": list(tensor.coherency),
        "tensor_orientation_resultant": list(tensor.orientation_resultant),
        "spectral_orientation": float(fft.orientation_degrees),
        "spectral_anisotropy": float(fft.anisotropy),
        "spectral_entropy": float(fft.angular_entropy),
        "spectral_scale": float(1000.0 / fft.characteristic_frequency_cycles_per_mm),
        "spectral_band_cycles_per_mm": [
            float(fft.analysis_min_frequency_cycles_per_mm),
            float(fft.analysis_max_frequency_cycles_per_mm),
        ],
        "hessian_blob_curve": placeholder_curve,
        "hessian_tube_curve": placeholder_curve,
        "hessian_blob_energy": 1.0,
        "hessian_tube_energy": 1.0,
        "hessian_blob_scale": scales[middle],
        "hessian_tube_scale": scales[middle],
        "variogram_separations_um": list(scales),
        "variogram_horizontal_curve": placeholder_variogram,
        "variogram_vertical_curve": placeholder_variogram,
        "variogram_horizontal_energy": 1.0,
        "variogram_vertical_energy": 1.0,
        "variogram_range_horizontal": scales[middle],
        "variogram_range_vertical": scales[middle],
    }


def measure_selected_with_mild_probes(
    image: np.ndarray,
    *,
    scales_px: Sequence[float],
    spectral_band_cycles_per_mm: tuple[float, float],
) -> tuple[dict[str, Any], list[tuple[str, float, dict[str, Any]]]]:
    base = measure_selected_organization(
        image,
        scales_px=scales_px,
        spectral_band_cycles_per_mm=spectral_band_cycles_per_mm,
    )
    probes = [
        (
            name,
            magnitude,
            measure_selected_organization(
                candidate,
                scales_px=scales_px,
                spectral_band_cycles_per_mm=spectral_band_cycles_per_mm,
            ),
        )
        for name, magnitude, candidate in _probe_images(
            image,
            grid_spacing_um=1.0,
            effective_spacing_um=1.0,
        )
    ]
    return base, probes


def _convert_dimensionless_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    split: str,
) -> list[dict[str, Any]]:
    family_map = _endpoint_family_map(config)
    converted: list[dict[str, Any]] = []
    for source in rows:
        endpoint = str(source["endpoint"])
        if endpoint not in family_map:
            continue
        row = dict(source)
        scale = row.pop("requested_scale_um", None)
        row.pop("development_partition", None)
        row["profile_partition"] = split
        row["endpoint_family"] = family_map[endpoint]
        row["calibration_status"] = "pixel_relative_only"
        row["requested_scale_value"] = scale
        row["requested_scale_unit"] = "px" if scale is not None else None
        row["physical_unit_output_eligible"] = False
        components = dict(row["support_components"])
        components["scale_sampling"] = components.pop("physical_sampling")
        components["samples_per_declared_scale"] = components.pop("samples_per_scale")
        row["support_components"] = components
        scores = dict(row["scores"])
        scores["scale_sampling_only"] = scores.pop("physical_sampling_only")
        row["scores"] = scores
        metadata = dict(row["metadata"])
        metadata["calibration_contract"] = (
            "No pixel spacing supplied by FMD test_mix; only dimensionless endpoints are eligible."
        )
        metadata["internal_scale_parameterization"] = (
            "Numeric pixel scales passed through the scale-equivariant estimator; physical outputs excluded."
        )
        row["metadata"] = metadata
        attach_declared_capture_stability_score(row, config=config)
        converted.append(row)
    return converted


def attach_declared_capture_stability_score(
    row: dict[str, Any],
    *,
    config: Mapping[str, Any],
) -> None:
    """Attach the v1.2 physics-informed score using acquisition inputs only."""

    specification = config["measurement"].get("input_only_score")
    if specification is None:
        return
    if specification.get("formula") != (
        "capture_weight * max(0, sqrt(target_averaged_captures / averaged_captures) - 1) "
        "+ perturbation_weight * perturbation_stability"
    ):
        raise ValueError("Unsupported FMD input-only score formula.")
    metadata = row.get("metadata", {})
    components = row.get("support_components", {})
    captures = float(metadata["averaged_captures"])
    target = float(specification["target_averaged_captures"])
    if captures <= 0 or target <= 0:
        raise ValueError("Declared FMD capture counts must be positive.")
    capture_deficit = max(0.0, math.sqrt(target / captures) - 1.0)
    perturbation = float(components["perturbation_stability"])
    score = (
        float(specification["capture_weight"]) * capture_deficit
        + float(specification["perturbation_weight"]) * perturbation
    )
    score_key = str(specification["score_key"])
    components["declared_capture_noise_deficit"] = float(capture_deficit)
    row["support_components"] = components
    row["scores"][score_key] = float(score)
    row["metadata"]["declared_capture_stability_score"] = {
        "score_key": score_key,
        "averaged_captures": int(captures),
        "target_averaged_captures": int(target),
        "capture_noise_deficit": float(capture_deficit),
        "perturbation_stability": perturbation,
        "score": float(score),
    }


def _verify_confirmation_profile(
    profile_path: Path | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if profile_path is None:
        raise ValueError("Confirmation decoding requires a frozen development profile.")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    verify_profile(profile)
    if profile["config_sha256"] != canonical_sha256(config):
        raise ValueError("Confirmation profile was compiled from a different protocol config.")
    expected = sorted(str(value) for value in config["selection"]["development_groups"])
    if sorted(profile["development"]["independent_groups"]) != expected:
        raise ValueError("Confirmation profile development groups differ from the prospective split.")
    return profile


def _verify_confirmation_lock(
    lock_path: Path | None,
    *,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if lock_path is None:
        raise ValueError("Confirmation decoding requires an executable confirmation lock.")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") not in {
        "nostos-fmd-validity-profile-confirmation-lock/1.0",
        "nostos-fmd-validity-profile-confirmation-lock/1.1",
    }:
        raise ValueError("Unsupported FMD confirmation lock schema.")
    if lock.get("confirmation_status_at_lock") != "images_not_decoded_for_measurement_analysis":
        raise ValueError("Confirmation lock does not attest an untouched confirmation split.")
    if str(lock.get("protocol_id")) != str(config["protocol_id"]):
        raise ValueError("Confirmation lock protocol differs from the supplied config.")
    expected_groups = sorted(str(value) for value in config["selection"]["confirmation_groups"])
    if sorted(str(value) for value in lock["confirmation_groups"]) != expected_groups:
        raise ValueError("Confirmation lock group set differs from the supplied config.")
    project_root = Path(__file__).resolve().parents[3]
    for artifact in lock["artifacts"]:
        path = project_root / str(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Locked confirmation artifact is missing: {path}")
        if sha256_file(path) != str(artifact["sha256"]):
            raise ValueError(f"Locked confirmation artifact hash mismatch: {artifact['path']}")
    return lock


def build_fmd_evidence_rows(
    data_root: Path,
    config_path: Path,
    output_directory: Path,
    *,
    split: str,
    profile_path: Path | None = None,
    confirmation_lock_path: Path | None = None,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") not in {
        "nostos-fmd-validity-profile/1.1",
        "nostos-fmd-validity-profile/1.2",
    }:
        raise ValueError("Unsupported FMD validity-profile configuration.")
    profile = (
        _verify_confirmation_profile(profile_path, config)
        if split == "confirmation"
        else None
    )
    confirmation_lock = (
        _verify_confirmation_lock(confirmation_lock_path, config=config)
        if split == "confirmation"
        else None
    )
    records = index_fmd_split(data_root, config, split=split)
    output_directory.mkdir(parents=True, exist_ok=True)
    index_path = output_directory / f"{split}_pair_index.json"
    index_payload = {
        "schema_version": "nostos-fmd-pair-index/1.0",
        "adapter_version": FMD_ADAPTER_VERSION,
        "protocol_id": config["protocol_id"],
        "split": split,
        "archive_sha256": config["source"]["archive_sha256"],
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "index_created_before_image_decode": True,
        "records": [asdict(record) for record in records],
    }
    index_payload["content_sha256"] = canonical_sha256(index_payload)
    write_json(index_path, index_payload)

    internal_config = _internal_measurement_config(config)
    scales = tuple(float(value) for value in config["measurement"]["analysis_scales_px"])
    spectral_band = shared_spectral_band_cycles_per_mm(internal_config, 1.0)
    reference_cache: dict[
        str, tuple[np.ndarray, dict[str, Any], list[tuple[str, float, dict[str, Any]]]]
    ] = {}
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for record in records:
        reference_key = record.reference_sha256
        if reference_key not in reference_cache:
            reference_image = _read_grayscale(data_root / Path(record.reference_path))
            reference_base, reference_probes = measure_selected_with_mild_probes(
                reference_image,
                scales_px=scales,
                spectral_band_cycles_per_mm=spectral_band,
            )
            reference_cache[reference_key] = (
                reference_image,
                reference_base,
                reference_probes,
            )
        reference_image, reference_base, reference_probes = reference_cache[reference_key]
        input_image = _read_grayscale(data_root / Path(record.input_path))
        registration = audit_pair_registration(
            input_image,
            reference_image,
            reference_spacing_um=1.0,
            effective_input_spacing_um=1.0,
        )
        input_base, input_probes = measure_selected_with_mild_probes(
            input_image,
            scales_px=scales,
            spectral_band_cycles_per_mm=spectral_band,
        )
        pair_rows = evaluate_precomputed_pair(
            pair_id=record.pair_id,
            reference_group_id=record.reference_group_id,
            structure=record.sample,
            effective_input_spacing_um=1.0,
            registration=registration,
            input_base=input_base,
            input_probes=input_probes,
            reference_base=reference_base,
            reference_probes=reference_probes,
            config=internal_config,
            metadata={
                "dataset": "FMD",
                "acquisition_modality": record.acquisition_modality,
                "sample": record.sample,
                "noise_realization": record.noise_realization,
                "acquisition_level": record.acquisition_level,
                "averaged_captures": record.averaged_captures,
                "input_sha256": record.input_sha256,
                "reference_sha256": record.reference_sha256,
            },
        )
        rows.extend(
            _convert_dimensionless_rows(pair_rows, config=config, split=split)
        )
    rows.sort(key=lambda row: str(row["case_id"]))
    elapsed = time.perf_counter() - started
    rows_path = output_directory / f"{split}_rows.jsonl"
    write_jsonl(rows_path, rows)
    eligible = [
        row
        for row in rows
        if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])
    ]
    invalid_by_family = Counter(
        str(row["endpoint_family"]) for row in eligible if bool(row["invalid"])
    )
    eligible_by_family = Counter(str(row["endpoint_family"]) for row in eligible)
    receipt: dict[str, Any] = {
        "schema_version": "nostos-fmd-evidence-build/1.0",
        "adapter_version": FMD_ADAPTER_VERSION,
        "status": "evidence_rows_complete",
        "protocol_id": config["protocol_id"],
        "split": split,
        "claim_boundary": config["scope"],
        "calibration_status": "pixel_relative_only",
        "physical_unit_output_eligible": False,
        "independent_groups": sorted({record.reference_group_id for record in records}),
        "independent_group_count": len({record.reference_group_id for record in records}),
        "paired_acquisitions": len(records),
        "unique_reference_images_decoded": len(reference_cache),
        "endpoint_rows": len(rows),
        "eligible_endpoint_rows": len(eligible),
        "eligible_by_family": dict(sorted(eligible_by_family.items())),
        "invalid_by_family": dict(sorted(invalid_by_family.items())),
        "elapsed_seconds": float(elapsed),
        "source": {
            "archive_sha256": config["source"]["archive_sha256"],
            "config_file_sha256": sha256_file(config_path),
            "pair_index_sha256": sha256_file(index_path),
            "rows_sha256": sha256_file(rows_path),
        },
        "confirmation_profile": (
            None
            if profile is None
            else {
                "content_sha256": profile["content_sha256"],
                "file_sha256": sha256_file(profile_path),
            }
        ),
        "confirmation_lock": (
            None
            if confirmation_lock is None
            else {
                "schema_version": confirmation_lock["schema_version"],
                "file_sha256": sha256_file(confirmation_lock_path),
            }
        ),
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    receipt_path = output_directory / f"{split}_evidence_receipt.json"
    write_json(receipt_path, receipt)
    return {
        "status": receipt["status"],
        "split": split,
        "rows": str(rows_path),
        "rows_sha256": receipt["source"]["rows_sha256"],
        "pair_index": str(index_path),
        "receipt": str(receipt_path),
        "independent_groups": receipt["independent_group_count"],
        "paired_acquisitions": len(records),
        "endpoint_rows": len(rows),
        "eligible_endpoint_rows": len(eligible),
        "elapsed_seconds": elapsed,
    }
