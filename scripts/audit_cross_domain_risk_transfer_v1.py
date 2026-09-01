"""Independent provenance and arithmetic audit for cross-domain transfer v1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-cross-domain-risk-transfer-v1/transfer.json"
REPEAT = ROOT / "outputs/nostos0-cross-domain-risk-transfer-v1-repeat/transfer.json"
OUTPUT = ROOT / "outputs/nostos0-cross-domain-risk-transfer-v1-audit/audit.json"
SOURCE_PATHS = {
    "biosr_f_actin": (
        "outputs/nostos0-biosr-tensor-v9-scale-conditioned-development/development_tensor_cases_v9.jsonl",
        "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/tensor_cases.jsonl",
    ),
    "fmd_widefield": (
        "outputs/nostos0-fmd-widefield-v1-3-development/development_rows.jsonl",
        "outputs/nostos0-fmd-widefield-v1-3-confirmation/confirmation_rows.jsonl",
    ),
    "pshg_tiss_breast": (
        "outputs/nostos0-pshg-acquisition-shift-v1-development/development_rows.jsonl",
        "outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation_rows.jsonl",
    ),
    "tendon_pshg_xrd": (
        "outputs/nostos0-tlt-pshg-xrd-v1-locked-development/development_rows.jsonl",
        "outputs/nostos0-tlt-pshg-xrd-v1-confirmation/confirmation_rows.jsonl",
    ),
    "heaton_in_vivo_shg": (
        "outputs/nostos0-heaton-in-vivo-shg-v1-risk-development/development_perturbation_rows.jsonl",
        "outputs/nostos0-heaton-in-vivo-shg-v1-confirmation/confirmation_perturbation_rows.jsonl",
    ),
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _aurc(score: np.ndarray, invalid: np.ndarray) -> float:
    order = np.argsort(score, kind="mergesort")
    x = score[order]
    y = invalid[order]
    coverage = [0.0]
    risk = [0.0]
    cumulative = 0
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and x[stop] == x[start]:
            stop += 1
        cumulative += int(np.sum(y[start:stop]))
        coverage.append(stop / len(order))
        risk.append(cumulative / stop)
        start = stop
    return float(np.trapezoid(np.asarray(risk), np.asarray(coverage)))


def _select(score: np.ndarray, target: int) -> np.ndarray:
    order = np.argsort(score, kind="mergesort")
    x = score[order]
    boundaries: list[int] = []
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and x[stop] == x[start]:
            stop += 1
        boundaries.append(stop)
        start = stop
    target = min(max(target, 1), len(order))
    distances = np.abs(np.asarray(boundaries) - target)
    chosen = int(np.flatnonzero(distances == np.min(distances))[-1])
    return order[: boundaries[chosen]]


def _close(a: float, b: float) -> bool:
    return bool(abs(a - b) <= 1e-12)


def main() -> None:
    payload: dict[str, Any] = json.loads(SOURCE.read_text(encoding="utf-8"))
    domains = []
    for item in payload["domains"]:
        name = item["domain"]
        dev_path, conf_path = SOURCE_PATHS[name]
        source_checks = {
            "development_sha256": _hash(ROOT / dev_path)
            == item["development_source_sha256"],
            "confirmation_sha256": _hash(ROOT / conf_path)
            == item["confirmation_source_sha256"],
        }
        predictions = item["predictions"]
        invalid = np.asarray([int(bool(row["invalid"])) for row in predictions])
        methods = sorted(predictions[0]["scores"])
        metric_checks = []
        for method in methods:
            score = np.asarray([float(row["scores"][method]) for row in predictions])
            selected = _select(score, int(item["historical_nostos_accepted_count"]))
            stored = item["summary"][method]
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
        transfer = ("transfer_logistic", "transfer_boosted")
        recomputed_best = min(
            transfer, key=lambda method: (float(item["summary"][method]["aurc"]), method)
        )
        expected_corresponding = (
            "domain_logistic" if recomputed_best == "transfer_logistic" else "domain_boosted"
        )
        structural = {
            "unique_case_ids": len(predictions)
            == len({str(row["case_id"]) for row in predictions}),
            "row_count_matches": len(predictions) == int(item["confirmation_rows"]),
            "invalid_count_matches": int(np.sum(invalid))
            == int(item["confirmation_invalid"]),
            "group_count_matches": len({str(row["group"]) for row in predictions})
            == int(item["confirmation_independent_units"]),
            "geometry_channels_complete": all(
                set(row["shared_geometry"])
                == {"acquisition", "identifiability", "scale", "consistency"}
                and all(np.isfinite(float(value)) for value in row["shared_geometry"].values())
                for row in predictions
            ),
            "held_out_domain_absent": bool(item["held_out_development_absent"])
            and name not in item["transfer_model"]["training_domains"],
            "label_blind_fingerprints_match": (
                bool(item["transfer_model"]["label_blind"])
                and item["transfer_model"]["target_geometry_sha256"]
                == item["transfer_model"]["label_complement_geometry_sha256"]
            ),
            "best_transfer_recomputed": recomputed_best
            == item["better_transfer_model_descriptive"],
            "corresponding_model_recomputed": expected_corresponding
            == item["corresponding_domain_trained_model"],
        }
        domains.append(
            {
                "domain": name,
                "source_checks": source_checks,
                "metric_checks": metric_checks,
                "structural_checks": structural,
                "pass": (
                    all(source_checks.values())
                    and all(check["pass"] for check in metric_checks)
                    and all(structural.values())
                ),
            }
        )
    receipt = {
        "audit": "nostos-cross-domain-risk-transfer-independent-audit/1.0",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "repeat_sha256": _hash(REPEAT),
        "repeat_files_byte_identical": SOURCE.read_bytes() == REPEAT.read_bytes(),
        "domains": domains,
    }
    receipt["status"] = (
        "pass"
        if receipt["repeat_files_byte_identical"] and all(item["pass"] for item in domains)
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
                "domains": {item["domain"]: item["pass"] for item in domains},
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
