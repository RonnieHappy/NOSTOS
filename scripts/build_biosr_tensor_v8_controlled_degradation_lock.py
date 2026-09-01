"""Freeze the outcome-blind BioSR v8 controlled-degradation pilot."""

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
CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v8_controlled_degradation_pilot.locked.json"
)
V7_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
V71_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
V71_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_1_nonlinear_lock.json"
TRANSFER_AUDIT = (
    ROOT
    / "outputs/nostos0-biosr-tensor-v7-mixed-lock-combined-audit/combined_confirmation_audit.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "manifests/paired_acquisition_tensor_v8_controlled_degradation_pilot_lock.json"
)
SOURCES = {
    "F-actin_linear": {
        "archive": Path(
            r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin.zip"
        ),
        "config": V7_CONFIG,
        "archive_receipt": lambda v7, _v71: v7["archives"]["F-actin_linear"],
    },
    "F-actin_nonlinear": {
        "archive": Path(
            r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin_Nonlinear.zip"
        ),
        "config": V71_CONFIG,
        "archive_receipt": lambda _v7, v71: v71["archive"],
    },
}
IMPLEMENTATION_FILES = (
    ROOT / "scripts/run_biosr_tensor_v8_controlled_degradation_pilot.py",
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

    challenge = json.loads(CONFIG.read_text(encoding="utf-8"))
    v7_lock = json.loads(V7_LOCK.read_text(encoding="utf-8"))
    v71_lock = json.loads(V71_LOCK.read_text(encoding="utf-8"))
    transfer = json.loads(TRANSFER_AUDIT.read_text(encoding="utf-8"))
    lineage = challenge["source_lineage"]
    expected_lineage = {
        V7_CONFIG: lineage["v7_linear_config_sha256"],
        V7_LOCK: lineage["v7_linear_lock_sha256"],
        V71_CONFIG: lineage["v7_1_nonlinear_config_sha256"],
        V71_LOCK: lineage["v7_1_nonlinear_lock_sha256"],
        TRANSFER_AUDIT: lineage["mixed_lock_transfer_audit_sha256"],
    }
    for path, expected in expected_lineage.items():
        if sha256_file(path) != expected:
            raise RuntimeError(f"Source lineage differs: {path}")
    _verify_locked_files(v7_lock, name="v7")
    _verify_locked_files(v71_lock, name="v7.1")
    if transfer["decision"]["measurement_transfer_gate"] != "PASS":
        raise RuntimeError("The prerequisite acquisition-family transfer gate failed.")

    selected_by_structure: dict[str, list[str]] = {}
    archive_receipts: dict[str, dict[str, Any]] = {}
    header_pair_counts: dict[str, int] = {}
    selected_pair_counts: dict[str, int] = {}
    for structure, source in SOURCES.items():
        source_config = json.loads(Path(source["config"]).read_text(encoding="utf-8"))
        specification = source_config["structures"][structure]
        archive = Path(source["archive"])
        inherited = dict(source["archive_receipt"](v7_lock, v71_lock))
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
        prior = set(v7_lock["confirmation"]["selected_cells"][structure])
        eligible = [cell for cell in layout["cells"] if cell not in prior]
        selected = select_confirmation_cells_v7(
            eligible,
            structure=structure,
            count=int(challenge["selection"]["fields_per_structure"]),
            salt=str(challenge["selection"]["selection_salt"]),
        )
        if selected != challenge["selection"]["selected_cells"][structure]:
            raise RuntimeError(f"Frozen v8 selection mismatch for {structure}.")
        if prior.intersection(selected):
            raise RuntimeError(f"v8 selection overlaps v7 confirmation for {structure}.")
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
        selected_levels = set(challenge["selection"]["signal_levels"][structure])
        kept = [
            record
            for record in records
            if record.cell_id in set(selected)
            and record.signal_level in selected_levels
        ]
        expected_pairs = len(selected) * len(selected_levels)
        if len(kept) != expected_pairs:
            raise RuntimeError(f"Selected header pair count mismatch for {structure}.")
        selected_by_structure[structure] = selected
        header_pair_counts[structure] = len(records)
        selected_pair_counts[structure] = len(kept)
        archive_receipts[structure] = {
            **inherited,
            "verified_sha256_before_v8_lock": observed_sha256,
            "header_index_pairs": len(records),
        }

    if sum(selected_pair_counts.values()) != int(
        challenge["selection"]["base_paired_acquisitions"]
    ):
        raise RuntimeError("Total selected pair count differs from the v8 config.")
    implementation = _implementation_receipt()
    supporting = (
        CONFIG,
        V7_CONFIG,
        V71_CONFIG,
        V7_LOCK,
        V71_LOCK,
        TRANSFER_AUDIT,
        ROOT / "docs/NOSTOS0_BIOSR_V8_CONTROLLED_DEGRADATION_PILOT.md",
        ROOT / "tests/test_controlled_degradation_v8.py",
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
            "nostos-paired-acquisition-tensor-v8-controlled-degradation-pilot-lock/1.0"
        ),
        "locked_at_utc": _utc_now(),
        "status": "locked_before_selected_field_pixel_decode_or_endpoint_outcome",
        "protocol_version": challenge["protocol_version"],
        "config": _artifact(CONFIG),
        "implementation_sha256": implementation["sha256"],
        "selected_cells": selected_by_structure,
        "selected_signal_levels": challenge["selection"]["signal_levels"],
        "degradations": challenge["degradations"],
        "archives": archive_receipts,
        "header_pair_counts": header_pair_counts,
        "selected_pair_counts": selected_pair_counts,
        "source_lineage": {
            "v7_config_sha256": sha256_file(V7_CONFIG),
            "v7_lock_sha256": sha256_file(V7_LOCK),
            "v7_1_config_sha256": sha256_file(V71_CONFIG),
            "v7_1_lock_sha256": sha256_file(V71_LOCK),
            "mixed_lock_transfer_audit_sha256": sha256_file(TRANSFER_AUDIT),
        },
        "access_state": {
            "central_directory_read": True,
            "mrc_headers_read": True,
            "selected_cell_pixel_arrays_decoded_by_v8": 0,
            "selected_cell_endpoint_outcomes_computed_by_v8": 0,
            "authorized_after_lock": (
                "Decode only the six selected cells, two frozen signal levels "
                "per cell and fourteen frozen degradations."
            ),
        },
        "files": [unique[key] for key in sorted(unique)],
        "verification": {
            "focused_pytest_command": (
                ".venv/Scripts/python.exe -m pytest -q "
                "tests/test_controlled_degradation_v8.py "
                "tests/test_biosr_tensor_v7_1_amendment.py "
                "tests/test_biosr_tensor_confirmation_v7.py "
                "tests/test_tensor_support_v7.py tests/test_tensor_evidence_v7.py"
            ),
            "focused_pytest_result": "16 passed in 0.85s",
            "compile_command": (
                ".venv/Scripts/python.exe -m compileall -q src scripts tests"
            ),
            "compile_exit_code": 0,
        },
        "claim_boundary": challenge["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_artifact(args.output), indent=2))


if __name__ == "__main__":
    main()
