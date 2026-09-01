"""Select and seal the NOSTOS BioSR v5 operating threshold."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from nostos.core.measurement_profile import MeasurementProfile
from nostos.validation.paired_acquisition_support import sha256_file
from nostos.validation.threshold_calibration import evaluate_threshold_calibration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "paired_acquisition_support_v5.locked.json"
DEFAULT_PROFILE = PROJECT_ROOT / "configs" / "biosr_widefield_measurement_profile_v1.locked.json"
DEFAULT_SCORE_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_score_formula_lock_v2.json"
DEFAULT_PILOT_SELECTION = PROJECT_ROOT / "manifests" / "biosr_small_pilot_v5_selection_lock.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "nostos0-biosr-threshold-calibration-v5"
DEFAULT_THRESHOLD_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_threshold_lock.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _verify_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures: list[dict[str, Any]] = []
    for item in payload["files"]:
        target = PROJECT_ROOT / item["path"]
        observed = sha256_file(target) if target.is_file() else None
        if (
            observed != item["sha256"]
            or not target.is_file()
            or target.stat().st_size != int(item["bytes"])
        ):
            failures.append(
                {"path": item["path"], "expected": item, "observed_sha256": observed}
            )
    if failures:
        raise RuntimeError(f"Score-formula lock verification failed: {failures}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _verify_archive_receipt(path: Path, expected_config_sha256: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("stage") != "threshold_calibration" or receipt.get("status") != "complete_threshold_calibration":
        raise ValueError(f"Archive receipt is not a completed threshold-calibration run: {path}")
    if receipt.get("config_sha256") != expected_config_sha256:
        raise ValueError(f"Archive receipt used the wrong frozen configuration: {path}")
    row_path = path.parent / "endpoint_cases.jsonl"
    index_path = path.parent / "pair_index.json"
    artifacts = receipt["artifacts"]
    if sha256_file(row_path) != artifacts["endpoint_cases_sha256"]:
        raise ValueError(f"Endpoint rows do not match their archive receipt: {row_path}")
    if sha256_file(index_path) != artifacts["pair_index_sha256"]:
        raise ValueError(f"Pair index does not match its archive receipt: {index_path}")
    return _read_jsonl(row_path), {
        "archive_receipt": _artifact(path),
        "endpoint_cases": _artifact(row_path),
        "pair_index": _artifact(index_path),
        "implementation_sha256": receipt["implementation"]["sha256"],
        "structure": receipt["structure"],
    }


def _write_combination_csv(path: Path, result: Mapping[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for label in ("operating_point", "conventional_qc_operating_point"):
        operating = result[label]
        for item in operating.get("combinations", []):
            rows.append({"condition": operating["condition"], **item})
    fieldnames = [
        "condition",
        "structure",
        "endpoint",
        "eligible",
        "accepted",
        "coverage",
        "invalid",
        "risk",
        "reference_fields",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{100 * value:.2f}%"


def _write_verdict(path: Path, audit: Mapping[str, Any]) -> None:
    result = audit["result"]
    operating = result["operating_point"]
    qc = result["conventional_qc_operating_point"]
    if operating["status"] == "operating_point_selected":
        operating_text = (
            f"The selected full-contract threshold is `{operating['threshold']:.12g}`. "
            f"It accepts {_percent(operating['coverage'])} of reference-eligible cases with "
            f"{_percent(operating['risk'])} observed risk and a stratified field-cluster "
            f"bootstrap upper 95% risk of {_percent(operating['cluster_bootstrap_risk_upper95'])}."
        )
    else:
        operating_text = "No threshold satisfied the frozen aggregate and structure–endpoint constraints."
    qc_text = (
        "No conventional-QC operating point passed the same constraints."
        if qc["status"] != "operating_point_selected"
        else (
            f"Conventional acquisition QC selected threshold `{qc['threshold']:.12g}` at "
            f"{_percent(qc['coverage'])} coverage and {_percent(qc['risk'])} observed risk."
        )
    )
    path.write_text(
        f"""# NOSTOS-0 BioSR threshold-calibration verdict

**Status:** {result['status'].upper()}  
**Analysis role:** One-time untouched threshold calibration  
**Confirmation data:** Not accessed

## Operating point

{operating_text}

{qc_text}

Full-contract AURC was {result['aurc']['full_contract']:.6f}, compared with {result['aurc']['always_emit']:.6f} for always emit and {result['aurc']['conventional_acquisition_qc']:.6f} for conventional acquisition QC. The reduction relative to always emit was {_percent(result['aurc']['reduction_fraction_vs_always_emit'])}.

## Frozen safeguards

Threshold selection used only endpoints retained by the locked acquisition profile. Every accepted, assessable structure–endpoint combination had to meet the 10% observed-risk limit and 70% coverage floor. Overall coverage had to reach 80%, and the stratified reference-field bootstrap upper 95% risk had to remain at or below 15%. The threshold maximizes coverage among tied-score cutoffs satisfying every rule.

## Decision boundary

Passing this gate authorizes the unchanged threshold for the untouched BioSR confirmation structures. It does not establish biological ground truth, acquisition-family generalization, clinical validity, diagnosis, treatment utility or intraoperative performance. A failed gate does not authorize threshold tuning on these calibration fields.
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ccp-receipt", type=Path, required=True)
    parser.add_argument("--er-receipt", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--score-lock", type=Path, default=DEFAULT_SCORE_LOCK)
    parser.add_argument("--pilot-selection", type=Path, default=DEFAULT_PILOT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold-lock-output", type=Path, default=DEFAULT_THRESHOLD_LOCK)
    args = parser.parse_args()

    score_lock = _verify_lock(args.score_lock)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    config_sha256 = sha256_file(args.config)
    profile = MeasurementProfile.from_path(args.profile)
    ccp_rows, ccp_receipts = _verify_archive_receipt(args.ccp_receipt, config_sha256)
    er_rows, er_receipts = _verify_archive_receipt(args.er_receipt, config_sha256)
    if ccp_receipts["implementation_sha256"] != er_receipts["implementation_sha256"]:
        raise ValueError("CCP and ER runs used different implementations.")
    if ccp_receipts["implementation_sha256"] != score_lock["implementation_sha256"]:
        raise ValueError("Calibration runs do not match the score-formula implementation lock.")
    if {ccp_receipts["structure"], er_receipts["structure"]} != {"CCPs", "ER"}:
        raise ValueError("Threshold calibration requires exactly the CCP and ER development structures.")
    rows = ccp_rows + er_rows
    pilot_selection = json.loads(args.pilot_selection.read_text(encoding="utf-8"))["selected"]
    observed_cells = {
        structure: {str(row["metadata"]["cell_id"]) for row in rows if row["structure"] == structure}
        for structure in ("CCPs", "ER")
    }
    overlaps = {
        structure: sorted(observed_cells[structure] & set(pilot_selection[structure]))
        for structure in ("CCPs", "ER")
    }
    if any(overlaps.values()):
        raise ValueError(f"Calibration fields overlap the score-design pilot: {overlaps}")
    result = evaluate_threshold_calibration(
        rows,
        eligible_endpoints=set(profile.eligible_endpoints),
        config=config,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    audit_path = args.output / "threshold_calibration.json"
    verdict_path = args.output / "THRESHOLD_VERDICT.md"
    combinations_path = args.output / "structure_endpoint_operating_points.csv"
    audit = {
        "schema_version": "nostos-biosr-threshold-calibration/1.0",
        "created_at_utc": _utc_now(),
        "analysis_role": "one_time_untouched_threshold_calibration",
        "lineage": {
            "config": _artifact(args.config),
            "profile": _artifact(args.profile),
            "score_formula_lock": _artifact(args.score_lock),
            "pilot_selection": _artifact(args.pilot_selection),
            "CCPs": ccp_receipts,
            "ER": er_receipts,
        },
        "field_selection": {
            "rule": config["development_partition"]["method"],
            "required_partition": "threshold_calibration",
            "cells": {key: sorted(value) for key, value in observed_cells.items()},
            "overlap_with_score_design_pilot": overlaps,
        },
        "result": result,
        "confirmation_archives_accessed": False,
        "claim_boundary": config["claim_boundary"],
    }
    audit_path.write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _write_combination_csv(combinations_path, result)
    _write_verdict(verdict_path, audit)
    if result["status"] == "pass":
        if args.threshold_lock_output.exists():
            raise FileExistsError(
                f"Refusing to overwrite an existing threshold lock: {args.threshold_lock_output}"
            )
        operating = result["operating_point"]
        files = [
            _artifact(path)
            for path in (
                args.config,
                args.profile,
                args.score_lock,
                Path(__file__),
                PROJECT_ROOT / "src" / "nostos" / "validation" / "threshold_calibration.py",
                args.ccp_receipt,
                args.ccp_receipt.parent / "endpoint_cases.jsonl",
                args.er_receipt,
                args.er_receipt.parent / "endpoint_cases.jsonl",
                audit_path,
                verdict_path,
                combinations_path,
            )
        ]
        threshold_lock = {
            "schema_version": "nostos-paired-acquisition-threshold-lock/1.0",
            "locked_at_utc": _utc_now(),
            "status": "threshold_locked_after_untouched_calibration_pass",
            "implementation_sha256": ccp_receipts["implementation_sha256"],
            "condition": "full_contract",
            "threshold": operating["threshold"],
            "eligible_endpoints": sorted(profile.eligible_endpoints),
            "calibration_result": {
                "coverage": operating["coverage"],
                "risk": operating["risk"],
                "cluster_bootstrap_risk_upper95": operating[
                    "cluster_bootstrap_risk_upper95"
                ],
                "aurc_reduction_fraction_vs_always_emit": result["aurc"][
                    "reduction_fraction_vs_always_emit"
                ],
            },
            "files": files,
            "confirmation_access": "authorized_only_for_unchanged_predeclared_confirmation_runs",
            "claim_boundary": "Operating threshold only; no clinical or biological validity claim.",
        }
        args.threshold_lock_output.parent.mkdir(parents=True, exist_ok=True)
        args.threshold_lock_output.write_text(
            json.dumps(threshold_lock, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operating_point": result["operating_point"],
                "aurc": result["aurc"],
                "audit": str(audit_path.resolve()),
                "verdict": str(verdict_path.resolve()),
                "threshold_lock": (
                    str(args.threshold_lock_output.resolve())
                    if result["status"] == "pass"
                    else None
                ),
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
