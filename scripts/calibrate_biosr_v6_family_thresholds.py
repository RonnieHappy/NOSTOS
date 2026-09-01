"""Select v6 structure-independent endpoint-family support thresholds."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from nostos.validation.paired_acquisition_support import sha256_file
from nostos.validation.selective_policy_v6 import select_family_policy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "paired_acquisition_support_v6_development.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "outputs" / "nostos0-biosr-v6-family-threshold-development"
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
        "path": str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _source_rows(receipt_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    endpoint_path = receipt_path.parent / "endpoint_cases.jsonl"
    pair_path = receipt_path.parent / "pair_index.json"
    if sha256_file(endpoint_path) != receipt["artifacts"]["endpoint_cases_sha256"]:
        raise ValueError(f"Endpoint hash mismatch: {endpoint_path}")
    if sha256_file(pair_path) != receipt["artifacts"]["pair_index_sha256"]:
        raise ValueError(f"Pair-index hash mismatch: {pair_path}")
    return _read_jsonl(endpoint_path), {
        "stage": receipt["stage"],
        "structure": receipt["structure"],
        "archive_receipt": _artifact(receipt_path),
        "endpoint_cases": _artifact(endpoint_path),
        "pair_index": _artifact(pair_path),
        "implementation_sha256": receipt["implementation"]["sha256"],
    }


def _write_family_csv(path: Path, policies: Mapping[str, Any]) -> None:
    fields = [
        "condition",
        "policy_status",
        "family",
        "family_status",
        "threshold",
        "eligible",
        "accepted",
        "coverage",
        "invalid",
        "risk",
        "cluster_bootstrap_risk_upper95",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for condition, policy in policies.items():
            for family, result in policy["families"].items():
                writer.writerow(
                    {
                        "condition": condition,
                        "policy_status": policy["status"],
                        "family": family,
                        "family_status": result["status"],
                        "threshold": result["threshold"],
                        "eligible": result["eligible"],
                        "accepted": result["accepted"],
                        "coverage": result["coverage"],
                        "invalid": result["invalid"],
                        "risk": result["risk"],
                        "cluster_bootstrap_risk_upper95": result[
                            "cluster_bootstrap_risk_upper95"
                        ],
                    }
                )


def _percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{100.0 * value:.2f}%"


def _write_verdict(path: Path, audit: Mapping[str, Any]) -> None:
    primary = audit["policies"]["full_contract"]
    overall = primary["overall"]
    family_lines = []
    for family, result in primary["families"].items():
        family_lines.append(
            f"- **{family}:** threshold `{result['threshold']:.12g}`, "
            f"{_percent(result['coverage'])} coverage, {_percent(result['risk'])} risk, "
            f"cluster upper 95% {_percent(result['cluster_bootstrap_risk_upper95'])}."
        )
    comparator_lines = []
    for condition, result in audit["policies"].items():
        if condition == "full_contract":
            continue
        if result["overall"] is None:
            comparator_lines.append(f"- **{condition}:** no complete family policy.")
        else:
            comparator_lines.append(
                f"- **{condition}:** {result['status'].upper()}, "
                f"{_percent(result['overall']['coverage'])} coverage and "
                f"{_percent(result['overall']['risk'])} risk."
            )
    path.write_text(
        "\n".join(
            [
                "# NOSTOS-0 BioSR v6 family-threshold development verdict",
                "",
                f"**Primary development gate:** {primary['status'].upper()}  ",
                "**Thresholds are structure-independent:** Yes  ",
                "**Confirmation data:** Not accessed  ",
                "**Confirmation access:** Not yet authorized; implementation freeze still required",
                "",
                "## Primary policy",
                "",
                f"The component-complete family policy retained {_percent(overall['coverage'])} of {overall['eligible']:,} eligible development cases with {_percent(overall['risk'])} observed risk. The structure-stratified reference-field cluster-bootstrap upper 95% risk was {_percent(overall['cluster_bootstrap_risk_upper95'])}.",
                "",
                *family_lines,
                "",
                "## Component-correct comparators",
                "",
                *comparator_lines,
                "",
                "Comparators no longer inherit hard abstentions from components they claim to omit. These are development-set comparisons; untouched confirmation must evaluate the locked policies without refitting.",
                "",
                "## Boundary",
                "",
                "A development pass permits construction of an immutable v6 confirmation package. It is not confirmation, clinical validation, biological ground truth or submission readiness. Axis-specific v5 variogram endpoints remain excluded; the intrinsic directional variogram is still a separate synthetic-development object.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    sources = []
    fields_by_stage: dict[str, set[str]] = {
        "score_design": set(),
        "threshold_calibration": set(),
    }
    for relative in config["development_sources"]:
        source, receipt = _source_rows(PROJECT_ROOT / relative)
        rows.extend(source)
        sources.append(receipt)
        fields_by_stage[receipt["stage"]].update(
            str(row["reference_group_id"]) for row in source
        )
    overlap = sorted(
        fields_by_stage["score_design"] & fields_by_stage["threshold_calibration"]
    )
    if overlap:
        raise ValueError(f"Development stages overlap: {overlap}")
    rules = config["family_threshold_selection"]
    parameters = {
        "family_map": config["endpoint_families"],
        "target_risk": float(rules["target_observed_risk"]),
        "maximum_risk_upper95": float(
            rules["maximum_cluster_bootstrap_risk_upper95"]
        ),
        "minimum_overall_coverage": float(rules["minimum_overall_coverage"]),
        "minimum_family_coverage": float(rules["minimum_family_coverage"]),
        "minimum_structure_coverage": float(
            rules["minimum_structure_family_coverage"]
        ),
        "draws": int(rules["bootstrap_replicates"]),
        "seed": int(rules["bootstrap_seed"]),
    }
    conditions = [
        "full_contract",
        "always_emit",
        "conventional_acquisition_qc",
        "physical_sampling_only",
        "perturbation_stability_only",
        "full_contract_without_qc",
        "full_contract_without_sampling",
        "full_contract_without_perturbation",
        "full_contract_without_identifiability",
    ]
    policies = {
        condition: select_family_policy(rows, condition=condition, **parameters)
        for condition in conditions
    }
    primary = policies["full_contract"]
    args.output.mkdir(parents=True, exist_ok=True)
    audit_path = args.output / "family_threshold_calibration.json"
    threshold_path = args.output / "family_thresholds_candidate.json"
    csv_path = args.output / "family_policy_comparison.csv"
    verdict_path = args.output / "DEVELOPMENT_VERDICT.md"
    threshold_candidate = {
        "schema_version": "nostos-family-threshold-candidate/1.0",
        "status": (
            "development_pass_not_yet_frozen_for_confirmation"
            if primary["status"] == "pass"
            else "development_fail"
        ),
        "condition": "full_contract",
        "raw_score": "full_contract",
        "family_map": config["endpoint_families"],
        "thresholds": {
            family: result["threshold"]
            for family, result in primary["families"].items()
            if result["status"] == "threshold_selected"
        },
        "structure_specific_thresholds": False,
        "confirmation_access_authorized": False,
    }
    threshold_path.write_text(
        json.dumps(threshold_candidate, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    audit = {
        "schema_version": "nostos-biosr-v6-family-threshold-development/1.0",
        "created_at_utc": _utc_now(),
        "status": (
            "development_pass_pending_implementation_freeze"
            if primary["status"] == "pass"
            else "development_fail"
        ),
        "config": _artifact(args.config),
        "sources": sources,
        "scope": {
            "reference_fields": len(
                {str(row["reference_group_id"]) for row in rows}
            ),
            "paired_acquisitions": len({str(row["pair_id"]) for row in rows}),
            "all_source_rows": len(rows),
            "score_design_fields": len(fields_by_stage["score_design"]),
            "threshold_calibration_fields": len(
                fields_by_stage["threshold_calibration"]
            ),
            "field_overlap": overlap,
        },
        "policy_semantics": rules["comparator_semantics"],
        "policies": policies,
        "threshold_candidate": threshold_candidate,
        "confirmation_archives_accessed": False,
        "confirmation_access_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    audit_path.write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_family_csv(csv_path, policies)
    _write_verdict(verdict_path, audit)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "scope": audit["scope"],
                "primary": primary,
                "comparators": {
                    key: {
                        "status": value["status"],
                        "overall": value["overall"],
                    }
                    for key, value in policies.items()
                    if key != "full_contract"
                },
                "artifacts": {
                    "audit": _artifact(audit_path),
                    "thresholds": _artifact(threshold_path),
                    "csv": _artifact(csv_path),
                    "verdict": _artifact(verdict_path),
                },
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
