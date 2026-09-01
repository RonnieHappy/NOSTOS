"""Run the locked BioSR v9 scale-conditioned support confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import (
    archive_layout_from_central_directory,
    index_biosr_tensor_archive_v7,
    select_confirmation_cells_v7,
)
from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    sha256_file,
)
from nostos.validation.scale_conditioned_support_v9 import (
    attach_v9_scale_conditioned_score,
    evaluate_v9_scale_conditioned_confirmation,
)
from run_biosr_tensor_v8_controlled_degradation_pilot import (
    SOURCES,
    _process_cell as _process_v8_cell,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = (
    "nostos-paired-acquisition-tensor/9.0-scale-conditioned-confirmation"
)
CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v9_scale_conditioned_confirmation.locked.json"
)
V8_CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v8_controlled_degradation_pilot.locked.json"
)
LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v9_scale_conditioned_confirmation_lock.json"
)
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
V8_LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v8_controlled_degradation_pilot_lock.json"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation"
)
IMPLEMENTATION_FILES = (
    Path(__file__).resolve(),
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


def _verify_lock() -> dict[str, Any]:
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    for item in payload["files"]:
        path = ROOT / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256_file(path) != item["sha256"]
        ):
            raise RuntimeError(f"v9 locked file differs: {item['path']}")
    implementation = _implementation_receipt()
    if implementation["sha256"] != payload["implementation_sha256"]:
        raise RuntimeError("v9 implementation differs from its lock.")
    if sha256_file(CONFIG) != payload["config"]["sha256"]:
        raise RuntimeError("v9 config differs from its lock.")
    for structure, source in SOURCES.items():
        archive = Path(source["archive"])
        expected = payload["archives"][structure]
        if archive.stat().st_size != int(expected["bytes"]):
            raise RuntimeError(f"Archive byte mismatch for {structure}.")
        if sha256_file(archive) != expected["sha256"]:
            raise RuntimeError(f"Archive hash mismatch for {structure}.")
    return payload


def _read_checkpoint(
    path: Path,
    *,
    lock_sha256: str,
    implementation_sha256: str,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("lock_sha256") != lock_sha256
        or payload.get("implementation_sha256") != implementation_sha256
    ):
        return None
    return payload


def _index_sources(
    confirmation: dict[str, Any], lock: dict[str, Any]
) -> tuple[list[BioSRPairRecord], dict[str, dict[str, Any]]]:
    v7_lock = json.loads(V7_LOCK.read_text(encoding="utf-8"))
    v8_lock = json.loads(V8_LOCK.read_text(encoding="utf-8"))
    all_records: list[BioSRPairRecord] = []
    configs: dict[str, dict[str, Any]] = {}
    for structure, source in SOURCES.items():
        source_config = json.loads(Path(source["config"]).read_text(encoding="utf-8"))
        configs[structure] = source_config
        specification = source_config["structures"][structure]
        archive = Path(source["archive"])
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
            raise RuntimeError(f"Config selection mismatch for {structure}.")
        if selected != lock["selected_cells"][structure]:
            raise RuntimeError(f"Lock selection mismatch for {structure}.")
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
        selected_set = set(selected)
        kept = [
            record
            for record in records
            if record.cell_id in selected_set and record.signal_level in levels
        ]
        expected = len(selected) * len(levels)
        if len(kept) != expected:
            raise RuntimeError(f"Expected {expected} selected pairs for {structure}.")
        all_records.extend(kept)
    return all_records, configs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive.")

    confirmation = json.loads(CONFIG.read_text(encoding="utf-8"))
    v8_challenge = json.loads(V8_CONFIG.read_text(encoding="utf-8"))
    if confirmation["protocol_version"] != PROTOCOL_VERSION:
        raise RuntimeError("Unexpected v9 protocol version.")
    lock = _verify_lock()
    implementation = _implementation_receipt()
    lock_sha256 = sha256_file(LOCK)
    records, source_configs = _index_sources(confirmation, lock)
    processing_config = deepcopy(v8_challenge)
    processing_config["selection"] = confirmation["selection"]
    processing_config["randomness"] = confirmation["randomness"]

    args.output.mkdir(parents=True, exist_ok=True)
    pair_index_path = args.output / "pair_index.json"
    pair_index_path.write_text(
        json.dumps(
            {
                "schema_version": "nostos-biosr-v9-pair-index/1.0",
                "selection_status": "locked_before_selected_cell_pixel_decode",
                "records": [asdict(record) for record in records],
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    grouped: dict[tuple[str, str], list[BioSRPairRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.structure, record.cell_id)].append(record)
    checkpoints = args.output / "cell_checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    pending: list[tuple[str, str, list[BioSRPairRecord]]] = []
    for (structure, cell), cell_records in sorted(grouped.items()):
        checkpoint_path = checkpoints / f"{structure}_{cell}.json"
        checkpoint = _read_checkpoint(
            checkpoint_path,
            lock_sha256=lock_sha256,
            implementation_sha256=implementation["sha256"],
        )
        if checkpoint is None:
            pending.append((structure, cell, cell_records))
        else:
            results.append(checkpoint["result"])
            print(f"reused {structure} {cell}: {len(checkpoint['result']['rows'])} rows")

    if pending:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    _process_v8_cell,
                    str(SOURCES[structure]["archive"]),
                    [asdict(record) for record in cell_records],
                    source_configs[structure],
                    processing_config,
                ): (structure, cell)
                for structure, cell, cell_records in pending
            }
            for future in as_completed(futures):
                structure, cell = futures[future]
                raw_result = future.result()
                support = confirmation["v9_scale_conditioned_support"]
                raw_result["rows"] = attach_v9_scale_conditioned_score(
                    raw_result["rows"],
                    minimum_samples_per_scale=float(
                        support["minimum_samples_per_scale"]
                    ),
                    exponent=float(support["scale_exponent"]),
                    acceptance_boundary=float(support["acceptance_boundary"]),
                )
                for row in raw_result["rows"]:
                    row["metadata"]["selection"] = (
                        "v9 hash-only selection before selected-cell pixel decode"
                    )
                    row["metadata"]["confirmation_role"] = (
                        "untouched_v9_scale_conditioned_confirmation"
                    )
                checkpoint_path = checkpoints / f"{structure}_{cell}.json"
                checkpoint_path.write_text(
                    json.dumps(
                        {
                            "lock_sha256": lock_sha256,
                            "implementation_sha256": implementation["sha256"],
                            "result": raw_result,
                        },
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                results.append(raw_result)
                print(
                    f"completed {structure} {cell}: {len(raw_result['rows'])} rows "
                    f"in {raw_result['elapsed_seconds']:.1f} s",
                    flush=True,
                )

    rows = [row for result in results for row in result["rows"]]
    expected_rows = (
        int(confirmation["selection"]["base_paired_acquisitions"])
        * len(v8_challenge["degradations"])
        * 5
        * 2
    )
    if len(rows) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} rows; observed {len(rows)}.")
    if len({str(row["case_id"]) for row in rows}) != len(rows):
        raise RuntimeError("Duplicate v9 case identifiers detected.")

    rows_path = args.output / "tensor_cases.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in sorted(rows, key=lambda item: str(item["case_id"])):
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    evaluation = evaluate_v9_scale_conditioned_confirmation(
        rows, gates=confirmation["confirmation_gates"]
    )
    receipt = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "complete_v9_scale_conditioned_confirmation",
        "confirmation_evaluation": evaluation,
        "selection": confirmation["selection"],
        "scale_conditioned_support": confirmation["v9_scale_conditioned_support"],
        "degradations": v8_challenge["degradations"],
        "rows": len(rows),
        "base_pairs": len(records),
        "transformed_pairs": len(records) * len(v8_challenge["degradations"]),
        "reference_fields": len(grouped),
        "lock": _artifact(LOCK),
        "config": _artifact(CONFIG),
        "implementation": implementation,
        "archives": lock["archives"],
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
            "workers": args.workers,
        },
        "checkpoints": [
            {
                "structure": result["structure"],
                "cell_id": result["cell_id"],
                "rows": len(result["rows"]),
                "elapsed_seconds": result["elapsed_seconds"],
            }
            for result in sorted(
                results, key=lambda item: (item["structure"], item["cell_id"])
            )
        ],
        "artifacts": {
            "pair_index": _artifact(pair_index_path),
            "tensor_cases": _artifact(rows_path),
        },
        "claim_boundary": confirmation["claim_boundary"],
    }
    receipt_path = args.output / "confirmation_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "receipt": _artifact(receipt_path),
                "status": evaluation["status"],
                "passes": evaluation["passes"],
                "assessable": evaluation["assessable"],
                "coverage": evaluation["full_contract"]["coverage"],
                "risk": evaluation["full_contract"]["risk"],
                "risk_upper95": evaluation["full_contract"][
                    "cluster_bootstrap_risk_upper95"
                ],
                "qc_risk": evaluation["conventional_acquisition_qc"]["risk"],
                "bootstrap_ci95": evaluation["risk_coverage_evidence"][
                    "bootstrap"
                ]["ci95"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
