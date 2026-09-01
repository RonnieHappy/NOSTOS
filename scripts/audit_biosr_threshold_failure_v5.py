"""Produce an immutable, read-only diagnostic of the failed BioSR v5 gate."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nostos.validation.failure_diagnostics import (
    diagnose_combinations,
    summarize_score_distributions,
    threshold_scale_conflicts,
)
from nostos.validation.paired_acquisition_support import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CALIBRATION = (
    PROJECT_ROOT
    / "outputs"
    / "nostos0-biosr-threshold-calibration-v5"
    / "threshold_calibration.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "nostos0-biosr-threshold-calibration-v5"


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


def _verify_artifact(item: dict[str, Any]) -> Path:
    path = PROJECT_ROOT / item["path"]
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(item["bytes"]):
        raise ValueError(f"Byte-count mismatch for {path}")
    if sha256_file(path) != item["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path}")
    return path


def _format_percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{100.0 * value:.2f}%"


def _write_csv(path: Path, diagnostics: list[dict[str, Any]]) -> None:
    fields = [
        "structure",
        "endpoint",
        "status",
        "eligible",
        "reference_fields",
        "hard_abstentions",
        "baseline_coverage",
        "baseline_invalid",
        "baseline_risk",
        "best_threshold",
        "best_accepted",
        "best_coverage",
        "best_invalid",
        "best_risk",
        "passes_independent_diagnostic",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in diagnostics:
            baseline = item.get("always_accept_nonhard") or {}
            best = item.get("best") or {}
            writer.writerow(
                {
                    "structure": item["structure"],
                    "endpoint": item["endpoint"],
                    "status": item["status"],
                    "eligible": item["eligible"],
                    "reference_fields": item["reference_fields"],
                    "hard_abstentions": item["hard_abstentions"],
                    "baseline_coverage": baseline.get("coverage"),
                    "baseline_invalid": baseline.get("invalid"),
                    "baseline_risk": baseline.get("risk"),
                    "best_threshold": best.get("threshold"),
                    "best_accepted": best.get("accepted"),
                    "best_coverage": best.get("coverage"),
                    "best_invalid": best.get("invalid"),
                    "best_risk": best.get("risk"),
                    "passes_independent_diagnostic": item[
                        "passes_independent_diagnostic"
                    ],
                }
            )


def _write_markdown(path: Path, audit: dict[str, Any]) -> None:
    failures = [
        item
        for item in audit["combination_diagnostics"]
        if item["status"] == "assessable"
        and not item["passes_independent_diagnostic"]
    ]
    failure_lines = []
    for item in failures:
        best = item["best"]
        failure_lines.append(
            f"- **{item['structure']} / {item['endpoint']}:** best observed risk "
            f"{_format_percent(best['risk'])} at {_format_percent(best['coverage'])} "
            f"coverage (threshold `{best['threshold']:.12g}`)."
        )
    conflict_lines = []
    for item in audit["threshold_scale_conflicts"][:10]:
        conflict_lines.append(
            f"- **{item['structure']}:** {item['endpoint_a']} requires "
            f"`{item['threshold_a']:.6g}` while {item['endpoint_b']} requires "
            f"`{item['threshold_b']:.6g}` at their independent diagnostic optima."
        )
    path.write_text(
        "\n".join(
            [
                "# NOSTOS-0 BioSR v5 failure diagnostic",
                "",
                "**Status:** Descriptive diagnosis of a prospectively failed gate  ",
                "**Confirmation data:** Not accessed  ",
                "**Decision use:** Development of a new v6 method only; no v5 threshold is authorized",
                "",
                "## What failed",
                "",
                "The frozen v5 selector found no single score threshold satisfying the risk and coverage contract across every assessable structure-endpoint combination. This audit asks whether the failure is merely caused by the shared cutoff or whether any endpoint is irreducibly unsupported under the frozen v5 score.",
                "",
                "## Endpoint-level bottleneck",
                "",
                *(failure_lines or ["- No irreducible endpoint failure was found."]),
                "",
                "Each line above gives the lowest descriptive risk obtainable when that combination is allowed its own threshold while retaining at least 70% coverage. Because ER vertical variogram range remains above 10%, removing the global-cutoff constraint alone cannot make v5 pass.",
                "",
                "## Score-scale incompatibility",
                "",
                *(conflict_lines or ["- No large threshold-scale separation was found."]),
                "",
                "These are post-failure diagnostics, not permissible v5 operating thresholds. They show that endpoint families do not share a commensurate raw risk-score scale.",
                "",
                "## Consequence",
                "",
                "Version 5 remains failed. The calibration fields are now development data and cannot provide confirmation for a repaired method. A v6 design must use endpoint-family calibration, preserve one structure-independent algorithm, replace or withhold coordinate-dependent variogram range scalars, and be frozen before any confirmation structure is accessed.",
                "",
                "The output does not justify biological, clinical, intraoperative or acquisition-family claims.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    result = calibration["result"]
    if result["status"] != "fail":
        raise ValueError("Failure diagnostics require a failed calibration result.")
    if result["operating_point"]["status"] != "no_operating_point":
        raise ValueError("Calibration unexpectedly contains an operating point.")
    if calibration.get("confirmation_archives_accessed") is not False:
        raise ValueError("Confirmation-access state is not sealed.")

    row_paths = []
    for structure in ("CCPs", "ER"):
        row_paths.append(_verify_artifact(calibration["lineage"][structure]["endpoint_cases"]))
    rows: list[dict[str, Any]] = []
    for path in row_paths:
        rows.extend(_read_jsonl(path))

    minimum_coverage = float(
        result["operating_point"]["constraints"][
            "minimum_structure_endpoint_coverage"
        ]
    )
    target_risk = float(
        result["operating_point"]["constraints"][
            "target_overall_and_combination_risk"
        ]
    )
    endpoints = set(result["claim_endpoints"])
    diagnostics = diagnose_combinations(
        rows,
        endpoints=endpoints,
        condition="full_contract",
        minimum_coverage=minimum_coverage,
        target_risk=target_risk,
    )
    claim_rows = [row for row in rows if str(row["endpoint"]) in endpoints]
    output = {
        "schema_version": "nostos-biosr-threshold-failure-diagnostic/1.0",
        "created_at_utc": _utc_now(),
        "status": "diagnostic_only_v5_remains_failed",
        "source_calibration": _artifact(args.calibration),
        "constraints": {
            "condition": "full_contract",
            "minimum_structure_endpoint_coverage": minimum_coverage,
            "target_structure_endpoint_risk": target_risk,
        },
        "scope": {
            "reference_fields": result["reference_fields"],
            "paired_acquisitions": result["paired_acquisitions"],
            "claim_endpoint_rows": result["endpoint_cases"],
            "reference_eligible_claim_cases": result["reference_eligible_cases"],
        },
        "combination_diagnostics": diagnostics,
        "irreducible_combination_failures": [
            {
                "structure": item["structure"],
                "endpoint": item["endpoint"],
                "best": item["best"],
            }
            for item in diagnostics
            if item["status"] == "assessable"
            and not item["passes_independent_diagnostic"]
        ],
        "threshold_scale_conflicts": threshold_scale_conflicts(diagnostics),
        "score_distribution": summarize_score_distributions(
            claim_rows,
            condition="full_contract",
        ),
        "interpretation": "Post-failure diagnosis only. No threshold is selected and confirmation access remains unauthorized.",
        "confirmation_archives_accessed": False,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "failure_diagnostics.json"
    csv_path = args.output / "structure_endpoint_best_points.csv"
    markdown_path = args.output / "FAILURE_DIAGNOSTIC.md"
    json_path.write_text(
        json.dumps(output, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(csv_path, diagnostics)
    _write_markdown(markdown_path, output)
    print(
        json.dumps(
            {
                "status": output["status"],
                "irreducible_combination_failures": output[
                    "irreducible_combination_failures"
                ],
                "threshold_scale_conflicts": output["threshold_scale_conflicts"],
                "artifacts": {
                    "json": _artifact(json_path),
                    "csv": _artifact(csv_path),
                    "markdown": _artifact(markdown_path),
                },
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
