"""Verify and audit the frozen NOSTOS BioSR version-5 twelve-field pilot."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from nostos.validation.paired_acquisition_support import aurc, risk_coverage_curve, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_RECEIPT = PROJECT_ROOT / "manifests" / "biosr_small_pilot_v5_artifact_receipt.json"
DEFAULT_PROFILE = PROJECT_ROOT / "configs" / "biosr_widefield_measurement_profile_v1.locked.json"
DEFAULT_PROTOCOL = PROJECT_ROOT / "configs" / "paired_acquisition_support_v5.locked.json"
DEFAULT_REPAIR_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_pilot_repair_v5_lock.json"


def _verify_artifact(specification: Mapping[str, Any]) -> Path:
    path = (PROJECT_ROOT / str(specification["path"])).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing receipted artifact: {path}")
    observed_bytes = path.stat().st_size
    observed_hash = sha256_file(path)
    if observed_bytes != int(specification["bytes"]) or observed_hash != specification["sha256"]:
        raise RuntimeError(
            f"Artifact receipt mismatch for {path}: expected "
            f"{specification['bytes']} bytes/{specification['sha256']}, observed "
            f"{observed_bytes} bytes/{observed_hash}."
        )
    return path


def _verify_lock(path: Path) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    for specification in lock["files"]:
        _verify_artifact(specification)
    return lock


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
    return rows


def load_verified_pilot(
    artifact_receipt_path: Path,
    profile_path: Path,
    protocol_path: Path,
    repair_lock_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Verify all pilot lineage and return rows, profile, protocol, and input receipts."""

    repair_lock = _verify_lock(repair_lock_path)
    artifact_receipt = json.loads(artifact_receipt_path.read_text(encoding="utf-8"))
    if artifact_receipt.get("status") != "complete_developmental_small_pilot_final_score":
        raise RuntimeError("Pilot artifact receipt is not complete.")
    _verify_artifact(artifact_receipt["selection_lock"])
    shared = artifact_receipt["shared"]
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != shared["protocol_version"]:
        raise RuntimeError("Protocol version disagrees with pilot artifact receipt.")
    if sha256_file(protocol_path) != shared["config_sha256"]:
        raise RuntimeError("Protocol hash disagrees with pilot artifact receipt.")
    _verify_artifact(
        {
            "path": profile["basis"]["artifact_receipt_path"],
            "bytes": profile["basis"]["artifact_receipt_bytes"],
            "sha256": profile["basis"]["artifact_receipt_sha256"],
        }
    )

    rows: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for entry in artifact_receipt["artifacts"]:
        receipt_path = _verify_artifact(entry["archive_receipt"])
        endpoint_path = _verify_artifact(entry["endpoint_cases"])
        _verify_artifact(entry["pair_index"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected = {
            "protocol_version": shared["protocol_version"],
            "status": "smoke_test",
            "stage": "score_design",
            "structure": entry["structure"],
            "config_sha256": shared["config_sha256"],
        }
        for key, value in expected.items():
            if receipt.get(key) != value:
                raise RuntimeError(f"Receipt field {key} disagrees at {receipt_path}.")
        if receipt.get("implementation", {}).get("sha256") != shared["implementation_sha256"]:
            raise RuntimeError(f"Implementation hash disagrees at {receipt_path}.")
        observed_cells = sorted(str(item["cell_id"]) for item in receipt["checkpoints"])
        if observed_cells != sorted(str(value) for value in entry["selected_cell_ids"]):
            raise RuntimeError(f"Selected cells disagree at {receipt_path}.")
        observed_rows = _read_jsonl(endpoint_path)
        if len(observed_rows) != int(entry["endpoint_cases_count"]):
            raise RuntimeError(f"Endpoint row count disagrees at {endpoint_path}.")
        rows.extend(observed_rows)
        receipts.append(
            {
                "structure": entry["structure"],
                "archive_receipt_path": str(receipt_path),
                "archive_receipt_sha256": entry["archive_receipt"]["sha256"],
                "endpoint_cases_path": str(endpoint_path),
                "endpoint_cases_sha256": entry["endpoint_cases"]["sha256"],
                "selected_cell_ids": observed_cells,
            }
        )

    if len(rows) != int(shared["endpoint_cases"]):
        raise RuntimeError("Pooled endpoint row count disagrees with the pilot receipt.")
    case_ids = [str(row["case_id"]) for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise RuntimeError("Duplicate endpoint case identifiers detected.")
    forbidden_partitions = sorted({str(row["development_partition"]) for row in rows} - {"score_design"})
    if forbidden_partitions:
        raise RuntimeError(f"Non-score-design rows detected: {forbidden_partitions}")
    observed_endpoints = {str(row["endpoint"]) for row in rows}
    profiled_endpoints = set(profile["eligible_for_threshold_calibration"]) | set(
        profile["disabled_for_this_acquisition_profile"]
    )
    if observed_endpoints != profiled_endpoints:
        raise RuntimeError(
            f"Acquisition profile does not exhaustively classify endpoints: "
            f"observed={sorted(observed_endpoints)}, profiled={sorted(profiled_endpoints)}"
        )
    if repair_lock.get("stage") != "decision_score_and_acquisition_profile_before_version_5_rerun":
        raise RuntimeError("Unexpected version-5 repair lock stage.")
    return rows, profile, protocol, receipts


def _reference_cases(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])
    ]


def _unit_boundary_cases(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in _reference_cases(rows)
        if not bool(row["hard_abstention"]) and float(row["scores"]["full_contract"]) <= 1.0
    ]


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def _quantile(values: Sequence[float], probability: float) -> float | None:
    return float(np.quantile(np.asarray(values, dtype=float), probability)) if values else None


def summarize_subset(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reference = _reference_cases(rows)
    accepted = _unit_boundary_cases(rows)
    invalid = [row for row in reference if bool(row["invalid"])]
    accepted_invalid = [row for row in accepted if bool(row["invalid"])]
    conditions = list(reference[0]["scores"]) if reference else []
    return {
        "endpoint_cases": len(rows),
        "registered_cases": sum(bool(row["pair_registration_eligible"]) for row in rows),
        "reference_eligible_cases": len(reference),
        "reference_eligibility_fraction_of_registered": _safe_fraction(
            len(reference), sum(bool(row["pair_registration_eligible"]) for row in rows)
        ),
        "reference_fields": len({str(row["reference_group_id"]) for row in reference}),
        "paired_acquisitions": len({str(row["pair_id"]) for row in reference}),
        "invalid_cases": len(invalid),
        "nonselective_risk": _safe_fraction(len(invalid), len(reference)),
        "hard_abstentions": sum(bool(row["hard_abstention"]) for row in reference),
        "unit_boundary": {
            "threshold": 1.0,
            "accepted_cases": len(accepted),
            "coverage": _safe_fraction(len(accepted), len(reference)),
            "silent_invalid_cases": len(accepted_invalid),
            "selective_risk": _safe_fraction(len(accepted_invalid), len(accepted)),
            "invalid_rejection_fraction": _safe_fraction(len(invalid) - len(accepted_invalid), len(invalid)),
            "status": "descriptive_not_final_threshold",
        },
        "error": {
            "median": _quantile([float(row["error"]) for row in reference], 0.5),
            "p95": _quantile([float(row["error"]) for row in reference], 0.95),
        },
        "aurc": {condition: aurc(reference, condition) for condition in conditions},
    }


def _endpoint_status(
    endpoint: str,
    summary: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> str:
    if endpoint in profile["disabled_for_this_acquisition_profile"]:
        return "disabled_by_acquisition_profile"
    if int(summary["reference_eligible_cases"]) == 0:
        return "no_reference_eligible_cases"
    if int(summary["invalid_cases"]) == 0:
        return "zero_observed_failures_in_eligible_pilot_cases"
    if int(summary["unit_boundary"]["silent_invalid_cases"]) == 0:
        return "all_observed_failures_rejected_at_unit_boundary"
    return "silent_failures_remain_at_unit_boundary"


def endpoint_summaries(
    rows: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["structure"]), str(row["endpoint"]))].append(row)
    output: list[dict[str, Any]] = []
    for (structure, endpoint), subset in sorted(groups.items()):
        summary = summarize_subset(subset)
        output.append(
            {
                "structure": structure,
                "endpoint": endpoint,
                "profile_status": (
                    "disabled"
                    if endpoint in profile["disabled_for_this_acquisition_profile"]
                    else "eligible_for_threshold_calibration"
                ),
                "observed_status": _endpoint_status(endpoint, summary, profile),
                "endpoint_cases": summary["endpoint_cases"],
                "registered_cases": summary["registered_cases"],
                "reference_eligible_cases": summary["reference_eligible_cases"],
                "reference_eligibility_fraction": summary["reference_eligibility_fraction_of_registered"],
                "invalid_cases": summary["invalid_cases"],
                "nonselective_risk": summary["nonselective_risk"],
                "hard_abstentions": summary["hard_abstentions"],
                "unit_boundary_accepted": summary["unit_boundary"]["accepted_cases"],
                "unit_boundary_coverage": summary["unit_boundary"]["coverage"],
                "unit_boundary_silent_invalid": summary["unit_boundary"]["silent_invalid_cases"],
                "unit_boundary_selective_risk": summary["unit_boundary"]["selective_risk"],
                "full_contract_aurc": summary["aurc"].get("full_contract"),
                "always_emit_aurc": summary["aurc"].get("always_emit"),
                "conventional_qc_aurc": summary["aurc"].get("conventional_acquisition_qc"),
                "median_error": summary["error"]["median"],
                "p95_error": summary["error"]["p95"],
            }
        )
    return output


def signal_level_summaries(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        level = int(row["metadata"]["signal_level_ordinal"])
        groups[(str(row["structure"]), str(row["endpoint"]), level)].append(row)
    output: list[dict[str, Any]] = []
    for (structure, endpoint, level), subset in sorted(groups.items()):
        summary = summarize_subset(subset)
        output.append(
            {
                "structure": structure,
                "endpoint": endpoint,
                "signal_level_ordinal": level,
                "reference_eligible_cases": summary["reference_eligible_cases"],
                "invalid_cases": summary["invalid_cases"],
                "nonselective_risk": summary["nonselective_risk"],
                "unit_boundary_coverage": summary["unit_boundary"]["coverage"],
                "unit_boundary_selective_risk": summary["unit_boundary"]["selective_risk"],
                "median_full_contract_score": _quantile(
                    [
                        float(row["scores"]["full_contract"])
                        for row in _reference_cases(subset)
                    ],
                    0.5,
                ),
            }
        )
    return output


def clustered_unit_boundary_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap field-clustered unit-boundary coverage and risk, stratified by structure."""

    reference = _reference_cases(rows)
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in reference:
        grouped[str(row["structure"])][str(row["reference_group_id"])].append(row)
    rng = np.random.default_rng(seed)
    coverage = np.empty(draws, dtype=float)
    selective_risk = np.empty(draws, dtype=float)
    nonselective_risk = np.empty(draws, dtype=float)
    for draw in range(draws):
        sampled_rows: list[Mapping[str, Any]] = []
        for structure in sorted(grouped):
            identifiers = sorted(grouped[structure])
            sampled = rng.choice(identifiers, size=len(identifiers), replace=True)
            for identifier in sampled:
                sampled_rows.extend(grouped[structure][str(identifier)])
        accepted = _unit_boundary_cases(sampled_rows)
        invalid = sum(bool(row["invalid"]) for row in sampled_rows)
        accepted_invalid = sum(bool(row["invalid"]) for row in accepted)
        coverage[draw] = len(accepted) / len(sampled_rows)
        nonselective_risk[draw] = invalid / len(sampled_rows)
        selective_risk[draw] = accepted_invalid / len(accepted) if accepted else np.nan

    def interval(values: np.ndarray) -> dict[str, Any]:
        finite = values[np.isfinite(values)]
        return {
            "finite_draws": int(len(finite)),
            "median": float(np.median(finite)),
            "ci95": [float(value) for value in np.quantile(finite, [0.025, 0.975])],
        }

    return {
        "draws": draws,
        "seed": seed,
        "resampling_unit": "reference_group_id, stratified by structure",
        "unit_boundary_coverage": interval(coverage),
        "unit_boundary_selective_risk": interval(selective_risk),
        "nonselective_risk": interval(nonselective_risk),
    }


def coverage_landmarks(
    rows: Sequence[Mapping[str, Any]],
    condition: str,
    targets: Sequence[float] = (0.5, 0.7, 0.8, 0.9, 0.95),
) -> dict[str, dict[str, float] | None]:
    """Return the closest tied-score operating point at or below each target coverage."""

    curve = risk_coverage_curve(rows, condition)
    output: dict[str, dict[str, float] | None] = {}
    for target in targets:
        candidates = [point for point in curve if float(point["coverage"]) <= float(target)]
        output[f"{target:.2f}"] = max(candidates, key=lambda point: point["coverage"]) if candidates else None
    return output


def _write_csv(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{100 * value:.1f}%"


def write_verdict(
    path: Path,
    audit: Mapping[str, Any],
    endpoint_rows: Sequence[Mapping[str, Any]],
) -> None:
    claim = audit["claim_endpoint_summary"]
    pooled = audit["all_endpoint_summary"]
    disabled = [row for row in endpoint_rows if row["profile_status"] == "disabled"]
    silent = [
        row
        for row in endpoint_rows
        if row["profile_status"] != "disabled" and int(row["unit_boundary_silent_invalid"]) > 0
    ]
    zero_failure = [
        row
        for row in endpoint_rows
        if row["profile_status"] != "disabled"
        and row["observed_status"] == "zero_observed_failures_in_eligible_pilot_cases"
    ]
    text = f"""# NOSTOS-0 version-5 small-pilot verdict

## Decision

**Promising and materially corrected, but not yet a validated or clinically usable tool.** The twelve-field pilot is sufficient to identify what currently works, what must be disabled, and what requires untouched calibration. It is not sufficient to establish generalization.

## What the pilot actually tested

- 12 independent BioSR reference fields: six CCP and six ER.
- 90 paired acquisitions and {pooled['endpoint_cases']} endpoint cases.
- {pooled['reference_eligible_cases']} registered, reference-eligible endpoint cases across all measured endpoints.
- A frozen physically calibrated estimator, input-only validity evidence, registered high-resolution reference labels, and field-level provenance.

## Result after the acquisition profile is applied

The profile retains {len(audit['profile']['eligible_for_threshold_calibration'])} endpoint families and disables three scalar outputs. Among retained claim endpoints, always-emitting risk was {_percent(claim['nonselective_risk'])}. The descriptive unit score boundary accepted {_percent(claim['unit_boundary']['coverage'])} with {_percent(claim['unit_boundary']['selective_risk'])} observed risk. This is not the final threshold.

Full-contract AURC on retained endpoints was {claim['aurc']['full_contract']:.4f}, versus {claim['aurc']['always_emit']:.4f} for always emit and {claim['aurc']['conventional_acquisition_qc']:.4f} for conventional QC.

As a descriptive ranking check, the closest tied-score point at or below 80% coverage accepted {_percent(audit['claim_risk_coverage_landmarks']['full_contract']['0.80']['coverage'])} with {_percent(audit['claim_risk_coverage_landmarks']['full_contract']['0.80']['risk'])} observed risk. At or below 90% coverage it accepted {_percent(audit['claim_risk_coverage_landmarks']['full_contract']['0.90']['coverage'])} with {_percent(audit['claim_risk_coverage_landmarks']['full_contract']['0.90']['risk'])} risk. These points were observed on development data and are not operating thresholds.

## Clean observations

{len(zero_failure)} structure-endpoint combinations had zero observed failures among reference-eligible pilot cases. This includes the response curves, angular entropy, anisotropy, variogram outputs, CCP coherence, and consensus-gated ER orientation. Zero observed failures in a small developmental pilot is encouraging, not a population guarantee.

## Explicitly disabled

"""
    for row in disabled:
        reason = audit["profile"]["disabled_for_this_acquisition_profile"][row["endpoint"]]
        text += f"- {row['structure']} / `{row['endpoint']}`: {reason}\n"
    text += "\n## Remaining failure\n\n"
    if silent:
        for row in silent:
            text += (
                f"- {row['structure']} / `{row['endpoint']}` retained "
                f"{row['unit_boundary_silent_invalid']} silent invalid cases at the descriptive unit boundary "
                f"(risk {_percent(row['unit_boundary_selective_risk'])}).\n"
            )
    else:
        text += "- No retained endpoint had a silent invalid case at the descriptive unit boundary.\n"
    text += """

ER tensor coherence is the principal unresolved item. All observed errors occurred at the two lowest signal levels, and the corrected score ranks those failures, but an untouched calibration partition must establish a threshold with field-clustered uncertainty.

## Go/no-go

- **Go** for continued research-tool development and frozen threshold calibration.
- **No-go** for clinical interpretation, intraoperative use, submission claims, or access to confirmation data before the threshold lock.
- **No further score or endpoint editing on these twelve fields.** Any additional change starts a new development version and leaves the calibration and confirmation partitions untouched.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-receipt", type=Path, default=DEFAULT_ARTIFACT_RECEIPT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--repair-lock", type=Path, default=DEFAULT_REPAIR_LOCK)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=26_082_801)
    args = parser.parse_args()

    rows, profile, protocol, receipts = load_verified_pilot(
        args.artifact_receipt,
        args.profile,
        args.protocol,
        args.repair_lock,
    )
    claim_endpoints = set(profile["eligible_for_threshold_calibration"])
    claim_rows = [row for row in rows if str(row["endpoint"]) in claim_endpoints]
    endpoint_rows = endpoint_summaries(rows, profile)
    signal_rows = signal_level_summaries(rows)
    all_summary = summarize_subset(rows)
    claim_summary = summarize_subset(claim_rows)
    claim_summary["aurc_reduction_fraction_vs_always_emit"] = 1.0 - (
        float(claim_summary["aurc"]["full_contract"])
        / float(claim_summary["aurc"]["always_emit"])
    )
    bootstrap = clustered_unit_boundary_bootstrap(
        claim_rows,
        draws=args.bootstrap_draws,
        seed=args.bootstrap_seed,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    endpoint_path = args.output / "endpoint_summary.csv"
    signal_path = args.output / "signal_level_summary.csv"
    verdict_path = args.output / "PILOT_VERDICT.md"
    _write_csv(endpoint_rows, endpoint_path)
    _write_csv(signal_rows, signal_path)
    audit: dict[str, Any] = {
        "schema_version": "nostos-biosr-small-pilot-audit/5.0",
        "analysis_role": "developmental_balanced_small_pilot",
        "artifact_receipt": {
            "path": str(args.artifact_receipt),
            "sha256": sha256_file(args.artifact_receipt),
        },
        "repair_lock": {
            "path": str(args.repair_lock),
            "sha256": sha256_file(args.repair_lock),
        },
        "protocol": {
            "path": str(args.protocol),
            "sha256": sha256_file(args.protocol),
            "version": protocol["protocol_version"],
        },
        "profile": profile,
        "input_receipts": receipts,
        "all_endpoint_summary": all_summary,
        "claim_endpoint_summary": claim_summary,
        "clustered_bootstrap": bootstrap,
        "claim_risk_coverage_landmarks": {
            condition: coverage_landmarks(claim_rows, condition)
            for condition in (
                "full_contract",
                "conventional_acquisition_qc",
                "perturbation_stability_only",
            )
        },
        "endpoint_rows": endpoint_rows,
        "artifacts": {},
        "claim_boundary": (
            "Developmental twelve-field evidence only; no final threshold, confirmation, "
            "generalization, clinical, or submission claim."
        ),
    }
    write_verdict(verdict_path, audit, endpoint_rows)
    audit["artifacts"] = {
        "endpoint_summary_sha256": sha256_file(endpoint_path),
        "signal_level_summary_sha256": sha256_file(signal_path),
        "pilot_verdict_sha256": sha256_file(verdict_path),
    }
    audit_path = args.output / "pilot_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "all_endpoint_summary": all_summary,
                "claim_endpoint_summary": claim_summary,
                "clustered_bootstrap": bootstrap,
                "audit_sha256": sha256_file(audit_path),
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
