"""Seal the v7 nonlinear spacing mismatch before any nonlinear pixel decode."""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from nostos.validation.paired_acquisition_support import (
    _mrc_header_from_bytes,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
ARCHIVE = Path(
    r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin_Nonlinear.zip"
)
FAILED_OUTPUT = (
    ROOT / "outputs/nostos0-biosr-tensor-v7-f-actin-nonlinear-confirmation"
)
OUTPUT = (
    ROOT
    / "manifests/paired_acquisition_tensor_v7_nonlinear_header_failure_receipt.json"
)


def _summary(values: list[Any]) -> list[Any]:
    return sorted({tuple(value) if isinstance(value, tuple) else value for value in values})


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}.")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    for item in lock["files"]:
        target = ROOT / item["path"]
        if (
            not target.is_file()
            or target.stat().st_size != int(item["bytes"])
            or sha256_file(target) != item["sha256"]
        ):
            raise RuntimeError(f"Locked v7 file changed: {item['path']}")
    if FAILED_OUTPUT.exists() and any(FAILED_OUTPUT.rglob("*")):
        raise RuntimeError(
            "Nonlinear v7 output artifacts exist; zero-pixel failure cannot be certified."
        )

    input_pattern = re.compile(
        r"^[^/]+/(?P<cell>Cell_\d+)/RawSIMData_level_(?P<level>\d{2})\.mrc$",
        re.I,
    )
    reference_pattern = re.compile(
        r"^[^/]+/(?P<cell>Cell_\d+)/SIM_gt_a\.mrc$", re.I
    )
    raw_spacing = []
    reference_spacing = []
    raw_shapes = []
    reference_shapes = []
    raw_frames = []
    levels: dict[str, set[int]] = defaultdict(set)
    references = set()
    with zipfile.ZipFile(ARCHIVE) as opened:
        for info in opened.infolist():
            match = input_pattern.match(info.filename)
            if match:
                with opened.open(info, "r") as stream:
                    header = _mrc_header_from_bytes(stream.read(1024))
                raw_spacing.append(header.spacing_yx_um)
                raw_shapes.append((header.ny, header.nx))
                raw_frames.append(header.nz)
                levels[match.group("cell")].add(int(match.group("level")))
                continue
            match = reference_pattern.match(info.filename)
            if match:
                with opened.open(info, "r") as stream:
                    header = _mrc_header_from_bytes(stream.read(1024))
                reference_spacing.append(header.spacing_yx_um)
                reference_shapes.append((header.ny, header.nx))
                references.add(match.group("cell"))

    raw_unique = _summary(raw_spacing)
    reference_unique = _summary(reference_spacing)
    raw_shape_unique = _summary(raw_shapes)
    reference_shape_unique = _summary(reference_shapes)
    frame_unique = _summary(raw_frames)
    if not (
        len(raw_unique) == 1
        and len(reference_unique) == 1
        and raw_shape_unique == [(502, 502)]
        and reference_shape_unique == [(1506, 1506)]
        and frame_unique == [25]
        and len(levels) == 51
        and set(levels) == references
        and all(value == set(range(1, 10)) for value in levels.values())
    ):
        raise RuntimeError("Nonlinear header layout is not uniform.")
    raw_value = np.asarray(raw_unique[0], dtype=float)
    reference_value = np.asarray(reference_unique[0], dtype=float)
    if not np.allclose(raw_value / reference_value, 3.0, rtol=0, atol=1e-6):
        raise RuntimeError("Nonlinear raw/reference header spacing ratio is not 3x.")
    if not np.allclose(
        raw_value * 502, reference_value * 1506, rtol=1e-7, atol=0
    ):
        raise RuntimeError("Nonlinear raw/reference header fields of view disagree.")
    frozen_expected = float(config["raw_sim_sampling_um"])
    if np.allclose(raw_value, frozen_expected, rtol=0, atol=1e-6):
        raise RuntimeError("The frozen and observed nonlinear spacing do not differ.")

    payload = {
        "schema_version": "nostos-biosr-tensor-v7-nonlinear-header-failure/1.0",
        "status": "v7_nonlinear_stopped_before_pixel_decode_due_to_frozen_spacing_mismatch",
        "protocol_version": config["protocol_version"],
        "frozen_expected_raw_spacing_um": frozen_expected,
        "observed_header_metadata": {
            "cells": len(levels),
            "levels_per_cell": 9,
            "input_members": len(raw_spacing),
            "reference_members": len(reference_spacing),
            "raw_spacing_yx_um": raw_unique[0],
            "reference_spacing_yx_um": reference_unique[0],
            "raw_shape_yx": raw_shape_unique[0],
            "reference_shape_yx": reference_shape_unique[0],
            "raw_frames": frame_unique[0],
            "spacing_ratio_raw_to_reference": (
                raw_value / reference_value
            ).tolist(),
            "raw_field_of_view_yx_um": (raw_value * 502).tolist(),
            "reference_field_of_view_yx_um": (
                reference_value * 1506
            ).tolist(),
            "uniform_across_archive": True,
        },
        "source_discrepancy": {
            "official_imaging_conditions_workbook_raw_spacing_um": frozen_expected,
            "all_archive_mrc_headers_raw_spacing_um": float(raw_value[0]),
            "resolution_rule": "Use the internally consistent per-acquisition MRC header calibration for nonlinear SIM, disclose the conflict with the record-level workbook, and preserve 0.0626 um for the linear archive whose headers agree with the workbook.",
            "outcome_informed": False,
        },
        "access_audit": {
            "central_directory_inspected": True,
            "mrc_headers_read": True,
            "mrc_payload_beyond_1024_byte_header_read_by_auditor": False,
            "nonlinear_pixel_arrays_decoded": 0,
            "nonlinear_endpoint_outcomes_computed": 0,
            "failed_output_directory_present": FAILED_OUTPUT.exists(),
        },
        "decision": {
            "v7_nonlinear_status": "failed_precondition_do_not_execute",
            "v7_linear_status": "unaffected_and_retained_under_original_v7_lock",
            "permitted_next_action": "Create a metadata-only v7.1 nonlinear amendment and a new lock before decoding nonlinear pixels.",
            "threshold_or_endpoint_change_permitted": False,
            "selected_field_change_permitted": False,
        },
        "lineage": {
            "v7_config_sha256": sha256_file(CONFIG),
            "v7_lock_sha256": sha256_file(LOCK),
            "archive_sha256": lock["archives"]["F-actin_nonlinear"]["sha256"],
            "implementation_sha256": sha256_file(Path(__file__)),
        },
        "claim_boundary": "Metadata-only failure and repair evidence. No nonlinear measurement result exists under v7.",
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "path": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
                "bytes": OUTPUT.stat().st_size,
                "sha256": sha256_file(OUTPUT),
                "status": payload["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

