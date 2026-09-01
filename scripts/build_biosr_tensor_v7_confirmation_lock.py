"""Freeze the NOSTOS BioSR tensor v7 F-actin confirmation package."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import (
    archive_layout_from_central_directory,
    select_confirmation_cells_v7,
)
from nostos.validation.paired_acquisition_support import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
)
CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
DEVELOPMENT_AUDIT = (
    ROOT
    / "outputs/nostos0-biosr-v7-family-specific-evidence-audit/family_specific_evidence_audit.json"
)
ARCHIVES = {
    "F-actin_linear": Path(
        r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin.zip"
    ),
    "F-actin_nonlinear": Path(
        r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\F-actin_Nonlinear.zip"
    ),
}
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


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise FileExistsError(
            f"Refusing to overwrite the v7 confirmation lock: {args.output}"
        )
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    development = json.loads(DEVELOPMENT_AUDIT.read_text(encoding="utf-8"))
    if config["protocol_version"] != "nostos-paired-acquisition-tensor/7.0":
        raise ValueError("Unexpected v7 protocol version.")
    if not development["freeze_decision"][
        "eligible_to_freeze_measurement_safety_contract"
    ]:
        raise ValueError("The v7 safety contract did not pass development.")
    if development["freeze_decision"][
        "eligible_to_freeze_incremental_benefit_claim"
    ]:
        raise ValueError(
            "Development must not be represented as independent benefit evidence."
        )
    if set(config["confirmation"]["structures"]) != set(ARCHIVES):
        raise ValueError("Frozen structures and archive map differ.")

    layouts: dict[str, Any] = {}
    selected_cells: dict[str, list[str]] = {}
    archive_receipts: dict[str, Any] = {}
    for structure, archive in ARCHIVES.items():
        specification = config["structures"][structure]
        if archive.name != specification["archive_name"]:
            raise ValueError(f"Archive name mismatch for {structure}.")
        if archive.stat().st_size != int(specification["archive_bytes"]):
            raise ValueError(f"Archive byte count mismatch for {structure}.")
        observed_md5 = _md5(archive)
        if observed_md5.lower() != str(specification["archive_md5"]).lower():
            raise ValueError(f"Archive MD5 mismatch for {structure}.")
        layout = archive_layout_from_central_directory(
            archive,
            structure=structure,
            expected_level_count=int(specification["expected_level_count"]),
            reference_basename=str(specification["primary_reference_basename"]),
            excluded_reference_basenames=tuple(
                specification["excluded_reference_basenames"]
            ),
        )
        layouts[structure] = layout
        selected_cells[structure] = select_confirmation_cells_v7(
            layout["cells"],
            structure=structure,
            count=int(config["confirmation"]["fields_per_structure"]),
            salt=str(config["confirmation"]["selection_salt"]),
        )
        archive_receipts[structure] = {
            "path": str(archive.resolve()),
            "bytes": archive.stat().st_size,
            "md5": observed_md5,
            "sha256": sha256_file(archive),
            "figshare_file_id": specification["archive_file_id"],
            "central_directory_cell_count": layout["cell_count"],
            "central_directory_expected_levels": layout["expected_levels"],
            "primary_reference_basename": layout[
                "primary_reference_basename"
            ],
            "excluded_reference_basenames": layout[
                "excluded_reference_basenames"
            ],
        }

    implementation = _implementation_receipt()
    supporting = (
        CONFIG,
        DEVELOPMENT_AUDIT,
        ROOT
        / "outputs/nostos0-biosr-v7-family-specific-evidence-audit/family_specific_tensor_cases.jsonl",
        ROOT
        / "outputs/nostos0-biosr-v7-resolution-margin-calibration/resolution_margin_calibration.json",
        ROOT
        / "outputs/nostos0-biosr-v7-tensor-distribution-development/tensor_distribution_development.json",
        ROOT
        / "outputs/nostos0-biosr-v7-physical-tensor-cross-domain-development/candidate_screen.json",
        ROOT
        / "manifests/paired_acquisition_support_v6_confirmation_failure_receipt.json",
        ROOT / "docs/NOSTOS0_BIOSR_V6_INITIAL_CONFIRMATION_FAILURE.md",
        ROOT / "docs/NOSTOS0_BIOSR_V7_CONFIRMATION_PROTOCOL.md",
        ROOT / "scripts/audit_biosr_v7_family_specific_evidence.py",
        ROOT / "scripts/audit_biosr_tensor_v7_confirmation.py",
        Path(__file__).resolve(),
        ROOT / "tests/test_physical_tensor.py",
        ROOT / "tests/test_tensor_support_v7.py",
        ROOT / "tests/test_tensor_contract_audit_v7.py",
        ROOT / "tests/test_tensor_evidence_v7.py",
        ROOT / "tests/test_biosr_tensor_confirmation_v7.py",
    )
    unique = {
        item["path"]: item
        for item in [
            *implementation["files"],
            *[_artifact(path) for path in supporting],
        ]
    }
    payload = {
        "schema_version": "nostos-paired-acquisition-tensor-v7-confirmation-lock/1.0",
        "locked_at_utc": _utc_now(),
        "status": "locked_after_download_and_central_directory_layout_repair_before_any_v7_f_actin_pixel_array_decode_or_endpoint_outcome",
        "protocol_version": config["protocol_version"],
        "implementation_sha256": implementation["sha256"],
        "config": _artifact(CONFIG),
        "development_gate": {
            "status": development["status"],
            "measurement_safety_freeze_eligible": development[
                "freeze_decision"
            ]["eligible_to_freeze_measurement_safety_contract"],
            "incremental_benefit_freeze_eligible": development[
                "freeze_decision"
            ]["eligible_to_freeze_incremental_benefit_claim"],
            "full_contract": {
                key: development["safety_gate"]["full_contract"][key]
                for key in (
                    "eligible",
                    "accepted",
                    "coverage",
                    "invalid",
                    "risk",
                    "cluster_bootstrap_risk_upper95",
                )
            },
            "coherence_aurc": development[
                "coherence_risk_coverage_evidence"
            ],
            "selection_optimism_disclosed": development[
                "evidence_strength_gate"
            ]["selection_warning"],
        },
        "confirmation": {
            "structures": config["confirmation"]["structures"],
            "fields_per_structure": config["confirmation"][
                "fields_per_structure"
            ],
            "field_selection_rule": config["confirmation"][
                "field_selection_rule"
            ],
            "selected_cells": selected_cells,
            "all_signal_levels_in_selected_fields": True,
            "threshold_refitting_permitted": False,
            "endpoint_addition_or_removal_permitted": False,
            "primary_safety_and_incremental_utility_decided_separately": True,
        },
        "archives": archive_receipts,
        "access_state": {
            "before_v7_lock": "Archives downloaded and integrity verified; ZIP central-directory names and sizes inspected; one prior linear indexing attempt may have read MRC headers before failing on the v6 nine-level expectation; no F-actin pixel array or endpoint outcome decoded.",
            "during_v7_lock": "Only whole-archive hashes and ZIP central-directory metadata were read. No image member was opened by the lock builder.",
            "authorized_after_lock": "Read MRC headers for layout validation, then decode only the sixteen locked fields and all their frozen signal levels; calculate no unregistered endpoint.",
        },
        "nonlinear_reference_resolution": {
            "primary": "SIM_gt_a.mrc",
            "excluded": "SIM_gt_b.mrc",
            "owner_answer": config["source_provenance"][
                "nonlinear_reference_owner_answer"
            ],
            "rule": "The excluded gamma-overview image cannot enter registration, measurement, sensitivity selection or any gate.",
        },
        "files": [unique[key] for key in sorted(unique)],
        "verification": {
            "pytest_command": "uv run --frozen pytest -q",
            "pytest_result": "267 passed, 4 skipped, 12 dependency deprecation warnings",
            "pytest_exit_code": 0,
            "compile_command": "uv run --frozen python -m compileall -q src scripts",
            "compile_exit_code": 0,
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

