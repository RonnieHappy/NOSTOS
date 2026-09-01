"""Independent arithmetic and provenance audit of the v1 selective-risk result.

This file intentionally does not import the production audit module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-selective-risk-baseline-v1/selective_risk_baseline.json"
OUTPUT = ROOT / "outputs/nostos0-selective-risk-baseline-v1-audit/audit.json"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _aurc(score: np.ndarray, invalid: np.ndarray) -> float:
    order = np.argsort(score, kind="mergesort")
    ordered_score = score[order]
    ordered_invalid = invalid[order]
    coverage = [0.0]
    risk = [0.0]
    cumulative = 0
    begin = 0
    while begin < len(order):
        end = begin + 1
        while end < len(order) and ordered_score[end] == ordered_score[begin]:
            end += 1
        cumulative += int(np.sum(ordered_invalid[begin:end]))
        coverage.append(end / len(order))
        risk.append(cumulative / end)
        begin = end
    return float(np.trapezoid(np.asarray(risk), np.asarray(coverage)))


def _select(score: np.ndarray, target: int) -> np.ndarray:
    order = np.argsort(score, kind="mergesort")
    ordered = score[order]
    boundaries: list[int] = []
    begin = 0
    while begin < len(order):
        end = begin + 1
        while end < len(order) and ordered[end] == ordered[begin]:
            end += 1
        boundaries.append(end)
        begin = end
    target = min(max(target, 1), len(order))
    distance = np.abs(np.asarray(boundaries) - target)
    chosen = int(np.flatnonzero(distance == np.min(distance))[-1])
    return order[: boundaries[chosen]]


def _close(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return bool(abs(left - right) <= tolerance)


def main() -> None:
    result: dict[str, Any] = json.loads(SOURCE.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    for domain in result["domains"]:
        source_checks = []
        for partition in ("development", "confirmation"):
            expected = domain[partition]["sha256"]
            observed = _file_hash(ROOT / domain[partition]["path"])
            source_checks.append(
                {
                    "partition": partition,
                    "expected_sha256": expected,
                    "observed_sha256": observed,
                    "pass": expected == observed,
                }
            )
        predictions = domain["predictions"]
        invalid = np.asarray([int(bool(row["invalid"])) for row in predictions], dtype=int)
        methods = sorted(predictions[0]["scores"])
        metric_checks = []
        for method in methods:
            score = np.asarray([float(row["scores"][method]) for row in predictions])
            selected = _select(score, int(domain["historical_nostos_accepted_count"]))
            stored = domain["summary"][method]
            observed_auc = _aurc(score, invalid)
            observed_risk = float(np.mean(invalid[selected]))
            metric_checks.append(
                {
                    "method": method,
                    "stored_aurc": stored["aurc"],
                    "recomputed_aurc": observed_auc,
                    "stored_matched_count": stored["matched_count"],
                    "recomputed_matched_count": int(len(selected)),
                    "stored_matched_risk": stored["matched_risk"],
                    "recomputed_matched_risk": observed_risk,
                    "pass": (
                        _close(float(stored["aurc"]), observed_auc)
                        and int(stored["matched_count"]) == len(selected)
                        and _close(float(stored["matched_risk"]), observed_risk)
                    ),
                }
            )
        case_ids = [row["case_id"] for row in predictions]
        group_count = len({row["group"] for row in predictions})
        structural = {
            "unique_case_ids": len(case_ids) == len(set(case_ids)),
            "prediction_rows_match_confirmation": len(predictions)
            == int(domain["confirmation"]["rows"]),
            "invalid_count_matches_confirmation": int(np.sum(invalid))
            == int(domain["confirmation"]["invalid"]),
            "group_count_matches_confirmation": group_count
            == int(domain["confirmation"]["independent_units"]),
            "label_blind_fingerprints_match": (
                domain["learned_comparator"]["confirmation_feature_sha256"]
                == domain["learned_comparator"]["label_complement_feature_sha256"]
                and bool(domain["learned_comparator"]["label_blind"])
            ),
        }
        checks.append(
            {
                "domain": domain["domain"],
                "source_checks": source_checks,
                "metric_checks": metric_checks,
                "structural_checks": structural,
                "pass": (
                    all(item["pass"] for item in source_checks)
                    and all(item["pass"] for item in metric_checks)
                    and all(structural.values())
                ),
            }
        )
    repeat = ROOT / "outputs/nostos0-selective-risk-baseline-v1-repeat/selective_risk_baseline.json"
    receipt = {
        "audit": "nostos-selective-risk-baseline-independent-audit/1.0",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _file_hash(SOURCE),
        "repeat_sha256": _file_hash(repeat),
        "repeat_files_byte_identical": SOURCE.read_bytes() == repeat.read_bytes(),
        "domains": checks,
    }
    receipt["status"] = (
        "pass"
        if receipt["repeat_files_byte_identical"] and all(item["pass"] for item in checks)
        else "fail"
    )
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "domains": {item["domain"]: item["pass"] for item in checks},
                "repeat_files_byte_identical": receipt["repeat_files_byte_identical"],
                "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if receipt["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
