"""Combine and audit the three locked BioSR v6 confirmation archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from nostos.validation.confirmation_v6 import evaluate_v6_confirmation
from nostos.validation.paired_acquisition_support import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "paired_acquisition_support_v6.locked.json"
DEFAULT_LOCK = (
    PROJECT_ROOT / "manifests" / "paired_acquisition_support_v6_confirmation_lock.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "nostos0-biosr-v6-initial-confirmation"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _verify_receipt(
    path: Path,
    *,
    config_sha256: str,
    lock_sha256: str,
    fields_per_structure: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("status") != "complete_initial_confirmation_archive":
        raise ValueError(f"Incomplete confirmation archive: {path}")
    if receipt["config"]["sha256"] != config_sha256:
        raise ValueError(f"Wrong v6 config in {path}")
    if receipt["confirmation_lock_sha256"] != lock_sha256:
        raise ValueError(f"Wrong v6 confirmation lock in {path}")
    endpoint_path = path.parent / "endpoint_cases.jsonl"
    pair_path = path.parent / "pair_index.json"
    for label, target in (("endpoint_cases", endpoint_path), ("pair_index", pair_path)):
        expected = receipt["artifacts"][label]
        if (
            target.stat().st_size != int(expected["bytes"])
            or sha256_file(target) != expected["sha256"]
        ):
            raise ValueError(f"Artifact mismatch for {target}")
    structure = str(receipt["structure"])
    available = list(receipt["selection"]["available_reference_group_ids"])
    expected_groups = sorted(
        available,
        key=lambda group: hashlib.sha256(
            f"NOSTOS-v6-initial-confirmation|{structure}|{group}".encode("utf-8")
        ).hexdigest(),
    )[:fields_per_structure]
    expected_cells = [group.split("|")[-1] for group in expected_groups]
    if receipt["selection"]["selected_cells"] != expected_cells:
        raise ValueError(f"Confirmation selection is not the frozen hash tranche: {path}")
    return _read_jsonl(endpoint_path), {
        "structure": structure,
        "archive_receipt": _artifact(path),
        "endpoint_cases": _artifact(endpoint_path),
        "pair_index": _artifact(pair_path),
        "selected_cells": expected_cells,
        "implementation_sha256": receipt["implementation"]["sha256"],
    }


def _write_policy_csv(path: Path, policies: Mapping[str, Any]) -> None:
    fields = [
        "condition",
        "eligible",
        "accepted",
        "coverage",
        "invalid",
        "risk",
        "risk_coverage_auc",
        "cluster_bootstrap_risk_upper95",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for condition, result in policies.items():
            writer.writerow(
                {
                    "condition": condition,
                    "eligible": result["eligible"],
                    "accepted": result["accepted"],
                    "coverage": result["coverage"],
                    "invalid": result["invalid"],
                    "risk": result["risk"],
                    "risk_coverage_auc": result["risk_coverage_auc"],
                    "cluster_bootstrap_risk_upper95": result.get(
                        "cluster_bootstrap_risk_upper95"
                    ),
                }
            )


def _write_combination_csv(path: Path, policies: Mapping[str, Any]) -> None:
    fields = [
        "condition",
        "structure",
        "endpoint_family",
        "eligible",
        "accepted",
        "coverage",
        "invalid",
        "risk",
        "reference_fields",
        "passes",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for condition, result in policies.items():
            for item in result["combinations"]:
                writer.writerow(
                    {
                        "condition": condition,
                        "structure": item["structure"],
                        "endpoint_family": item["endpoint_family"],
                        "eligible": item["eligible"],
                        "accepted": item["accepted"],
                        "coverage": item["coverage"],
                        "invalid": item["invalid"],
                        "risk": item["risk"],
                        "reference_fields": item["reference_fields"],
                        "passes": item.get("passes"),
                    }
                )


def _percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{100.0 * value:.2f}%"


def _write_verdict(path: Path, audit: Mapping[str, Any]) -> None:
    result = audit["result"]
    full = result["policies"]["full_contract"]
    qc = result["policies"]["conventional_acquisition_qc"]
    failed = [item for item in full["combinations"] if not item.get("passes", True)]
    failed_lines = [
        f"- {item['structure']} / {item['endpoint_family']}: "
        f"{_percent(item['coverage'])} coverage, {_percent(item['risk'])} risk."
        for item in failed
    ]
    path.write_text(
        "\n".join(
            [
                "# NOSTOS-0 BioSR v6 initial-confirmation verdict",
                "",
                f"**Status:** {result['status'].upper()}  ",
                f"**Safety gate:** {'PASS' if result['safety_gate_passed'] else 'FAIL'}  ",
                f"**Incremental comparator:** {result['incremental_comparator']['status'].upper()}  ",
                "**Threshold refitting:** None",
                "",
                "## Fixed-policy result",
                "",
                f"Across {result['reference_fields']} independently selected reference fields, the frozen full contract retained {_percent(full['coverage'])} of eligible cases at {_percent(full['risk'])} observed risk. Its structure-stratified field-cluster bootstrap upper 95% risk was {_percent(full.get('cluster_bootstrap_risk_upper95'))}.",
                "",
                f"Conventional acquisition QC retained {_percent(qc['coverage'])} at {_percent(qc['risk'])} risk. Full-contract AURC reduction relative to always emit was {_percent(result['aurc_reduction_fraction_vs_always_emit'])}.",
                "",
                "## Failing structure–family combinations",
                "",
                *(failed_lines or ["- None."]),
                "",
                "## Claim boundary",
                "",
                "This is paired-acquisition technical confirmation relative to registered BioSR high-resolution references. It does not establish biological truth, clinical validity, diagnosis, intraoperative utility or generalization to an unrelated microscope family.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--microtubules-receipt", type=Path, required=True)
    parser.add_argument("--f-actin-linear-receipt", type=Path, required=True)
    parser.add_argument("--f-actin-nonlinear-receipt", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--confirmation-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    config_sha = sha256_file(args.config)
    lock_sha = sha256_file(args.confirmation_lock)
    rows: list[dict[str, Any]] = []
    receipts = []
    for path in (
        args.microtubules_receipt,
        args.f_actin_linear_receipt,
        args.f_actin_nonlinear_receipt,
    ):
        source_rows, receipt = _verify_receipt(
            path,
            config_sha256=config_sha,
            lock_sha256=lock_sha,
            fields_per_structure=int(
                config["initial_confirmation"]["fields_per_structure"]
            ),
        )
        rows.extend(source_rows)
        receipts.append(receipt)
    observed = {item["structure"] for item in receipts}
    expected = set(config["initial_confirmation"]["structures"])
    if observed != expected:
        raise ValueError(f"Confirmation structures mismatch: {observed} != {expected}")
    implementations = {item["implementation_sha256"] for item in receipts}
    if len(implementations) != 1:
        raise ValueError("Confirmation archives used different implementations.")

    result = evaluate_v6_confirmation(rows, config=config)
    args.output.mkdir(parents=True, exist_ok=True)
    audit_path = args.output / "confirmation_audit.json"
    verdict_path = args.output / "CONFIRMATION_VERDICT.md"
    policy_path = args.output / "policy_summary.csv"
    combination_path = args.output / "structure_family_summary.csv"
    audit = {
        "schema_version": "nostos-biosr-v6-initial-confirmation/1.0",
        "created_at_utc": _utc_now(),
        "analysis_role": "untouched_initial_confirmation",
        "config": _artifact(args.config),
        "confirmation_lock": _artifact(args.confirmation_lock),
        "sources": receipts,
        "result": result,
        "confirmation_archives_accessed_only_after_lock": True,
        "claim_boundary": config["claim_boundary"],
    }
    audit_path.write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_policy_csv(policy_path, result["policies"])
    _write_combination_csv(combination_path, result["policies"])
    _write_verdict(verdict_path, audit)
    print(
        json.dumps(
            {
                "status": result["status"],
                "safety_gate_passed": result["safety_gate_passed"],
                "incremental_comparator": result["incremental_comparator"],
                "full_contract": result["policies"]["full_contract"],
                "artifacts": {
                    "audit": _artifact(audit_path),
                    "verdict": _artifact(verdict_path),
                    "policies": _artifact(policy_path),
                    "combinations": _artifact(combination_path),
                },
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
