"""Recover the completed locked v7 linear run after receipt-path serialization."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import evaluate_v7_confirmation
from nostos.validation.paired_acquisition_support import sha256_file


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/nostos0-biosr-tensor-v7-f-actin-linear-confirmation"
CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
IMPLEMENTATION_FILES = (
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    receipt_path = OUTPUT / "archive_receipt.json"
    if receipt_path.exists():
        raise FileExistsError(f"Refusing to overwrite {receipt_path}.")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    implementation = _implementation_receipt()
    if implementation["sha256"] != lock["implementation_sha256"]:
        raise RuntimeError("Current implementation no longer matches the v7 lock.")
    for item in lock["files"]:
        target = ROOT / item["path"]
        if (
            not target.is_file()
            or target.stat().st_size != int(item["bytes"])
            or sha256_file(target) != item["sha256"]
        ):
            raise RuntimeError(f"Locked file changed: {item['path']}")

    pair_index_path = OUTPUT / "pair_index.json"
    rows_path = OUTPUT / "tensor_cases.jsonl"
    pair_index = json.loads(pair_index_path.read_text(encoding="utf-8"))
    rows = _read_jsonl(rows_path)
    selected = lock["confirmation"]["selected_cells"]["F-actin_linear"]
    if pair_index["selected_cells"] != selected:
        raise RuntimeError("Linear pair-index selection differs from the v7 lock.")
    if len(rows) != 960 or len({row["case_id"] for row in rows}) != 960:
        raise RuntimeError("Linear row set is incomplete or contains duplicates.")
    if {row["metadata"]["cell_id"] for row in rows} != set(selected):
        raise RuntimeError("Linear rows do not contain exactly the locked fields.")

    checkpoints = []
    checkpoint_rows: dict[str, dict[str, Any]] = {}
    for cell in selected:
        path = OUTPUT / "cell_checkpoints" / f"{cell}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload["protocol_version"] != config["protocol_version"]
            or payload["archive_sha256"]
            != lock["archives"]["F-actin_linear"]["sha256"]
            or payload["config_sha256"] != lock["config"]["sha256"]
            or payload["implementation_sha256"]
            != lock["implementation_sha256"]
            or payload["rows_count"] != 120
        ):
            raise RuntimeError(f"Invalid checkpoint receipt for {cell}.")
        for row in payload["rows"]:
            case_id = str(row["case_id"])
            if case_id in checkpoint_rows:
                raise RuntimeError(f"Duplicate checkpoint case: {case_id}")
            checkpoint_rows[case_id] = row
        checkpoints.append(
            {
                key: payload[key]
                for key in ("cell_id", "rows_count", "elapsed_seconds")
            }
        )
    if set(checkpoint_rows) != {str(row["case_id"]) for row in rows}:
        raise RuntimeError("Final row file and locked checkpoints disagree.")
    for row in rows:
        if checkpoint_rows[str(row["case_id"])] != row:
            raise RuntimeError(f"Row payload differs for {row['case_id']}.")

    rules = {
        **config["confirmation"]["primary_safety_rules"],
        **config["confirmation"][
            "separate_incremental_coherence_utility_rules"
        ],
    }
    evaluation = evaluate_v7_confirmation(rows, rules=rules)
    specification = config["structures"]["F-actin_linear"]
    receipt = {
        "protocol_version": config["protocol_version"],
        "status": "complete_v7_confirmation_archive_recovered_after_receipt_path_serialization_error",
        "analysis_role": "locked_untouched_f_actin_linear_confirmation_archive",
        "structure": "F-actin_linear",
        "recovery": {
            "reason": "The locked runner completed every field and wrote checkpoints plus tensor_cases.jsonl, then raised ValueError while serializing a relative artifact path on Windows.",
            "scientific_computation_repeated": False,
            "rows_recalculated": False,
            "recovery_checks": "Lock, implementation, configuration, selection, archive hash, all eight checkpoints, 960 unique cases and byte-level JSON row equality were verified before receipt construction.",
            "finalizer_path": str(Path(__file__).resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
            "finalizer_sha256": sha256_file(Path(__file__)),
        },
        "selection": {
            "selected_cells": selected,
            "available_cells": len(pair_index["available_cells"]),
            "selected_reference_fields": len(selected),
            "outcome_or_pixel_dependent": False,
        },
        "reference_policy": {
            "primary_reference_basename": specification[
                "primary_reference_basename"
            ],
            "excluded_reference_basenames": specification[
                "excluded_reference_basenames"
            ],
        },
        "archive": lock["archives"]["F-actin_linear"],
        "config": lock["config"],
        "implementation": implementation,
        "confirmation_lock_sha256": sha256_file(LOCK),
        "runtime": {
            "finalizer_python": sys.version,
            "finalizer_platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
        },
        "checkpoints": sorted(checkpoints, key=lambda item: item["cell_id"]),
        "rows": len(rows),
        "pairs": len({str(row["pair_id"]) for row in rows}),
        "provisional_single_archive_evaluation": evaluation,
        "combined_gate_required": True,
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
    receipt_path.write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(receipt_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
                "bytes": receipt_path.stat().st_size,
                "sha256": sha256_file(receipt_path),
                "status": receipt["status"],
                "evaluation": evaluation["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

