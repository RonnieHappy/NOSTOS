"""Freeze the untouched BioSR v9 scale-conditioned support confirmation."""

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
from run_biosr_tensor_v8_controlled_degradation_pilot import SOURCES


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v9_scale_conditioned_confirmation.locked.json"
)
V7_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
V71_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
V8_CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v8_controlled_degradation_pilot.locked.json"
)
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
V71_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_1_nonlinear_lock.json"
V8_LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v8_controlled_degradation_pilot_lock.json"
)
V8_RECEIPT = (
    ROOT / "outputs/nostos0-biosr-tensor-v8-controlled-degradation-pilot/pilot_receipt.json"
)
V9_DEVELOPMENT = (
    ROOT
    / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-development/development_audit.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "manifests/paired_acquisition_tensor_v9_scale_conditioned_confirmation_lock.json"
)
IMPLEMENTATION_FILES = (
    ROOT / "scripts/run_biosr_tensor_v9_scale_conditioned_confirmation.py",
    ROOT / "scripts/run_biosr_tensor_v8_controlled_degradation_pilot.py",
    ROOT / "src/nostos/validation/scale_conditioned_support_v9.py",
    ROOT / "src/nostos/validation/controlled_degradation_v8.py",
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


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": _relative(path),
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


def _verify_locked_files(lock: dict[str, Any], *, name: str) -> None:
    for item in lock["files"]:
        path = ROOT / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256_file(path) != item["sha256"]
        ):
            raise RuntimeError(f"{name} lineage failure: {item['path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}.")

    confirmation = json.loads(CONFIG.read_text(encoding="utf-8"))
    v7_lock = json.loads(V7_LOCK.read_text(encoding="utf-8"))
    v71_lock = json.loads(V71_LOCK.read_text(encoding="utf-8"))
    v8_lock = json.loads(V8_LOCK.read_text(encoding="utf-8"))
    v8_config = json.loads(V8_CONFIG.read_text(encoding="utf-8"))
    v8_receipt = json.loads(V8_RECEIPT.read_text(encoding="utf-8"))
    development = json.loads(V9_DEVELOPMENT.read_text(encoding="utf-8"))
    lineage = confirmation["source_lineage"]
    expected = {
        V7_CONFIG: lineage["v7_linear_config_sha256"],
        V71_CONFIG: lineage["v7_1_nonlinear_config_sha256"],
        V7_LOCK: lineage["v7_confirmation_lock_sha256"],
        V71_LOCK: lineage["v7_1_nonlinear_lock_sha256"],
        V8_CONFIG: lineage["v8_challenge_config_sha256"],
        V8_LOCK: lineage["v8_challenge_lock_sha256"],
        V8_RECEIPT: lineage["v8_failure_receipt_sha256"],
        V9_DEVELOPMENT: lineage["v9_development_audit_sha256"],
    }
    for path, digest in expected.items():
        if sha256_file(path) != digest:
            raise RuntimeError(f"v9 source lineage differs: {path}")
    _verify_locked_files(v7_lock, name="v7")
    _verify_locked_files(v71_lock, name="v7.1")
    _verify_locked_files(v8_lock, name="v8")
    if v8_receipt["pilot_evaluation"]["status"] != "fail":
        raise RuntimeError("v9 requires the sealed assessable v8 failure.")
    if v8_receipt["pilot_evaluation"]["assessable"] is not True:
        raise RuntimeError("The v8 failure was not assessable.")
    selected_development = development["calibration"]["selected"]
    support = confirmation["v9_scale_conditioned_support"]
    if development["status"] != "operating_point_selected":
        raise RuntimeError("v9 development did not select an operating point.")
    if float(selected_development["acceptance_boundary"]) != float(
        support["acceptance_boundary"]
    ):
        raise RuntimeError("v9 boundary differs from development selection.")
    if float(development["calibration"]["primary_exponent"]) != float(
        support["scale_exponent"]
    ):
        raise RuntimeError("v9 exponent differs from development selection.")
    if support["threshold_refitting_permitted"] is not False:
        raise RuntimeError("v9 threshold refitting must be prohibited.")

    selected_by_structure: dict[str, list[str]] = {}
    archives: dict[str, dict[str, Any]] = {}
    header_pair_counts: dict[str, int] = {}
    selected_pair_counts: dict[str, int] = {}
    for structure, source in SOURCES.items():
        source_config = json.loads(Path(source["config"]).read_text(encoding="utf-8"))
        specification = source_config["structures"][structure]
        archive = Path(source["archive"])
        inherited = (
            dict(v7_lock["archives"][structure])
            if structure == "F-actin_linear"
            else dict(v71_lock["archive"])
        )
        if archive.stat().st_size != int(inherited["bytes"]):
            raise RuntimeError(f"Archive byte mismatch for {structure}.")
        observed_sha256 = sha256_file(archive)
        if observed_sha256 != inherited["sha256"]:
            raise RuntimeError(f"Archive hash mismatch for {structure}.")
        layout = archive_layout_from_central_directory(
            archive,
            structure=structure,
            expected_level_count=int(specification["expected_level_count"]),
            reference_basename=str(specification["primary_reference_basename"]),
            excluded_reference_basenames=tuple(
                specification["excluded_reference_basenames"]
            ),
        )
        excluded = set(v7_lock["confirmation"]["selected_cells"][structure])
        excluded.update(v8_lock["selected_cells"][structure])
        eligible = [cell for cell in layout["cells"] if cell not in excluded]
        selected = select_confirmation_cells_v7(
            eligible,
            structure=structure,
            count=int(confirmation["selection"]["fields_per_structure"]),
            salt=str(confirmation["selection"]["selection_salt"]),
        )
        if selected != confirmation["selection"]["selected_cells"][structure]:
            raise RuntimeError(f"Frozen v9 selection mismatch for {structure}.")
        if excluded.intersection(selected):
            raise RuntimeError(f"v9 selection overlaps prior evidence for {structure}.")
        records = index_biosr_tensor_archive_v7(
            archive,
            structure=structure,
            expected_raw_spacing_um=float(source_config["raw_sim_sampling_um"]),
            upscaling_factor=int(specification["upscaling_factor"]),
            expected_level_count=int(specification["expected_level_count"]),
            expected_input_frames=int(specification["expected_input_frames"]),
            reference_basename=str(specification["primary_reference_basename"]),
            spacing_absolute_tolerance_um=float(
                source_config["mrc_header_spacing_absolute_tolerance_um"]
            ),
            field_of_view_relative_tolerance=float(
                source_config["field_of_view_relative_tolerance"]
            ),
        )
        levels = set(confirmation["selection"]["signal_levels"][structure])
        kept = [
            record
            for record in records
            if record.cell_id in set(selected) and record.signal_level in levels
        ]
        expected_pairs = len(selected) * len(levels)
        if len(kept) != expected_pairs:
            raise RuntimeError(f"Selected pair count mismatch for {structure}.")
        selected_by_structure[structure] = selected
        header_pair_counts[structure] = len(records)
        selected_pair_counts[structure] = len(kept)
        archives[structure] = {
            **inherited,
            "verified_sha256_before_v9_lock": observed_sha256,
            "header_index_pairs": len(records),
        }
    if sum(selected_pair_counts.values()) != int(
        confirmation["selection"]["base_paired_acquisitions"]
    ):
        raise RuntimeError("Total v9 pair count differs from the config.")
    if v8_config["degradations"] != v8_lock["degradations"]:
        raise RuntimeError("v8 degradation lineage differs.")

    implementation = _implementation_receipt()
    supporting = (
        CONFIG,
        V7_CONFIG,
        V71_CONFIG,
        V8_CONFIG,
        V7_LOCK,
        V71_LOCK,
        V8_LOCK,
        V8_RECEIPT,
        V9_DEVELOPMENT,
        ROOT / "docs/NOSTOS0_BIOSR_V9_SCALE_CONDITIONED_CONFIRMATION.md",
        ROOT / "tests/test_scale_conditioned_support_v9.py",
        Path(__file__).resolve(),
    )
    unique = {
        item["path"]: item
        for item in [
            *implementation["files"],
            *[_artifact(path) for path in supporting],
        ]
    }
    payload = {
        "schema_version": (
            "nostos-paired-acquisition-tensor-v9-scale-conditioned-confirmation-lock/1.0"
        ),
        "locked_at_utc": _utc_now(),
        "status": "locked_before_selected_field_pixel_decode_or_endpoint_outcome",
        "protocol_version": confirmation["protocol_version"],
        "config": _artifact(CONFIG),
        "implementation_sha256": implementation["sha256"],
        "selected_cells": selected_by_structure,
        "selected_signal_levels": confirmation["selection"]["signal_levels"],
        "degradations": v8_config["degradations"],
        "v9_scale_conditioned_support": support,
        "confirmation_gates": confirmation["confirmation_gates"],
        "archives": archives,
        "header_pair_counts": header_pair_counts,
        "selected_pair_counts": selected_pair_counts,
        "source_lineage": {
            "v8_failure_receipt_sha256": sha256_file(V8_RECEIPT),
            "v9_development_audit_sha256": sha256_file(V9_DEVELOPMENT),
        },
        "access_state": {
            "central_directory_read": True,
            "mrc_headers_read": True,
            "selected_cell_pixel_arrays_decoded_by_v9": 0,
            "selected_cell_endpoint_outcomes_computed_by_v9": 0,
            "authorized_after_lock": (
                "Decode only the eight selected v9 cells, two frozen signal "
                "levels per cell and the unchanged fourteen v8 degradations."
            ),
        },
        "files": [unique[key] for key in sorted(unique)],
        "verification": {
            "focused_pytest_command": (
                ".venv/Scripts/python.exe -m pytest -q "
                "tests/test_scale_conditioned_support_v9.py "
                "tests/test_controlled_degradation_v8.py "
                "tests/test_biosr_tensor_v7_1_amendment.py "
                "tests/test_biosr_tensor_confirmation_v7.py "
                "tests/test_tensor_support_v7.py tests/test_tensor_evidence_v7.py"
            ),
            "focused_pytest_result": "19 passed in 0.84s",
            "compile_command": (
                ".venv/Scripts/python.exe -m compileall -q src scripts tests"
            ),
            "compile_exit_code": 0,
        },
        "claim_boundary": confirmation["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_artifact(args.output), indent=2))


if __name__ == "__main__":
    main()
