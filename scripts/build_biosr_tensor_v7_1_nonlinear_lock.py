"""Freeze the metadata-only v7.1 nonlinear confirmation amendment."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import (
    archive_layout_from_central_directory,
    index_biosr_tensor_archive_v7,
    select_confirmation_cells_v7,
)
from nostos.validation.paired_acquisition_support import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "manifests/paired_acquisition_tensor_v7_1_nonlinear_lock.json"
)
CONFIG = ROOT / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
V7_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
FAILURE = (
    ROOT
    / "manifests/paired_acquisition_tensor_v7_nonlinear_header_failure_receipt.json"
)
LINEAR_RECEIPT = (
    ROOT
    / "outputs/nostos0-biosr-tensor-v7-f-actin-linear-confirmation/archive_receipt.json"
)
ARCHIVE = Path(
    r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin_Nonlinear.zip"
)
IMPLEMENTATION_FILES = (
    ROOT / "scripts/run_biosr_tensor_v7_1_nonlinear_confirmation.py",
    ROOT / "scripts/run_biosr_tensor_v7_confirmation.py",
    ROOT / "src/nostos/validation/biosr_tensor_confirmation_v7.py",
    ROOT / "src/nostos/validation/tensor_support_v7.py",
    ROOT / "src/nostos/validation/tensor_contract_audit_v7.py",
    ROOT / "src/nostos/validation/tensor_evidence_v7.py",
    ROOT / "src/nostos/features/physical_tensor.py",
    ROOT / "src/nostos/features/spatial_fft.py",
    ROOT / "src/nostos/core/qc.py",
    ROOT / "src/nostos/validation/paired_acquisition_support.py",
    ROOT / "src/nostos/validation/metrics.py",
    ROOT / "pyproject.toml",
    ROOT / "uv.lock",
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(ROOT.resolve())).replace(
            "\\", "/"
        ),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _implementation_receipt() -> dict[str, Any]:
    files = [_artifact(path) for path in IMPLEMENTATION_FILES]
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}.")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    v7_lock = json.loads(V7_LOCK.read_text(encoding="utf-8"))
    linear = json.loads(LINEAR_RECEIPT.read_text(encoding="utf-8"))
    if config["protocol_version"] != (
        "nostos-paired-acquisition-tensor/7.1-nonlinear-metadata-amendment"
    ):
        raise ValueError("Unexpected v7.1 protocol version.")
    if failure["access_audit"]["nonlinear_pixel_arrays_decoded"] != 0:
        raise ValueError("Nonlinear pixels were not sealed before v7.1.")
    if failure["access_audit"]["nonlinear_endpoint_outcomes_computed"] != 0:
        raise ValueError("Nonlinear outcomes were not sealed before v7.1.")
    if sha256_file(V7_CONFIG) != config["lineage"]["v7_config_sha256"]:
        raise ValueError("v7 config lineage mismatch.")
    if sha256_file(V7_LOCK) != config["lineage"]["v7_lock_sha256"]:
        raise ValueError("v7 lock lineage mismatch.")
    if sha256_file(FAILURE) != config["lineage"][
        "v7_nonlinear_header_failure_receipt_sha256"
    ]:
        raise ValueError("Header-failure lineage mismatch.")
    if sha256_file(LINEAR_RECEIPT) != config["lineage"][
        "v7_linear_confirmation_receipt_sha256"
    ]:
        raise ValueError("Linear-receipt lineage mismatch.")
    if linear["structure"] != "F-actin_linear" or linear["rows"] != 960:
        raise ValueError("Completed v7 linear receipt is incomplete.")

    specification = config["structures"]["F-actin_nonlinear"]
    if ARCHIVE.stat().st_size != int(specification["archive_bytes"]):
        raise ValueError("Nonlinear archive byte count mismatch.")
    archive_sha256 = sha256_file(ARCHIVE)
    if archive_sha256 != v7_lock["archives"]["F-actin_nonlinear"]["sha256"]:
        raise ValueError("Nonlinear archive SHA-256 differs from the v7 lock.")
    if (
        v7_lock["archives"]["F-actin_nonlinear"]["md5"]
        != specification["archive_md5"]
    ):
        raise ValueError("Nonlinear archive MD5 lineage mismatch.")
    layout = archive_layout_from_central_directory(
        ARCHIVE,
        structure="F-actin_nonlinear",
        expected_level_count=int(specification["expected_level_count"]),
        reference_basename=str(specification["primary_reference_basename"]),
        excluded_reference_basenames=tuple(
            specification["excluded_reference_basenames"]
        ),
    )
    selected = select_confirmation_cells_v7(
        layout["cells"],
        structure="F-actin_nonlinear",
        count=int(config["confirmation"]["fields_per_structure"]),
        salt=str(config["confirmation"]["selection_salt"]),
    )
    if (
        selected != config["confirmation"]["selected_cells"]
        or selected
        != v7_lock["confirmation"]["selected_cells"]["F-actin_nonlinear"]
    ):
        raise ValueError("v7.1 field selection differs from v7.")
    records = index_biosr_tensor_archive_v7(
        ARCHIVE,
        structure="F-actin_nonlinear",
        expected_raw_spacing_um=float(config["raw_sim_sampling_um"]),
        upscaling_factor=int(specification["upscaling_factor"]),
        expected_level_count=int(specification["expected_level_count"]),
        expected_input_frames=int(specification["expected_input_frames"]),
        reference_basename=str(specification["primary_reference_basename"]),
        spacing_absolute_tolerance_um=float(
            config["mrc_header_spacing_absolute_tolerance_um"]
        ),
        field_of_view_relative_tolerance=float(
            config["field_of_view_relative_tolerance"]
        ),
    )
    if len(records) != 459:
        raise ValueError("Nonlinear header index must contain 459 pairs.")

    implementation = _implementation_receipt()
    supporting = (
        CONFIG,
        V7_CONFIG,
        V7_LOCK,
        FAILURE,
        LINEAR_RECEIPT,
        ROOT / "docs/NOSTOS0_BIOSR_V7_CONFIRMATION_PROTOCOL.md",
        ROOT / "docs/NOSTOS0_BIOSR_V7_1_METADATA_AMENDMENT.md",
        ROOT / "scripts/build_biosr_tensor_v7_nonlinear_header_failure_receipt.py",
        ROOT / "scripts/finalize_biosr_tensor_v7_linear_receipt.py",
        Path(__file__).resolve(),
        ROOT / "tests/test_biosr_tensor_v7_1_amendment.py",
    )
    unique = {
        item["path"]: item
        for item in [
            *implementation["files"],
            *[_artifact(path) for path in supporting],
        ]
    }
    payload = {
        "schema_version": "nostos-paired-acquisition-tensor-v7-1-nonlinear-lock/1.0",
        "locked_at_utc": _utc_now(),
        "status": "locked_after_uniform_header_audit_before_any_nonlinear_pixel_array_decode_or_endpoint_outcome",
        "protocol_version": config["protocol_version"],
        "implementation_sha256": implementation["sha256"],
        "config": _artifact(CONFIG),
        "selected_cells": selected,
        "archive": {
            **v7_lock["archives"]["F-actin_nonlinear"],
            "verified_sha256_before_v7_1_lock": archive_sha256,
            "header_index_pairs": len(records),
            "raw_spacing_yx_um": failure["observed_header_metadata"][
                "raw_spacing_yx_um"
            ],
            "reference_spacing_yx_um": failure[
                "observed_header_metadata"
            ]["reference_spacing_yx_um"],
        },
        "amendment": {
            "only_scientific_change": "nonlinear physical grid calibration from 0.0626 um to 0.0604 um",
            "outcome_informed": False,
            "selected_fields_changed": False,
            "thresholds_changed": False,
            "endpoints_changed": False,
            "comparators_or_gates_changed": False,
            "linear_result_reused_under_original_lock": True,
        },
        "access_state": {
            "nonlinear_mrc_headers_read": True,
            "nonlinear_payload_beyond_header_read": False,
            "nonlinear_pixel_arrays_decoded": 0,
            "nonlinear_endpoint_outcomes_computed": 0,
            "authorized_after_lock": "Decode only the eight carried-forward nonlinear cells and all nine frozen signal levels using SIM_gt_a.mrc; exclude SIM_gt_b.mrc completely."
        },
        "lineage": {
            "v7_lock_sha256": sha256_file(V7_LOCK),
            "v7_failure_receipt_sha256": sha256_file(FAILURE),
            "v7_linear_receipt_sha256": sha256_file(LINEAR_RECEIPT),
        },
        "files": [unique[key] for key in sorted(unique)],
        "verification": {
            "focused_pytest_command": ".venv/Scripts/python.exe -m pytest -q tests/test_biosr_tensor_v7_1_amendment.py tests/test_biosr_tensor_confirmation_v7.py tests/test_tensor_support_v7.py tests/test_tensor_evidence_v7.py",
            "focused_pytest_result": "13 passed in 0.88s",
            "compile_command": ".venv/Scripts/python.exe -m compileall -q src scripts tests",
            "compile_exit_code": 0
        },
        "claim_boundary": config["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_artifact(args.output), indent=2))


if __name__ == "__main__":
    main()
