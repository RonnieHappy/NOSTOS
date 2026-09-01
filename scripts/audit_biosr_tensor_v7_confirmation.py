"""Strict combined audit for the two untouched BioSR tensor v7 archives."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import evaluate_v7_confirmation
from nostos.validation.paired_acquisition_support import sha256_file


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
INPUTS = {
    "F-actin_linear": ROOT
    / "outputs/nostos0-biosr-tensor-v7-f-actin-linear-confirmation",
    "F-actin_nonlinear": ROOT
    / "outputs/nostos0-biosr-tensor-v7-f-actin-nonlinear-confirmation",
}
OUTPUT = ROOT / "outputs/nostos0-biosr-tensor-v7-combined-audit"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    source_receipts = []
    for structure, directory in INPUTS.items():
        receipt_path = directory / "archive_receipt.json"
        rows_path = directory / "tensor_cases.jsonl"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["protocol_version"] != config["protocol_version"]:
            raise ValueError(f"Protocol mismatch for {structure}.")
        if receipt["structure"] != structure:
            raise ValueError(f"Structure mismatch for {structure}.")
        if receipt["confirmation_lock_sha256"] != sha256_file(LOCK):
            raise ValueError(f"Lock hash mismatch for {structure}.")
        if receipt["artifacts"]["tensor_cases"]["sha256"] != sha256_file(
            rows_path
        ):
            raise ValueError(f"Tensor-row hash mismatch for {structure}.")
        selected = receipt["selection"]["selected_cells"]
        if selected != lock["confirmation"]["selected_cells"][structure]:
            raise ValueError(f"Selected cells differ from lock for {structure}.")
        rows.extend(_read_jsonl(rows_path))
        source_receipts.append(
            {
                "structure": structure,
                "receipt_path": str(receipt_path.relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "receipt_sha256": sha256_file(receipt_path),
                "rows_path": str(rows_path.relative_to(ROOT)).replace("\\", "/"),
                "rows_sha256": sha256_file(rows_path),
                "fields": len(selected),
                "pairs": receipt["pairs"],
                "rows": receipt["rows"],
            }
        )
    if len({str(row["case_id"]) for row in rows}) != len(rows):
        raise ValueError("Combined confirmation contains duplicate case identifiers.")
    rules = {
        **config["confirmation"]["primary_safety_rules"],
        **config["confirmation"][
            "separate_incremental_coherence_utility_rules"
        ],
    }
    evaluation = evaluate_v7_confirmation(rows, rules=rules)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    combined_rows = OUTPUT / "combined_tensor_cases.jsonl"
    with combined_rows.open("w", encoding="utf-8") as stream:
        for row in sorted(rows, key=lambda item: str(item["case_id"])):
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload = {
        "schema_version": "nostos-biosr-tensor-v7-combined-confirmation-audit/1.0",
        "protocol_version": config["protocol_version"],
        "status": evaluation["status"],
        "evaluation": evaluation,
        "scope": {
            "structures": sorted(INPUTS),
            "reference_fields": sum(item["fields"] for item in source_receipts),
            "paired_acquisitions": sum(item["pairs"] for item in source_receipts),
            "endpoint_rows": len(rows),
        },
        "sources": source_receipts,
        "lineage": {
            "config_sha256": sha256_file(CONFIG),
            "confirmation_lock_sha256": sha256_file(LOCK),
            "auditor_sha256": sha256_file(Path(__file__)),
        },
        "artifacts": {
            "combined_tensor_cases": {
                "path": str(combined_rows.relative_to(ROOT)).replace("\\", "/"),
                "bytes": combined_rows.stat().st_size,
                "sha256": sha256_file(combined_rows),
            }
        },
        "interpretation": {
            "measurement_safety": (
                "confirmed on the frozen F-actin tranche"
                if evaluation["measurement_safety"]["passes"]
                else "failed on the frozen F-actin tranche"
            ),
            "incremental_coherence_utility": evaluation[
                "incremental_coherence_utility"
            ]["status"],
            "submission_rule": "A measurement-safety pass supports the endpoint's technical-validity claim. A high-impact validity-contract superiority claim additionally requires confirmed incremental coherence utility; not-assessable or failed utility cannot be restated as success.",
        },
        "claim_boundary": config["claim_boundary"],
    }
    output_path = OUTPUT / "combined_confirmation_audit.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
                "status": payload["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

