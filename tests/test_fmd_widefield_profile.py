from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from nostos.validation.fmd_widefield_profile import (
    build_fmd_widefield_evidence_rows,
    index_widefield_split,
)


def _write_member(opened: tarfile.TarFile, name: str, payload: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    opened.addfile(member, io.BytesIO(payload))


def _fixture(tmp_path: Path) -> tuple[Path, dict]:
    archive = tmp_path / "WideField_BPAE_R.tar"
    with tarfile.open(archive, "w") as opened:
        for field in (7, 15, 16, 17):
            _write_member(
                opened,
                f"WideField_BPAE_R/gt/{field}/avg50.png",
                f"reference-{field}".encode(),
            )
            for level in ("raw", "avg2", "avg4", "avg8", "avg16"):
                _write_member(
                    opened,
                    (
                        f"WideField_BPAE_R/{level}/{field}/"
                        f"synthetic-prefix-{field:03d}0003.png"
                    ),
                    f"input-{field}-{level}-3".encode(),
                )
    payload = archive.read_bytes()
    config = {
        "schema_version": "nostos-fmd-widefield-validity-profile/1.0",
        "protocol_id": "fixture",
        "source": {
            "archive_name": archive.name,
            "archive_bytes": len(payload),
            "archive_md5": hashlib.md5(payload).hexdigest(),  # noqa: S324
            "archive_sha256": hashlib.sha256(payload).hexdigest(),
            "acquisition_modality": "WideField",
            "sample": "BPAE_R",
            "acquisition_levels": {
                "raw": 1,
                "avg2": 2,
                "avg4": 4,
                "avg8": 8,
                "avg16": 16,
            },
            "image_shape_yx_px": [512, 512],
        },
        "selection": {
            "development_fields": [7, 15],
            "confirmation_fields": [16, 17],
            "realization_indices": {
                "7": [3],
                "15": [3],
                "16": [3],
                "17": [3],
            },
            "expected_fields_per_split": 2,
            "expected_realizations_per_field_level": 1,
            "expected_pairs_per_split": 10,
        },
    }
    return archive, config


def test_tar_index_is_frozen_member_exact_and_pixel_decode_free(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)
    records, identity = index_widefield_split(tmp_path, config, split="development")
    assert len(records) == 10
    assert {record.field_of_view for record in records} == {7, 15}
    assert {record.noise_realization for record in records} == {3}
    assert all(record.input_sha256 for record in records)
    assert all(record.reference_sha256 for record in records)
    assert identity["sha256"] == config["source"]["archive_sha256"]


def test_confirmation_refuses_to_index_without_frozen_profile(tmp_path: Path) -> None:
    _, config = _fixture(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen development profile"):
        build_fmd_widefield_evidence_rows(
            tmp_path,
            config_path,
            tmp_path / "output",
            split="confirmation",
        )
