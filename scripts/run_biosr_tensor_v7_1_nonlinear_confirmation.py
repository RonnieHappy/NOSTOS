"""Run the metadata-amended, locked BioSR nonlinear F-actin confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import (
    archive_layout_from_central_directory,
    evaluate_v7_confirmation,
    index_biosr_tensor_archive_v7,
    select_confirmation_cells_v7,
)
from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    sha256_file,
)

# The scientific computation is imported unchanged from the v7 runner.  The
# v7.1 amendment changes only nonlinear physical spacing and receipt paths.
from run_biosr_tensor_v7_confirmation import _process_cell


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = (
    "nostos-paired-acquisition-tensor/7.1-nonlinear-metadata-amendment"
)
DEFAULT_CONFIG = (
    ROOT / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
)
LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_1_nonlinear_lock.json"
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
DEFAULT_OUTPUT = (
    ROOT / "outputs/nostos0-biosr-tensor-v7-1-f-actin-nonlinear-confirmation"
)
IMPLEMENTATION_FILES = (
    Path(__file__).resolve(),
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


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _implementation_receipt() -> dict[str, Any]:
    files = [
        {
            "path": str(path.resolve().relative_to(ROOT.resolve())).replace(
                "\\", "/"
            ),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in IMPLEMENTATION_FILES
    ]
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "files": files}


def _verify_lock() -> dict[str, Any]:
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    for item in payload["files"]:
        target = ROOT / item["path"]
        if (
            not target.is_file()
            or target.stat().st_size != int(item["bytes"])
            or sha256_file(target) != item["sha256"]
        ):
            raise RuntimeError(f"Locked v7.1 file changed: {item['path']}")
    implementation = _implementation_receipt()
    if implementation["sha256"] != payload["implementation_sha256"]:
        raise RuntimeError("v7.1 implementation differs from its lock.")
    return payload


def _read_checkpoint(
    path: Path,
    *,
    archive_sha256: str,
    config_sha256: str,
    implementation_sha256: str,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("archive_sha256") != archive_sha256
        or payload.get("config_sha256") != config_sha256
        or payload.get("implementation_sha256") != implementation_sha256
    ):
        return None
    return payload


def run(
    *,
    archive: Path,
    config_path: Path,
    output: Path,
    workers: int,
) -> dict[str, Any]:
    lock = _verify_lock()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("Config and v7.1 runner protocol versions disagree.")
    structure = "F-actin_nonlinear"
    specification = config["structures"][structure]
    if archive.name != specification["archive_name"]:
        raise ValueError("Archive basename differs from the v7.1 configuration.")
    config_sha = sha256_file(config_path)
    if config_sha != lock["config"]["sha256"]:
        raise RuntimeError("Configuration differs from the v7.1 lock.")
    if archive.stat().st_size != int(specification["archive_bytes"]):
        raise RuntimeError("Archive byte count differs from frozen metadata.")
    observed_md5 = _md5(archive)
    if observed_md5.lower() != str(specification["archive_md5"]).lower():
        raise RuntimeError("Archive MD5 differs from frozen metadata.")
    archive_sha = sha256_file(archive)
    implementation = _implementation_receipt()

    layout = archive_layout_from_central_directory(
        archive,
        structure=structure,
        expected_level_count=int(specification["expected_level_count"]),
        reference_basename=str(specification["primary_reference_basename"]),
        excluded_reference_basenames=tuple(
            specification["excluded_reference_basenames"]
        ),
    )
    selected_by_hash = select_confirmation_cells_v7(
        layout["cells"],
        structure=structure,
        count=int(config["confirmation"]["fields_per_structure"]),
        salt=str(config["confirmation"]["selection_salt"]),
    )
    selected = list(config["confirmation"]["selected_cells"])
    if selected != selected_by_hash or selected != lock["selected_cells"]:
        raise RuntimeError("Carried-forward v7 selection is not exact.")

    records = index_biosr_tensor_archive_v7(
        archive,
        structure=structure,
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
    by_cell: dict[str, list[BioSRPairRecord]] = defaultdict(list)
    for record in records:
        by_cell[record.cell_id].append(record)
    if sorted(by_cell) != layout["cells"]:
        raise RuntimeError("Header index and central-directory cell sets differ.")

    output.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = output / "cell_checkpoints"
    checkpoints_dir.mkdir(exist_ok=True)
    pair_index = {
        "schema_version": "nostos-biosr-tensor-v7-1-nonlinear-pair-index/1.0",
        "selection_status": "carried_forward_from_v7_before_any_nonlinear_pixel_decode",
        "selection_rule": config["confirmation"]["field_selection_rule"],
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_md5": observed_md5,
        "archive_sha256": archive_sha,
        "structure": structure,
        "raw_sim_sampling_um": config["raw_sim_sampling_um"],
        "upscaling_factor": specification["upscaling_factor"],
        "expected_level_count": specification["expected_level_count"],
        "expected_input_frames": specification["expected_input_frames"],
        "primary_reference_basename": specification[
            "primary_reference_basename"
        ],
        "excluded_reference_basenames": specification[
            "excluded_reference_basenames"
        ],
        "selected_cells": selected,
        "available_cells": layout["cells"],
        "records": [
            asdict(record) for record in records if record.cell_id in selected
        ],
    }
    pair_index_path = output / "pair_index.json"
    pair_index_path.write_text(
        json.dumps(pair_index, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    all_rows: list[dict[str, Any]] = []
    pending = []
    checkpoint_receipts = []
    for cell in selected:
        checkpoint = checkpoints_dir / f"{cell}.json"
        payload = _read_checkpoint(
            checkpoint,
            archive_sha256=archive_sha,
            config_sha256=config_sha,
            implementation_sha256=implementation["sha256"],
        )
        if payload is None:
            pending.append(cell)
        else:
            all_rows.extend(payload["rows"])
            checkpoint_receipts.append(
                {
                    key: payload[key]
                    for key in ("cell_id", "rows_count", "elapsed_seconds")
                }
            )
    if pending:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_cell,
                    str(archive),
                    [asdict(record) for record in by_cell[cell]],
                    config,
                ): cell
                for cell in pending
            }
            for future in as_completed(futures):
                result = future.result()
                cell = str(result["cell_id"])
                for row in result["rows"]:
                    row["metadata"]["confirmation_selection"] = (
                        "v7_hash_selection_carried_unchanged_into_locked_v7_1_metadata_amendment"
                    )
                    row["metadata"]["calibration_amendment"] = (
                        "nonlinear MRC header spacing 0.0604 um"
                    )
                payload = {
                    "protocol_version": PROTOCOL_VERSION,
                    "archive_sha256": archive_sha,
                    "config_sha256": config_sha,
                    "implementation_sha256": implementation["sha256"],
                    "cell_id": cell,
                    "reference_group_id": result["reference_group_id"],
                    "records": result["records"],
                    "rows_count": len(result["rows"]),
                    "elapsed_seconds": result["elapsed_seconds"],
                    "rows": result["rows"],
                }
                checkpoint = checkpoints_dir / f"{cell}.json"
                checkpoint.write_text(
                    json.dumps(payload, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                all_rows.extend(result["rows"])
                checkpoint_receipts.append(
                    {
                        key: payload[key]
                        for key in ("cell_id", "rows_count", "elapsed_seconds")
                    }
                )
                print(
                    f"completed {structure} {cell}: {payload['rows_count']} rows "
                    f"in {payload['elapsed_seconds']:.1f} s",
                    flush=True,
                )
    all_rows.sort(key=lambda row: str(row["case_id"]))
    rows_path = output / "tensor_cases.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    rules = {
        **config["confirmation"]["primary_safety_rules"],
        **config["confirmation"][
            "separate_incremental_coherence_utility_rules"
        ],
    }
    evaluation = evaluate_v7_confirmation(all_rows, rules=rules)
    receipt = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "complete_v7_1_nonlinear_confirmation_archive",
        "analysis_role": "locked_untouched_nonlinear_confirmation_after_metadata_only_spacing_amendment",
        "structure": structure,
        "selection": {
            "selected_cells": selected,
            "available_cells": len(by_cell),
            "selected_reference_fields": len(selected),
            "outcome_or_pixel_dependent": False,
        },
        "calibration": {
            "raw_sim_sampling_um": config["raw_sim_sampling_um"],
            "reference_sampling_um": config["raw_sim_sampling_um"]
            / specification["upscaling_factor"],
            "authority": config["calibration_authority"],
        },
        "reference_policy": {
            "primary_reference_basename": specification[
                "primary_reference_basename"
            ],
            "excluded_reference_basenames": specification[
                "excluded_reference_basenames"
            ],
        },
        "archive": lock["archive"],
        "config": lock["config"],
        "implementation": implementation,
        "v7_1_lock_sha256": sha256_file(LOCK),
        "v7_lock_sha256": sha256_file(V7_LOCK),
        "workers": workers,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
        },
        "checkpoints": sorted(
            checkpoint_receipts, key=lambda item: item["cell_id"]
        ),
        "rows": len(all_rows),
        "pairs": len({str(row["pair_id"]) for row in all_rows}),
        "provisional_single_archive_evaluation": evaluation,
        "combined_with_v7_linear_gate_required": True,
        "artifacts": {
            "pair_index": {
                "path": str(pair_index_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
                "bytes": pair_index_path.stat().st_size,
                "sha256": sha256_file(pair_index_path),
            },
            "tensor_cases": {
                "path": str(rows_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
                "bytes": rows_path.stat().st_size,
                "sha256": sha256_file(rows_path),
            },
        },
        "claim_boundary": config["claim_boundary"],
    }
    receipt_path = output / "archive_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path(
            r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin_Nonlinear.zip"
        ),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--workers", type=int, default=max(1, min(2, os.cpu_count() or 1))
    )
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive.")
    result = run(
        archive=args.archive,
        config_path=args.config,
        output=args.output,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "selection": result["selection"],
                "rows": result["rows"],
                "pairs": result["pairs"],
                "evaluation": result[
                    "provisional_single_archive_evaluation"
                ]["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

