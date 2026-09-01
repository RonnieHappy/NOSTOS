"""Independent receipt audit for the locked TLT pSHG-XRD confirmation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr


SAMPLES = ("Sample2", "Sample4")
ZONES = ("NM", "EM", "LM")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _risk(rows: Sequence[Mapping[str, Any]]) -> float:
    return float(np.mean([bool(row["invalid"]) for row in rows])) if rows else 1.0


def _risk_coverage_auc(rows: Sequence[Mapping[str, Any]], score: str) -> float:
    ordered = sorted(rows, key=lambda row: (float(row[score]), str(row["case_id"])))
    coverage = [0.0]
    risk = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        value = float(ordered[index][score])
        end = index
        while end < len(ordered) and float(ordered[end][score]) == value:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage.append(end / len(ordered))
        risk.append(invalid / end)
        index = end
    return float(np.trapezoid(risk, coverage))


def _select_nearest_ties(
    rows: Sequence[Mapping[str, Any]], count: int, score: str
) -> list[Mapping[str, Any]]:
    ordered = sorted(rows, key=lambda row: (float(row[score]), str(row["case_id"])))
    groups: list[list[Mapping[str, Any]]] = []
    index = 0
    while index < len(ordered):
        value = float(ordered[index][score])
        end = index + 1
        while end < len(ordered) and float(ordered[end][score]) == value:
            end += 1
        groups.append(ordered[index:end])
        index = end
    cumulative = np.cumsum([len(group) for group in groups])
    distances = np.abs(cumulative - min(count, len(ordered)))
    candidates = np.flatnonzero(distances == np.min(distances))
    chosen = int(candidates[-1])
    return [row for group in groups[: chosen + 1] for row in group]


def _close(first: Any, second: Any, tolerance: float = 1e-12) -> bool:
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        return set(first) == set(second) and all(
            _close(first[key], second[key], tolerance) for key in first
        )
    if isinstance(first, list) and isinstance(second, list):
        return len(first) == len(second) and all(
            _close(left, right, tolerance) for left, right in zip(first, second, strict=True)
        )
    if isinstance(first, (float, int)) and isinstance(second, (float, int)):
        return bool(np.isclose(float(first), float(second), atol=tolerance, rtol=tolerance))
    return first == second


def _organization(clean: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def rho(values: Sequence[Mapping[str, Any]]) -> float:
        result = spearmanr(
            [row["organization_reference_mean_i2"] for row in values],
            [row["diagnostics"]["median_coherence"] for row in values],
        ).statistic
        return float(result) if np.isfinite(result) else 0.0

    return {
        "fields": len(clean),
        "pooled_spearman": rho(clean),
        "per_specimen_spearman": {
            sample: rho([row for row in clean if row["sample"] == sample])
            for sample in SAMPLES
        },
        "per_specimen_zone_means": {
            sample: {
                zone: {
                    "fields": len(
                        [row for row in clean if row["sample"] == sample and row["zone"] == zone]
                    ),
                    "nostos_median_coherence": float(
                        np.mean(
                            [
                                row["diagnostics"]["median_coherence"]
                                for row in clean
                                if row["sample"] == sample and row["zone"] == zone
                            ]
                        )
                    ),
                    "pshg_mean_i2": float(
                        np.mean(
                            [
                                row["organization_reference_mean_i2"]
                                for row in clean
                                if row["sample"] == sample and row["zone"] == zone
                            ]
                        )
                    ),
                }
                for zone in ZONES
            }
            for sample in SAMPLES
        },
    }


def _bootstrap(
    rows: Sequence[Mapping[str, Any]], threshold: float, draws: int, seed: int
) -> dict[str, Any]:
    by_sample = {sample: [row for row in rows if row["sample"] == sample] for sample in SAMPLES}
    rng = np.random.default_rng(seed)
    full_risk: list[float] = []
    differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    areas = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    for _ in range(draws):
        sampled: list[dict[str, Any]] = []
        for replicate, index in enumerate(rng.integers(0, 2, 2)):
            sample = SAMPLES[int(index)]
            for row in by_sample[sample]:
                sampled.append(
                    {
                        **row,
                        "case_id": f"bootstrap-{replicate}|{row['case_id']}",
                    }
                )
        full = [row for row in sampled if row["scores"]["full_contract"] <= threshold]
        value = _risk(full)
        full_risk.append(value)
        full_rows = [{**row, "score": row["scores"]["full_contract"]} for row in sampled]
        full_area = _risk_coverage_auc(full_rows, "score")
        for name in differences:
            comparator_rows = [{**row, "score": row["scores"][name]} for row in sampled]
            selected = _select_nearest_ties(comparator_rows, len(full), "score")
            differences[name].append(_risk(selected) - value)
            areas[name].append(_risk_coverage_auc(comparator_rows, "score") - full_area)

    def interval(values: Sequence[float]) -> list[float]:
        return [float(value) for value in np.quantile(values, (0.025, 0.975))]

    return {
        "draws_requested": draws,
        "draws_retained": len(full_risk),
        "unit": "specimen with nested fields and conditions retained",
        "full_risk_95": interval(full_risk),
        "matched_risk_difference_95": {
            name: interval(values) for name, values in differences.items()
        },
        "aurc_difference_95": {name: interval(values) for name, values in areas.items()},
        "caution": "Only two independent specimens; intervals are descriptive and not population-generalization evidence.",
    }


def audit_confirmation(
    project_root: Path,
    dataset_root: Path,
    lock_path: Path,
    result_root: Path,
    output: Path,
) -> dict[str, Any]:
    lock = _read_json(lock_path)
    config = _read_json(project_root / lock["config_path"])
    prelock = _read_json(project_root / lock["prelock_path"])
    result = _read_json(result_root / "confirmation.json")
    rows = _read_rows(result_root / "confirmation_rows.jsonl")
    checks: dict[str, bool] = {}

    for path_key, hash_key in (
        ("protocol_path", "protocol_sha256"),
        ("config_path", "config_sha256"),
        ("prelock_path", "prelock_sha256"),
        ("candidate_screen_path", "candidate_screen_sha256"),
        ("development_profile_path", "development_profile_sha256"),
        ("development_result_path", "development_result_sha256"),
        ("implementation_path", "implementation_sha256"),
        ("runner_path", "runner_sha256"),
    ):
        checks[f"lock_{hash_key}"] = _sha256(project_root / lock[path_key]) == lock[hash_key]
    checks["lock_sha256_in_result"] = _sha256(lock_path) == result["lock_sha256"]

    source_ok = True
    for sample in SAMPLES:
        for zone in ZONES:
            name = f"{sample}{zone}.mat"
            expected = prelock["files"][name]
            path = dataset_root / name
            source_ok &= path.stat().st_size == expected["bytes"]
            source_ok &= hashlib.md5(path.read_bytes()).hexdigest() == expected["md5"]
    checks["source_files"] = bool(source_ok)

    conditions = {condition["id"] for condition in config["conditions"]}
    checks["unique_case_ids"] = len(rows) == len({row["case_id"] for row in rows})
    checks["condition_set"] = {row["condition"] for row in rows} == conditions
    checks["rectangular_field_condition_matrix"] = len(rows) == len(
        {row["field_id"] for row in rows}
    ) * len(conditions)
    measurement = config["measurement"]
    checks["invalid_flags"] = all(
        bool(row["invalid"])
        == (
            row["median_error_degrees"] > measurement["invalid_median_error_degrees"]
            or row["p75_error_degrees"] > measurement["invalid_p75_error_degrees"]
        )
        for row in rows
    )
    checks["policy_scores"] = all(
        all(
            np.isclose(
                row["scores"][name],
                max(row["diagnostics"]["components"][part] for part in parts),
            )
            for name, parts in config["policies"].items()
        )
        for row in rows
    )

    threshold = config["operating_rule"]["maximum_full_contract_score"]
    full = [row for row in rows if row["scores"]["full_contract"] <= threshold]
    matched = {
        "full_contract": {
            "accepted": len(full),
            "coverage": len(full) / len(rows),
            "invalid": sum(bool(row["invalid"]) for row in full),
            "risk": _risk(full),
            "score_threshold": threshold,
        }
    }
    for name in ("acquisition_qc", "endpoint_qc"):
        candidates = [{**row, "score": row["scores"][name]} for row in rows]
        selected = _select_nearest_ties(candidates, len(full), "score")
        matched[name] = {
            "accepted": len(selected),
            "coverage": len(selected) / len(rows),
            "invalid": sum(bool(row["invalid"]) for row in selected),
            "risk": _risk(selected),
            "score_threshold": max(row["score"] for row in selected),
        }
    checks["matched_summary"] = _close(matched, result["summary"]["matched_coverage"])

    aurc = {
        name: _risk_coverage_auc(
            [{**row, "score": row["scores"][name]} for row in rows], "score"
        )
        for name in config["policies"]
    }
    checks["risk_coverage_auc"] = _close(aurc, result["summary"]["risk_coverage_auc"])
    clean = [row for row in rows if row["condition"] == "clean"]
    organization = _organization(clean)
    checks["organization"] = _close(organization, result["summary"]["organization"])

    reconstructed_bootstrap = _bootstrap(
        rows, threshold, config["bootstrap"]["draws"], config["bootstrap"]["seed"]
    )
    checks["bootstrap"] = _close(reconstructed_bootstrap, result["bootstrap"])

    payload = [
        (row["case_id"], bool(row["scores"]["full_contract"] <= threshold))
        for row in rows
    ]
    decision_hash = hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    checks["decision_hash"] = (
        decision_hash == result["label_blindness_audit"]["before_sha256"]
        == result["label_blindness_audit"]["after_reference_mutation_sha256"]
    )
    checks["reported_status_matches_gates"] = (
        result["status"] == ("pass" if all(result["success_gates"].values()) else "fail")
    )
    checks["known_failed_gates_exact"] = {
        name for name, passed in result["success_gates"].items() if not passed
    } == {"full_coverage", "clean_preservation"}

    status = "verified_qualified_fail" if all(checks.values()) and result["status"] == "fail" else "audit_failed"
    audit = {
        "schema_version": "nostos.tlt_pshg_xrd.audit.v1",
        "status": status,
        "checks": checks,
        "verified_checks": sum(bool(value) for value in checks.values()),
        "total_checks": len(checks),
        "reconstructed": {
            "matched_coverage": matched,
            "risk_coverage_auc": aurc,
            "organization": organization,
            "bootstrap": reconstructed_bootstrap,
            "decision_hash": decision_hash,
        },
        "interpretation": "The computation and preregistered failure are verified. Strong selective-risk and organization-recovery results do not override the missed coverage gates.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return audit

