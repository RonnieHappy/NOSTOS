"""Benchmark v6 endpoint-family risk calibration on disclosed development fields."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from nostos.validation.family_risk_calibration import (
    brier_score,
    calibrated_operating_summary,
    cross_fitted_family_risk,
    expected_calibration_error,
    logarithmic_loss,
    risk_coverage_auc,
)
from nostos.validation.paired_acquisition_support import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "paired_acquisition_support_v6_development.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "outputs" / "nostos0-biosr-v6-family-calibration-development"
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
    if receipt.get("stage") not in {"score_design", "threshold_calibration"}:
        raise ValueError(f"Unsupported development stage in {receipt_path}")
    endpoint_path = receipt_path.parent / "endpoint_cases.jsonl"
    pair_index_path = receipt_path.parent / "pair_index.json"
    if sha256_file(endpoint_path) != receipt["artifacts"]["endpoint_cases_sha256"]:
        raise ValueError(f"Endpoint hash mismatch in {receipt_path}")
    if sha256_file(pair_index_path) != receipt["artifacts"]["pair_index_sha256"]:
        raise ValueError(f"Pair-index hash mismatch in {receipt_path}")
    return _read_jsonl(endpoint_path), {
        "stage": receipt["stage"],
        "structure": receipt["structure"],
        "archive_receipt": _artifact(receipt_path),
        "endpoint_cases": _artifact(endpoint_path),
        "pair_index": _artifact(pair_index_path),
        "implementation_sha256": receipt["implementation"]["sha256"],
    }


def _gate(
    summary: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    rules = config["development_gate"]
    combinations = summary["combinations"]
    combination_results = [
        {
            **item,
            "passes": bool(
                item["coverage"] >= float(rules["minimum_structure_family_coverage"])
                and item["risk"] is not None
                and item["risk"]
                <= float(rules["maximum_observed_overall_and_structure_family_risk"])
            ),
        }
        for item in combinations
    ]
    overall = bool(
        summary["coverage"] >= float(rules["minimum_overall_coverage"])
        and summary["risk"] is not None
        and summary["risk"]
        <= float(rules["maximum_observed_overall_and_structure_family_risk"])
    )
    return {
        "status": "pass" if overall and all(item["passes"] for item in combination_results) else "fail",
        "overall_passes": overall,
        "structure_family_results": combination_results,
        "rules": rules,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def _write_candidate_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    fields = [
        "bins",
        "brier_score",
        "logarithmic_loss",
        "expected_calibration_error",
        "risk_coverage_auc",
        "coverage_at_risk_cutoff",
        "observed_risk_at_cutoff",
        "accepted_at_cutoff",
        "development_gate_status",
        "selected",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in candidates:
            operating = item["operating_summary"]
            writer.writerow(
                {
                    "bins": item["bins"],
                    "brier_score": item["brier_score"],
                    "logarithmic_loss": item["logarithmic_loss"],
                    "expected_calibration_error": item[
                        "expected_calibration_error"
                    ],
                    "risk_coverage_auc": item["risk_coverage_auc"],
                    "coverage_at_risk_cutoff": operating["coverage"],
                    "observed_risk_at_cutoff": operating["risk"],
                    "accepted_at_cutoff": operating["accepted"],
                    "development_gate_status": item["development_gate"]["status"],
                    "selected": item["selected"],
                }
            )


def _percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{100.0 * value:.2f}%"


def _write_verdict(path: Path, audit: Mapping[str, Any]) -> None:
    selected = audit["selected_candidate"]
    operating = selected["operating_summary"]
    failed = [
        item
        for item in selected["development_gate"]["structure_family_results"]
        if not item["passes"]
    ]
    failed_lines = [
        f"- {item['structure']} / {item['endpoint_family']}: "
        f"{_percent(item['coverage'])} coverage, {_percent(item['risk'])} risk."
        for item in failed
    ]
    path.write_text(
        "\n".join(
            [
                "# NOSTOS-0 v6 family-calibration development verdict",
                "",
                "**Analysis role:** Transparent post-v5-failure development  ",
                f"**Selected candidate:** {selected['bins']} quantile bins  ",
                f"**Development gate:** {selected['development_gate']['status'].upper()}  ",
                "**Confirmation data:** Not accessed",
                "",
                "## Cross-fitted result",
                "",
                f"The selected candidate was chosen by minimum out-of-field Brier score, not by gate status. At the common calibrated-risk cutoff of 10%, it retained {_percent(operating['coverage'])} of eligible cases with {_percent(operating['risk'])} observed risk.",
                "",
                f"Cross-fitted Brier score was {selected['brier_score']:.6f}; logarithmic loss was {selected['logarithmic_loss']:.6f}; expected calibration error was {selected['expected_calibration_error']:.6f}; AURC was {selected['risk_coverage_auc']:.6f}.",
                "",
                "## Failing structure–family combinations",
                "",
                *(failed_lines or ["- None under the descriptive development rules."]),
                "",
                "## Boundary",
                "",
                "This benchmark may select a calibration architecture for a later v6 freeze. It is not confirmation and cannot authorize Microtubule or F-actin access. The axis-specific v5 variogram endpoints were removed because their definition failed; the new intrinsic directional variogram remains in synthetic development and is not silently substituted into these results.",
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
    source_rows: list[dict[str, Any]] = []
    sources = []
    stage_groups: dict[str, set[str]] = {"score_design": set(), "threshold_calibration": set()}
    for relative in config["development_sources"]:
        rows, receipt = _source_rows(PROJECT_ROOT / relative)
        source_rows.extend(rows)
        sources.append(receipt)
        stage_groups[receipt["stage"]].update(
            str(row["reference_group_id"]) for row in rows
        )
    overlap = sorted(stage_groups["score_design"] & stage_groups["threshold_calibration"])
    if overlap:
        raise ValueError(f"Pilot and threshold development fields overlap: {overlap}")
    observed_structures = {str(row["structure"]) for row in source_rows}
    if observed_structures != {"CCPs", "ER"}:
        raise ValueError(f"Unexpected structures: {observed_structures}")

    candidate_results: list[dict[str, Any]] = []
    candidate_rows: dict[int, list[dict[str, Any]]] = {}
    candidate_maps: dict[int, dict[str, Any]] = {}
    method = config["candidate_calibration"]
    risk_cutoff = float(config["development_gate"]["maximum_calibrated_risk"])
    for bins in method["candidate_bin_counts"]:
        rows, maps = cross_fitted_family_risk(
            source_rows,
            family_map=config["endpoint_families"],
            raw_score=method["raw_score"],
            bins=int(bins),
            folds=int(method["cross_fitting_folds"]),
            seed=int(method["cross_fitting_seed"]),
            prior_alpha=float(method["prior_alpha"]),
            prior_beta=float(method["prior_beta"]),
        )
        nonhard = [row for row in rows if not bool(row["hard_abstention"])]
        operating = calibrated_operating_summary(
            rows,
            maximum_predicted_risk=risk_cutoff,
        )
        gate = _gate(operating, config)
        candidate_rows[int(bins)] = rows
        candidate_maps[int(bins)] = {
            family: risk_map.to_dict() for family, risk_map in maps.items()
        }
        candidate_results.append(
            {
                "bins": int(bins),
                "brier_score": brier_score(nonhard, score_key="calibrated_risk"),
                "logarithmic_loss": logarithmic_loss(
                    nonhard,
                    score_key="calibrated_risk",
                ),
                "expected_calibration_error": expected_calibration_error(
                    nonhard,
                    score_key="calibrated_risk",
                ),
                "risk_coverage_auc": risk_coverage_auc(
                    rows,
                    score_key="calibrated_risk",
                ),
                "operating_summary": operating,
                "development_gate": gate,
                "selected": False,
            }
        )
    selected = min(
        candidate_results,
        key=lambda item: (
            item["brier_score"],
            item["logarithmic_loss"],
            item["bins"],
        ),
    )
    selected["selected"] = True
    selected_bins = int(selected["bins"])
    selected_rows = candidate_rows[selected_bins]
    selected_maps = candidate_maps[selected_bins]

    args.output.mkdir(parents=True, exist_ok=True)
    rows_path = args.output / "selected_cross_fitted_rows.jsonl"
    maps_path = args.output / "selected_final_risk_maps.json"
    audit_path = args.output / "candidate_benchmark.json"
    csv_path = args.output / "candidate_metrics.csv"
    verdict_path = args.output / "DEVELOPMENT_VERDICT.md"
    _write_jsonl(rows_path, selected_rows)
    maps_path.write_text(
        json.dumps(
            {
                "schema_version": "nostos-family-risk-map-candidate/1.0",
                "status": "development_candidate_not_frozen_for_confirmation",
                "selected_bins": selected_bins,
                "raw_score": method["raw_score"],
                "endpoint_families": config["endpoint_families"],
                "risk_maps": selected_maps,
                "structure_is_predictor": False,
                "confirmation_access_authorized": False,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    audit = {
        "schema_version": "nostos-biosr-v6-family-calibration-development/1.0",
        "created_at_utc": _utc_now(),
        "status": "development_complete_candidate_selected",
        "config": _artifact(args.config),
        "sources": sources,
        "scope": {
            "reference_fields": len(
                {str(row["reference_group_id"]) for row in source_rows}
            ),
            "paired_acquisitions": len({str(row["pair_id"]) for row in source_rows}),
            "all_source_rows": len(source_rows),
            "score_design_fields": len(stage_groups["score_design"]),
            "threshold_calibration_fields": len(stage_groups["threshold_calibration"]),
            "field_overlap": overlap,
        },
        "candidate_selection_rule": method["selection_rule"],
        "candidate_results": candidate_results,
        "selected_candidate": selected,
        "selected_maps": selected_maps,
        "removed_v5_endpoints": config["excluded_v5_endpoints"],
        "intrinsic_variogram_status": config["intrinsic_variogram"],
        "confirmation_archives_accessed": False,
        "confirmation_access_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    audit_path.write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_candidate_csv(csv_path, candidate_results)
    _write_verdict(verdict_path, audit)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "scope": audit["scope"],
                "selected_candidate": selected,
                "artifacts": {
                    "audit": _artifact(audit_path),
                    "rows": _artifact(rows_path),
                    "maps": _artifact(maps_path),
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
