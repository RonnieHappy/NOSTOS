"""Seal the prospective NOSTOS BioSR v6 confirmation failure.

This builder is intentionally separate from the v6 locked implementation.  It
verifies the original confirmation lock, records the first untouched
Microtubules tranche exactly as emitted, and records the F-actin archive-layout
error without decoding an F-actin image member.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK = PROJECT_ROOT / "manifests/paired_acquisition_support_v6_confirmation_lock.json"
MICRO_DIR = PROJECT_ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation"
MICRO_RECEIPT = MICRO_DIR / "archive_receipt.json"
LINEAR_ARCHIVE = Path(
    r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin.zip"
)
LINEAR_OUTPUT = PROJECT_ROOT / "outputs/nostos0-biosr-v6-f-actin-linear-initial-confirmation"
REPORT = PROJECT_ROOT / "docs/NOSTOS0_BIOSR_V6_INITIAL_CONFIRMATION_FAILURE.md"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "manifests/paired_acquisition_support_v6_confirmation_failure_receipt.json"
)
LEVEL_PATTERN = re.compile(
    r"^F-actin/Cell_(?P<cell>\d+)/RawSIMData_level_(?P<level>\d+)\.mrc$",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        label = str(resolved.relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        label = str(resolved)
    return {
        "path": label,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_lock(lock: dict[str, Any]) -> None:
    failures: list[str] = []
    for item in lock["files"]:
        path = PROJECT_ROOT / str(item["path"])
        if not path.is_file():
            failures.append(f"missing:{item['path']}")
            continue
        if path.stat().st_size != int(item["bytes"]):
            failures.append(f"bytes:{item['path']}")
        if sha256_file(path) != str(item["sha256"]):
            failures.append(f"sha256:{item['path']}")
    if failures:
        raise RuntimeError(f"The original v6 confirmation lock no longer verifies: {failures}")


def index_linear_levels(archive: Path) -> dict[str, list[int]]:
    """Read only ZIP central-directory names; never open an image member."""

    levels: dict[str, set[int]] = {}
    with zipfile.ZipFile(archive) as handle:
        for name in handle.namelist():
            match = LEVEL_PATTERN.match(name)
            if match is None:
                continue
            cell = f"Cell_{int(match.group('cell')):03d}"
            levels.setdefault(cell, set()).add(int(match.group("level")))
    return {cell: sorted(values) for cell, values in sorted(levels.items())}


def build_payload() -> dict[str, Any]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    verify_lock(lock)
    micro = json.loads(MICRO_RECEIPT.read_text(encoding="utf-8"))
    if micro["status"] != "complete_initial_confirmation_archive":
        raise ValueError("The Microtubules receipt is not complete.")
    if micro["structure"] != "Microtubules":
        raise ValueError("The first confirmation receipt is not Microtubules.")
    if micro["confirmation_lock_sha256"] != sha256_file(LOCK):
        raise ValueError("The Microtubules run does not point to the frozen v6 lock.")
    if micro["config"]["sha256"] != lock["config"]["sha256"]:
        raise ValueError("The Microtubules config hash differs from the lock.")
    if micro["implementation"]["sha256"] != lock["implementation_sha256"]:
        raise ValueError("The Microtubules implementation differs from the lock.")

    provisional = micro["provisional_single_archive_policy_summary"]
    full = provisional["policies"]["full_contract"]
    combinations = {
        item["endpoint_family"]: item for item in full["combinations"]
    }
    if combinations["tensor_coherence"]["passes"] is not False:
        raise ValueError("Expected Microtubules tensor-coherence failure is absent.")
    if combinations["tensor_orientation"]["passes"] is not False:
        raise ValueError("Expected Microtubules tensor-orientation failure is absent.")
    if provisional["safety_gate_passed"] is not False:
        raise ValueError("The v6 Microtubules safety gate unexpectedly passed.")

    if not LINEAR_ARCHIVE.is_file():
        raise FileNotFoundError(LINEAR_ARCHIVE)
    if LINEAR_ARCHIVE.stat().st_size != 2_233_338_886:
        raise ValueError("F-actin linear archive byte count differs from the source manifest.")
    if md5_file(LINEAR_ARCHIVE) != "80fafab68f26fb71de12be0141face74":
        raise ValueError("F-actin linear archive MD5 differs from the source manifest.")
    levels = index_linear_levels(LINEAR_ARCHIVE)
    if not levels or any(value != list(range(1, 13)) for value in levels.values()):
        raise ValueError("The official F-actin linear archive is not uniformly 12-level.")
    if LINEAR_OUTPUT.exists():
        raise FileExistsError(
            "F-actin output exists; cannot attest that the layout failure preceded output."
        )

    micro_artifacts = [
        artifact(MICRO_RECEIPT),
        artifact(MICRO_DIR / "pair_index.json"),
        artifact(MICRO_DIR / "endpoint_cases.jsonl"),
    ]
    return {
        "schema_version": "nostos-paired-acquisition-v6-confirmation-failure/1.0",
        "created_at_utc": _utc_now(),
        "status": "prospective_v6_failed_after_first_untouched_structure",
        "protocol_version": "nostos-paired-acquisition-support/6.0",
        "lineage": {
            "confirmation_lock": artifact(LOCK),
            "implementation_sha256": lock["implementation_sha256"],
            "verified_locked_files": len(lock["files"]),
            "locked_file_mismatches": 0,
            "thresholds_refit_after_confirmation_access": False,
            "endpoints_changed_after_confirmation_access": False,
        },
        "access_ledger": {
            "Microtubules": "eight hash-selected fields decoded and analyzed once under v6",
            "F-actin_linear": "archive integrity verified and central-directory names indexed; zero image members decoded and zero endpoint outcomes computed",
            "F-actin_nonlinear": "no image member decoded and no endpoint outcome computed",
        },
        "microtubules_result": {
            "selected_fields": micro["selection"]["selected_cells"],
            "available_fields": micro["selection"]["available_cells"],
            "reference_fields": micro["selection"]["selected_reference_fields"],
            "paired_acquisitions": micro["pairs"],
            "endpoint_rows": micro["rows"],
            "full_contract": full,
            "aurc_reduction_fraction_vs_always_emit": provisional[
                "aurc_reduction_fraction_vs_always_emit"
            ],
            "safety_gate_passed": provisional["safety_gate_passed"],
            "incremental_comparator": provisional["incremental_comparator"],
            "artifacts": micro_artifacts,
        },
        "decisive_failures": [
            {
                "family": "tensor_coherence",
                "coverage": combinations["tensor_coherence"]["coverage"],
                "risk": combinations["tensor_coherence"]["risk"],
                "reason": "coverage below the frozen structure-family floor",
            },
            {
                "family": "tensor_orientation",
                "coverage": combinations["tensor_orientation"]["coverage"],
                "risk": combinations["tensor_orientation"]["risk"],
                "reason": "accepted-case risk above the frozen ceiling",
            },
            {
                "family": "all_families",
                "coverage": full["coverage"],
                "risk": full["risk"],
                "cluster_bootstrap_risk_upper95": full[
                    "cluster_bootstrap_risk_upper95"
                ],
                "reason": "overall coverage and clustered risk upper bound missed frozen gates",
            },
        ],
        "linear_layout_error": {
            "archive": {
                "path": str(LINEAR_ARCHIVE),
                "bytes": LINEAR_ARCHIVE.stat().st_size,
                "md5": "80fafab68f26fb71de12be0141face74",
                "sha256": sha256_file(LINEAR_ARCHIVE),
            },
            "indexed_cells": len(levels),
            "observed_levels_per_cell": list(range(1, 13)),
            "frozen_expected_level_count": 9,
            "failure_stage": "central-directory indexing before field selection and before pixel decode",
            "scientific_outcome_observed": False,
        },
        "decision": {
            "v6_confirmation_status": "failed",
            "remaining_f_actin_pixels_reserved": True,
            "microtubules_reclassified_for_next_version": "development_only",
            "next_gate": "Develop tensor repair on only the eight receipted Microtubules fields, freeze v7 and the corrected 12-level F-actin layouts, then decode the predeclared F-actin confirmation fields exactly once.",
        },
        "report": artifact(REPORT),
        "claim_boundary": "This is a failed research validation gate. It does not validate a universal measurement contract, clinical use, biological truth, diagnosis, intraoperative utility, or Nature-level readiness.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable receipt: {args.output}")
    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact(args.output), indent=2))


if __name__ == "__main__":
    main()
