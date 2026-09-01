"""Hash-locked FMD widefield adapter for acquisition-specific profile validation.

The adapter indexes and hashes selected tar members before any image is decoded.
Development and confirmation fields are fixed by the supplied protocol.  A
confirmation run additionally requires a verified development profile and an
executable confirmation lock.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, Mapping, Sequence

import numpy as np
from PIL import Image

from nostos.validation.fmd_validity_profile import (
    _convert_dimensionless_rows,
    _internal_measurement_config,
    measure_selected_with_mild_probes,
)
from nostos.validation.paired_acquisition_support import (
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


FMD_WIDEFIELD_ADAPTER_VERSION = "nostos-fmd-widefield-profile-adapter/1.0"
LEVELS = ("raw", "avg2", "avg4", "avg8", "avg16")
REALIZATION_SUFFIX = re.compile(r"(?P<index>\d{4})\.png$", re.IGNORECASE)


@dataclass(frozen=True)
class WidefieldPairRecord:
    pair_id: str
    reference_group_id: str
    acquisition_modality: str
    sample: str
    field_of_view: int
    noise_realization: int
    acquisition_level: str
    averaged_captures: int
    input_member: str
    reference_member: str
    input_bytes: int
    reference_bytes: int
    input_sha256: str
    reference_sha256: str


def _hash_stream(stream: BinaryIO) -> tuple[str, str, int]:
    md5 = hashlib.md5()  # noqa: S324 - required to verify the repository checksum.
    sha256 = hashlib.sha256()
    total = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        md5.update(chunk)
        sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest(), total


def verify_widefield_archive(
    data_root: Path, config: Mapping[str, Any]
) -> tuple[Path, dict[str, Any]]:
    source = config["source"]
    archive = data_root / str(source["archive_name"])
    if not archive.is_file():
        raise FileNotFoundError(f"FMD widefield archive not found: {archive}")
    with archive.open("rb") as stream:
        observed_md5, observed_sha256, observed_bytes = _hash_stream(stream)
    if observed_bytes != int(source["archive_bytes"]):
        raise ValueError("FMD widefield archive byte count differs from the frozen protocol.")
    if observed_md5 != str(source["archive_md5"]).lower():
        raise ValueError("FMD widefield archive MD5 differs from the repository checksum.")
    if observed_sha256 != str(source["archive_sha256"]).lower():
        raise ValueError("FMD widefield archive SHA-256 differs from the frozen protocol.")
    return archive, {
        "bytes": observed_bytes,
        "md5": observed_md5,
        "sha256": observed_sha256,
    }


def _member_bytes(opened: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    stream = opened.extractfile(member)
    if stream is None:
        raise ValueError(f"Tar member cannot be read: {member.name}")
    payload = stream.read()
    if len(payload) != int(member.size):
        raise ValueError(f"Tar member byte count changed while reading: {member.name}")
    return payload


def _selected_fields(config: Mapping[str, Any], split: str) -> list[int]:
    if split not in {"development", "confirmation"}:
        raise ValueError("FMD widefield split must be development or confirmation.")
    fields = [int(value) for value in config["selection"][f"{split}_fields"]]
    expected = int(config["selection"]["expected_fields_per_split"])
    if len(fields) != expected or len(set(fields)) != expected:
        raise ValueError(f"FMD widefield {split} field selection is not complete and unique.")
    return fields


def _validate_member_tree(
    members: Mapping[str, tarfile.TarInfo],
    *,
    config: Mapping[str, Any],
    split: str,
) -> list[tuple[int, int, str, tarfile.TarInfo, tarfile.TarInfo]]:
    source = config["source"]
    root = f"{source['acquisition_modality']}_{source['sample']}"
    fields = _selected_fields(config, split)
    captures = {str(key): int(value) for key, value in source["acquisition_levels"].items()}
    if set(captures) != set(LEVELS):
        raise ValueError("FMD widefield acquisition levels differ from the adapter contract.")
    selected: list[tuple[int, int, str, tarfile.TarInfo, tarfile.TarInfo]] = []
    for field in fields:
        reference_name = f"{root}/gt/{field}/avg50.png"
        reference = members.get(reference_name)
        if reference is None or not reference.isfile():
            raise ValueError(f"Frozen FMD reference member is missing: {reference_name}")
        realization_indices = [
            int(value) for value in config["selection"]["realization_indices"][str(field)]
        ]
        expected_realizations = int(
            config["selection"]["expected_realizations_per_field_level"]
        )
        if (
            len(realization_indices) != expected_realizations
            or len(set(realization_indices)) != expected_realizations
        ):
            raise ValueError(f"Frozen realization selection is malformed for FOV {field}.")
        for level in LEVELS:
            prefix = f"{root}/{level}/{field}/"
            by_realization: dict[int, tarfile.TarInfo] = {}
            for name, member in members.items():
                if not member.isfile() or not name.startswith(prefix):
                    continue
                match = REALIZATION_SUFFIX.search(name)
                if match is None:
                    continue
                realization = int(match.group("index"))
                if realization in by_realization:
                    raise ValueError(
                        f"Duplicate FMD realization {realization} under {prefix}."
                    )
                by_realization[realization] = member
            for realization in realization_indices:
                input_member = by_realization.get(realization)
                if input_member is None:
                    raise ValueError(
                        f"Frozen FMD input is missing: FOV {field}, {level}, realization {realization}."
                    )
                selected.append((field, realization, level, input_member, reference))
    expected_pairs = int(config["selection"]["expected_pairs_per_split"])
    if len(selected) != expected_pairs:
        raise ValueError(
            f"FMD widefield {split} pair count is {len(selected)}, expected {expected_pairs}."
        )
    return selected


def index_widefield_split(
    data_root: Path,
    config: Mapping[str, Any],
    *,
    split: str,
) -> tuple[list[WidefieldPairRecord], dict[str, Any]]:
    """Verify the archive and hash only frozen members without decoding pixels."""

    archive, archive_identity = verify_widefield_archive(data_root, config)
    with tarfile.open(archive, mode="r:") as opened:
        members = {member.name: member for member in opened.getmembers()}
        selected = _validate_member_tree(members, config=config, split=split)
        payload_cache: dict[str, tuple[int, str]] = {}
        for _, _, _, input_member, reference_member in selected:
            for member in (input_member, reference_member):
                if member.name in payload_cache:
                    continue
                payload = _member_bytes(opened, member)
                payload_cache[member.name] = (
                    len(payload),
                    hashlib.sha256(payload).hexdigest(),
                )

    source = config["source"]
    root = f"{source['acquisition_modality']}_{source['sample']}"
    captures = {str(key): int(value) for key, value in source["acquisition_levels"].items()}
    records: list[WidefieldPairRecord] = []
    for field, realization, level, input_member, reference_member in selected:
        input_bytes, input_sha256 = payload_cache[input_member.name]
        reference_bytes, reference_sha256 = payload_cache[reference_member.name]
        records.append(
            WidefieldPairRecord(
                pair_id=f"{root}|fov{field}|r{realization:02d}|{level}",
                reference_group_id=f"{root}|fov{field}",
                acquisition_modality=str(source["acquisition_modality"]),
                sample=str(source["sample"]),
                field_of_view=field,
                noise_realization=realization,
                acquisition_level=level,
                averaged_captures=captures[level],
                input_member=input_member.name,
                reference_member=reference_member.name,
                input_bytes=input_bytes,
                reference_bytes=reference_bytes,
                input_sha256=input_sha256,
                reference_sha256=reference_sha256,
            )
        )
    records.sort(key=lambda record: record.pair_id)
    return records, archive_identity


def _read_grayscale_member(
    opened: tarfile.TarFile,
    member_name: str,
    *,
    expected_sha256: str,
    expected_shape: Sequence[int],
) -> np.ndarray:
    member = opened.getmember(member_name)
    payload = _member_bytes(opened, member)
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError(f"Selected member changed after the pre-decode index: {member_name}")
    with Image.open(io.BytesIO(payload)) as image:
        array = np.asarray(image.convert("L"), dtype=np.float64)
    shape = tuple(int(value) for value in expected_shape)
    if array.ndim != 2 or array.shape != shape:
        raise ValueError(
            f"FMD image {member_name} has shape {array.shape}, expected {shape}."
        )
    if not np.isfinite(array).all():
        raise ValueError(f"FMD image {member_name} contains non-finite values.")
    return array


def _verify_confirmation_profile(
    profile_path: Path | None,
    *,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if profile_path is None:
        raise ValueError("Confirmation decoding requires a frozen development profile.")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    verify_profile(profile)
    if profile["config_sha256"] != canonical_sha256(config):
        raise ValueError("Confirmation profile was compiled from a different protocol config.")
    expected_groups = sorted(
        f"{config['source']['acquisition_modality']}_{config['source']['sample']}|fov{field}"
        for field in _selected_fields(config, "development")
    )
    if sorted(profile["development"]["independent_groups"]) != expected_groups:
        raise ValueError("Profile development fields differ from the prospective protocol.")
    support = profile.get("acquisition_stratum_support")
    modality = str(config["source"]["acquisition_modality"])
    if support is None or modality not in support["supported_strata"]:
        raise ValueError("The frozen acquisition modality is not supported by the profile.")
    return profile


def _verify_confirmation_lock(
    lock_path: Path | None,
    *,
    config: Mapping[str, Any],
    profile: Mapping[str, Any],
    profile_path: Path,
) -> dict[str, Any]:
    if lock_path is None:
        raise ValueError("Confirmation decoding requires an executable confirmation lock.")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "nostos-fmd-widefield-confirmation-lock/1.0":
        raise ValueError("Unsupported FMD widefield confirmation-lock schema.")
    if lock.get("confirmation_status_at_lock") != "pixels_not_decoded_for_measurement_analysis":
        raise ValueError("Confirmation lock does not attest an untouched confirmation split.")
    expected_content = str(lock.get("content_sha256", ""))
    content = dict(lock)
    content.pop("content_sha256", None)
    if not expected_content or canonical_sha256(content) != expected_content:
        raise ValueError("FMD widefield confirmation-lock content hash mismatch.")
    if str(lock.get("protocol_id")) != str(config["protocol_id"]):
        raise ValueError("Confirmation lock protocol differs from the supplied config.")
    if lock.get("config_content_sha256") != canonical_sha256(config):
        raise ValueError("Confirmation lock config content hash differs from the supplied config.")
    if lock.get("profile_content_sha256") != profile["content_sha256"]:
        raise ValueError("Confirmation lock profile content hash differs from the supplied profile.")
    if lock.get("profile_file_sha256") != sha256_file(profile_path):
        raise ValueError("Confirmation lock profile file hash differs from the supplied profile.")
    if lock.get("archive_sha256") != config["source"]["archive_sha256"]:
        raise ValueError("Confirmation lock archive identity differs from the protocol.")
    if [int(value) for value in lock["confirmation_fields"]] != _selected_fields(
        config, "confirmation"
    ):
        raise ValueError("Confirmation lock field order differs from the protocol.")
    project_root = Path(__file__).resolve().parents[3]
    for artifact in lock["artifacts"]:
        path = project_root / str(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Locked confirmation artifact is missing: {path}")
        if sha256_file(path) != str(artifact["sha256"]):
            raise ValueError(f"Locked confirmation artifact hash mismatch: {artifact['path']}")
    return lock


def build_fmd_widefield_evidence_rows(
    data_root: Path,
    config_path: Path,
    output_directory: Path,
    *,
    split: str,
    profile_path: Path | None = None,
    confirmation_lock_path: Path | None = None,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "nostos-fmd-widefield-validity-profile/1.0":
        raise ValueError("Unsupported FMD widefield validity-profile configuration.")
    if split not in {"development", "confirmation"}:
        raise ValueError("FMD widefield split must be development or confirmation.")

    profile: dict[str, Any] | None = None
    confirmation_lock: dict[str, Any] | None = None
    if split == "confirmation":
        if profile_path is None:
            raise ValueError("Confirmation decoding requires a frozen development profile.")
        profile = _verify_confirmation_profile(profile_path, config=config)
        confirmation_lock = _verify_confirmation_lock(
            confirmation_lock_path,
            config=config,
            profile=profile,
            profile_path=profile_path,
        )

    records, archive_identity = index_widefield_split(
        data_root, config, split=split
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    index_path = output_directory / f"{split}_pair_index.json"
    index_payload: dict[str, Any] = {
        "schema_version": "nostos-fmd-widefield-pair-index/1.0",
        "adapter_version": FMD_WIDEFIELD_ADAPTER_VERSION,
        "protocol_id": config["protocol_id"],
        "split": split,
        "archive_identity": archive_identity,
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "index_created_before_image_decode": True,
        "selected_member_payloads_read_for_checksum_only_before_index": True,
        "records": [asdict(record) for record in records],
    }
    index_payload["content_sha256"] = canonical_sha256(index_payload)
    write_json(index_path, index_payload)

    internal_config = _internal_measurement_config(config)
    scales = tuple(float(value) for value in config["measurement"]["analysis_scales_px"])
    spectral_band = shared_spectral_band_cycles_per_mm(internal_config, 1.0)
    expected_shape = config["source"]["image_shape_yx_px"]
    reference_cache: dict[
        str, tuple[np.ndarray, dict[str, Any], list[tuple[str, float, dict[str, Any]]]]
    ] = {}
    rows: list[dict[str, Any]] = []
    archive_path = data_root / str(config["source"]["archive_name"])
    started = time.perf_counter()
    with tarfile.open(archive_path, mode="r:") as opened:
        for record in records:
            if record.reference_sha256 not in reference_cache:
                reference_image = _read_grayscale_member(
                    opened,
                    record.reference_member,
                    expected_sha256=record.reference_sha256,
                    expected_shape=expected_shape,
                )
                reference_base, reference_probes = measure_selected_with_mild_probes(
                    reference_image,
                    scales_px=scales,
                    spectral_band_cycles_per_mm=spectral_band,
                )
                reference_cache[record.reference_sha256] = (
                    reference_image,
                    reference_base,
                    reference_probes,
                )
            reference_image, reference_base, reference_probes = reference_cache[
                record.reference_sha256
            ]
            input_image = _read_grayscale_member(
                opened,
                record.input_member,
                expected_sha256=record.input_sha256,
                expected_shape=expected_shape,
            )
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
                    "field_of_view": record.field_of_view,
                    "noise_realization": record.noise_realization,
                    "acquisition_level": record.acquisition_level,
                    "averaged_captures": record.averaged_captures,
                    "input_member": record.input_member,
                    "reference_member": record.reference_member,
                    "input_sha256": record.input_sha256,
                    "reference_sha256": record.reference_sha256,
                },
            )
            rows.extend(_convert_dimensionless_rows(pair_rows, config=config, split=split))

    rows.sort(key=lambda row: str(row["case_id"]))
    elapsed = time.perf_counter() - started
    rows_path = output_directory / f"{split}_rows.jsonl"
    write_jsonl(rows_path, rows)
    eligible = [
        row
        for row in rows
        if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])
    ]
    eligible_by_family = Counter(str(row["endpoint_family"]) for row in eligible)
    invalid_by_family = Counter(
        str(row["endpoint_family"]) for row in eligible if bool(row["invalid"])
    )
    receipt: dict[str, Any] = {
        "schema_version": "nostos-fmd-widefield-evidence-build/1.0",
        "adapter_version": FMD_WIDEFIELD_ADAPTER_VERSION,
        "status": "evidence_rows_complete",
        "protocol_id": config["protocol_id"],
        "split": split,
        "claim_boundary": config["scope"],
        "calibration_status": "pixel_relative_only",
        "physical_unit_output_eligible": False,
        "independent_groups": sorted({record.reference_group_id for record in records}),
        "independent_group_count": len(
            {record.reference_group_id for record in records}
        ),
        "paired_acquisitions": len(records),
        "unique_reference_images_decoded": len(reference_cache),
        "endpoint_rows": len(rows),
        "eligible_endpoint_rows": len(eligible),
        "eligible_by_family": dict(sorted(eligible_by_family.items())),
        "invalid_by_family": dict(sorted(invalid_by_family.items())),
        "elapsed_seconds": float(elapsed),
        "source": {
            "archive_identity": archive_identity,
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
                "content_sha256": confirmation_lock["content_sha256"],
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
