"""Independent receipt-level audit of the frozen Heaton SHG confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr


ENDPOINTS = (
    "axial_resultant",
    "foreground_occupancy",
    "median_segment_straightness",
    "median_segment_length_um",
    "median_local_width_um",
)
PAIRING = {
    "axial_resultant": "coefficient_of_alignment",
    "foreground_occupancy": "detected_pixel_fraction",
    "median_segment_straightness": "median_straightness",
    "median_segment_length_um": "median_length_um",
    "median_local_width_um": "median_width_um",
}
POLICIES = (
    "acquisition_qc",
    "endpoint_qc",
    "without_scale_consistency",
    "without_threshold_consistency",
    "without_nested_consistency",
    "full_contract",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def predict(payload: dict[str, Any], value: float) -> float:
    x = np.asarray(payload["x_thresholds"], dtype=float)
    y = np.asarray(payload["y_thresholds"], dtype=float)
    if len(x) == 1:
        return float(y[0])
    return float(np.interp(value, x, y, left=y[0], right=y[-1]))


def annotate(rows: list[dict[str, Any]], lock: dict[str, Any], policy: str) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        clone = dict(row)
        clone["calibrated_risk"] = (
            1.0
            if bool(row["hard_abstention"])
            else predict(
                lock["risk_maps"][policy][row["endpoint"]],
                float(row["scores"][policy]),
            )
        )
        output.append(clone)
    return output


def accepted(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if not bool(row["hard_abstention"]) and float(row["calibrated_risk"]) <= threshold
    ]


def risk(rows: list[dict[str, Any]]) -> float:
    return float(np.mean([bool(row["invalid"]) for row in rows])) if rows else 1.0


def lowest(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (float(row["calibrated_risk"]), row["case_id"]))[:count]


def aurc(rows: list[dict[str, Any]]) -> float:
    ordered = sorted(rows, key=lambda row: (float(row["calibrated_risk"]), row["case_id"]))
    coverage = [0.0]
    risks = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        score = float(ordered[index]["calibrated_risk"])
        end = index
        while end < len(ordered) and float(ordered[end]["calibrated_risk"]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage.append(end / len(ordered))
        risks.append(invalid / end)
        index = end
    return float(np.trapezoid(np.asarray(risks), np.asarray(coverage)))


def correlations(clean: list[dict[str, Any]]) -> dict[str, float | None]:
    output: dict[str, float | None] = {}
    for endpoint in ENDPOINTS:
        x = [float(row["nostos"][endpoint]) for row in clean]
        y = [float(row["comparator"][PAIRING[endpoint]]) for row in clean]
        rho = float(spearmanr(x, y).statistic)
        output[endpoint] = rho if np.isfinite(rho) else None
    return output


def close(first: float | None, second: float | None, tolerance: float = 1e-12) -> bool:
    if first is None or second is None:
        return first is second
    return bool(abs(float(first) - float(second)) <= tolerance)


def audit(
    config_path: Path,
    protocol_path: Path,
    development_path: Path,
    lock_path: Path,
    development_dir: Path,
    exp10_stage: Path,
    exp15_stage: Path,
    confirmation_dir: Path,
    output: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    result_path = confirmation_dir / "confirmation.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    development_summary = development_dir / "development_summary.json"
    development_clean = development_dir / "development_clean_rows.jsonl"
    development_cases = development_dir / "development_perturbation_rows.jsonl"
    exp10_receipt_path = exp10_stage / "stage_receipt.json"
    exp15_receipt_path = exp15_stage / "stage_receipt.json"
    exp10_official_path = exp10_stage / "curvealign_official_receipt.json"
    exp15_official_path = exp15_stage / "curvealign_official_receipt.json"
    exp10_receipt = json.loads(exp10_receipt_path.read_text(encoding="utf-8"))
    exp15_receipt = json.loads(exp15_receipt_path.read_text(encoding="utf-8"))
    exp10_official = json.loads(exp10_official_path.read_text(encoding="utf-8"))
    exp15_official = json.loads(exp15_official_path.read_text(encoding="utf-8"))
    clean_path = confirmation_dir / "confirmation_clean_rows.jsonl"
    cases_path = confirmation_dir / "confirmation_perturbation_rows.jsonl"
    clean = read_jsonl(clean_path)
    rows = read_jsonl(cases_path)
    threshold = float(lock["maximum_predicted_risk"])
    policy_rows = {policy: annotate(rows, lock, policy) for policy in POLICIES}
    full = accepted(policy_rows["full_contract"], threshold)
    acquisition = lowest(policy_rows["acquisition_qc"], len(full))
    point_correlations = correlations(clean)
    operating = {}
    for policy, values in policy_rows.items():
        selected = accepted(values, threshold)
        operating[policy] = {
            "eligible": len(values),
            "accepted": len(selected),
            "coverage": len(selected) / len(values),
            "invalid": int(sum(bool(row["invalid"]) for row in selected)),
            "risk": risk(selected) if selected else None,
        }
    independent_aurc = {policy: aurc(values) for policy, values in policy_rows.items()}
    checks = {
        "lock_status_authorized": lock.get("status") == "locked_confirmation_authorized",
        "config_hash": lock.get("config_sha256") == sha256_file(config_path),
        "protocol_hash": lock.get("protocol_sha256") == sha256_file(protocol_path),
        "adapter_development_hash": lock.get("adapter_development_sha256") == sha256_file(development_path),
        "development_summary_hash": lock.get("development_summary_sha256") == sha256_file(development_summary),
        "development_clean_hash": lock.get("development_clean_rows_sha256") == sha256_file(development_clean),
        "development_cases_hash": lock.get("development_perturbation_rows_sha256") == sha256_file(development_cases),
        "development_confirmation_mice_disjoint": set(row["mouse"] for row in exp10_receipt["rows"]).isdisjoint(
            row["mouse"] for row in exp15_receipt["rows"]
        ),
        "stage_counts": exp10_receipt.get("fields") == 34 and exp15_receipt.get("fields") == 45,
        "stage_statuses": exp10_receipt.get("status") == "development_stage_parameters_locked"
        and exp15_receipt.get("status") == "confirmation_stage_parameters_locked",
        "official_receipts_complete": exp10_official.get("status") == "complete"
        and exp15_official.get("status") == "complete"
        and exp10_official.get("input_images") == 34
        and exp15_official.get("input_images") == 45,
        "confirmation_row_counts": len(clean) == 45 and len(rows) == 600,
        "confirmation_mice": len({row["mouse"] for row in rows}) == 8,
        "unique_case_ids": len({row["case_id"] for row in rows}) == len(rows),
        "result_lock_hash": result.get("lock_sha256") == sha256_file(lock_path),
        "result_stage_hash": result.get("exp15_stage_receipt_sha256") == sha256_file(exp15_receipt_path),
        "result_official_hash": result.get("exp15_official_receipt_sha256") == sha256_file(exp15_official_path),
        "point_correlations_reproduced": all(
            close(point_correlations[endpoint], result["summary"]["clean_correlations"][endpoint])
            for endpoint in ENDPOINTS
        ),
        "operating_points_reproduced": all(
            operating[policy] == result["summary"]["operating"][policy] for policy in POLICIES
        ),
        "aurc_reproduced": all(
            close(independent_aurc[policy], result["summary"]["risk_coverage_auc"][policy])
            for policy in POLICIES
        ),
        "matched_risk_reduction_reproduced": close(
            risk(acquisition) - risk(full),
            result["summary"]["matched_acquisition_qc"]["risk_reduction"],
        ),
        "failure_status_preserved": result.get("status") == "fail" and not all(result["success_gates"].values()),
    }
    payload = {
        "schema_version": "nostos.heaton_shg_confirmation_audit.v1",
        "status": "verified_failed_confirmation" if all(checks.values()) else "audit_failed",
        "checks": checks,
        "recomputed": {
            "clean_correlations": point_correlations,
            "operating": operating,
            "risk_coverage_auc": independent_aurc,
            "matched_risk_reduction_vs_acquisition_qc": risk(acquisition) - risk(full),
        },
        "scientific_verdict": (
            "The frozen Exp15 benchmark failed. Two of five clean endpoint pairs met the rho threshold; "
            "the calibrated policy retained only straightness cases at 20% coverage, so it cannot support "
            "the preregistered multi-endpoint transfer claim."
        ),
        "claim_boundary": config["claim_boundary"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--development-dir", type=Path, required=True)
    parser.add_argument("--exp10-stage", type=Path, required=True)
    parser.add_argument("--exp15-stage", type=Path, required=True)
    parser.add_argument("--confirmation-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        args.config.resolve(),
        args.protocol.resolve(),
        args.development.resolve(),
        args.lock.resolve(),
        args.development_dir.resolve(),
        args.exp10_stage.resolve(),
        args.exp15_stage.resolve(),
        args.confirmation_dir.resolve(),
        args.output.resolve(),
    )
    print(json.dumps({"status": result["status"], "checks": result["checks"]}, indent=2))


if __name__ == "__main__":
    main()
