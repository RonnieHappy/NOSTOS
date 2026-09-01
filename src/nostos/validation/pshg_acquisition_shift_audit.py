"""Independent audit of the frozen PSHG acquisition-shift confirmation.

This module intentionally does not import the confirmation implementation. It
reconstructs the hash split, calibration decisions, risk summaries, bootstrap
intervals, and label-blindness receipt directly from frozen artifacts.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np


POLICIES = (
    "acquisition_qc",
    "endpoint_qc",
    "without_scale_consistency",
    "without_split_consistency",
    "full_contract",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def independent_split(names: Sequence[str], *, salt: str, development: int) -> dict[str, list[str]]:
    ordered = sorted(
        {str(name) for name in names},
        key=lambda name: hashlib.sha256(f"{salt}|{name}".encode()).hexdigest(),
    )
    return {"development": ordered[:development], "confirmation": ordered[development:]}


def _predict(raw: float, risk_map: Mapping[str, Any]) -> float:
    x = np.asarray(risk_map["x_thresholds"], dtype=float)
    y = np.asarray(risk_map["y_thresholds"], dtype=float)
    if len(x) == 1:
        return float(y[0])
    return float(np.interp(raw, x, y, left=y[0], right=y[-1]))


def _aurc(rows: Sequence[Mapping[str, Any]], score_key: str = "calibrated_risk") -> float:
    ordered = sorted(rows, key=lambda row: (float(row[score_key]), str(row["case_id"])))
    coverage = [0.0]
    risk = [0.0]
    invalid = 0
    index = 0
    while index < len(ordered):
        score = float(ordered[index][score_key])
        end = index
        while end < len(ordered) and float(ordered[end][score_key]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        coverage.append(end / len(ordered))
        risk.append(invalid / end)
        index = end
    return float(np.trapezoid(np.asarray(risk), np.asarray(coverage)))


def _lowest(rows: Sequence[Mapping[str, Any]], count: int) -> list[Mapping[str, Any]]:
    return sorted(rows, key=lambda row: (float(row["calibrated_risk"]), str(row["case_id"])))[:count]


def _risk(rows: Sequence[Mapping[str, Any]]) -> float:
    return float(np.mean([bool(row["invalid"]) for row in rows])) if rows else 1.0


def _operating(rows: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    accepted = [row for row in rows if float(row["calibrated_risk"]) <= threshold]
    invalid = sum(bool(row["invalid"]) for row in accepted)
    return {
        "eligible": len(rows),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(rows),
        "invalid": int(invalid),
        "risk": float(invalid / len(accepted)) if accepted else None,
    }


def _decision_hash(rows: Sequence[Mapping[str, Any]], threshold: float) -> str:
    payload = [
        (str(row["case_id"]), bool(float(row["calibrated_risk"]) <= threshold))
        for row in rows
    ]
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resample(rows: Sequence[Mapping[str, Any]], indices: np.ndarray, rois: Sequence[str]) -> list[dict[str, Any]]:
    by_roi: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_roi.setdefault(str(row["roi"]), []).append(row)
    output: list[dict[str, Any]] = []
    for replicate, index in enumerate(indices):
        roi = rois[int(index)]
        for row in by_roi[roi]:
            clone = dict(row)
            clone["case_id"] = f"bootstrap-{replicate}|{row['case_id']}"
            output.append(clone)
    return output


def _interval(values: Sequence[float]) -> list[float]:
    return [float(value) for value in np.quantile(np.asarray(values), (0.025, 0.975))]


def _bootstrap(
    policy_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    threshold: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    rois = sorted({str(row["roi"]) for row in policy_rows["full_contract"]})
    rng = np.random.default_rng(seed)
    full_risks: list[float] = []
    risk_differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    aurc_differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    for _ in range(draws):
        indices = rng.integers(0, len(rois), len(rois))
        sampled = {name: _resample(rows, indices, rois) for name, rows in policy_rows.items()}
        selected = [
            row
            for row in sampled["full_contract"]
            if float(row["calibrated_risk"]) <= threshold
        ]
        if not selected:
            continue
        full_risk = _risk(selected)
        full_risks.append(full_risk)
        count = len(selected)
        full_aurc = _aurc(sampled["full_contract"])
        for name in risk_differences:
            risk_differences[name].append(_risk(_lowest(sampled[name], count)) - full_risk)
            aurc_differences[name].append(_aurc(sampled[name]) - full_aurc)
    return {
        "draws_requested": draws,
        "draws_retained": len(full_risks),
        "full_risk_95": _interval(full_risks),
        "matched_risk_difference_95": {
            name: _interval(values) for name, values in risk_differences.items()
        },
        "aurc_difference_95": {
            name: _interval(values) for name, values in aurc_differences.items()
        },
    }


def _close(left: Any, right: Any, *, atol: float = 1e-12) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(_close(left[key], right[key], atol=atol) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_close(a, b, atol=atol) for a, b in zip(left, right, strict=True))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(np.isclose(float(left), float(right), rtol=0.0, atol=atol))
    return left == right


def _source_receipt(dataset_root: Path, manifest: Mapping[str, Any], confirmation_rois: set[str]) -> dict[str, Any]:
    selected = [entry for entry in manifest["files"] if str(entry["roi"]) in confirmation_rois]
    mismatches: list[dict[str, Any]] = []
    for entry in selected:
        path = dataset_root / str(entry["roi"]) / str(entry["name"])
        observed = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
            "sha256": _sha256(path) if path.exists() else None,
        }
        if not observed["exists"] or observed["bytes"] != int(entry["bytes"]) or observed["sha256"] != entry["sha256"]:
            mismatches.append({"path": path.as_posix(), "expected": dict(entry), "observed": observed})
    return {
        "files_expected": len(selected),
        "files_verified": len(selected) - len(mismatches),
        "bytes_verified": int(sum(int(entry["bytes"]) for entry in selected if not any(item["expected"] == entry for item in mismatches))),
        "mismatches": mismatches,
    }


def run_audit(
    *,
    dataset_root: Path,
    config_path: Path,
    protocol_path: Path,
    profile_path: Path,
    lock_path: Path,
    result_path: Path,
    rows_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    config = _load_json(config_path)
    profile = _load_json(profile_path)
    lock = _load_json(lock_path)
    result = _load_json(result_path)
    rows = _load_jsonl(rows_path)
    manifest_path = dataset_root / "download_manifest.json"
    manifest = _load_json(manifest_path)
    conditions = [str(item["id"]) for item in config["conditions"]]
    names = sorted(path.name for path in dataset_root.iterdir() if path.is_dir())
    split = independent_split(
        names,
        salt=str(config["split"]["salt"]),
        development=int(config["split"]["development_rois"]),
    )
    confirmation = set(split["confirmation"])
    development = set(split["development"])

    checks: dict[str, bool] = {}
    checks["protocol_hash"] = _sha256(protocol_path) == lock["protocol_sha256"]
    checks["config_hash"] = _sha256(config_path) == lock["config_sha256"]
    checks["profile_hash"] = _sha256(profile_path) == lock["profile_sha256"]
    checks["manifest_hash"] = _sha256(manifest_path) == lock["source_manifest_sha256"]
    checks["lock_hash_in_result"] = _sha256(lock_path) == result["lock_sha256"]
    checks["split_matches_lock_profile_result"] = split == lock["split"] == profile["split"] == result["split"]
    checks["split_exact_and_disjoint"] = (
        len(confirmation) == int(config["split"]["confirmation_rois"])
        and len(development) == int(config["split"]["development_rois"])
        and confirmation.isdisjoint(development)
    )
    expected_cases = {(roi, condition) for roi in confirmation for condition in conditions}
    observed_cases = [(str(row["roi"]), str(row["condition"])) for row in rows]
    checks["case_matrix_complete"] = (
        len(rows) == len(expected_cases)
        and set(observed_cases) == expected_cases
        and all(count == 1 for count in Counter(observed_cases).values())
    )
    checks["development_excluded"] = all(str(row["roi"]) not in development for row in rows)
    median_cut = float(config["measurement"]["invalid_median_error_degrees"])
    p75_cut = float(config["measurement"]["invalid_p75_error_degrees"])
    checks["invalidity_recomputed"] = all(
        bool(row["invalid"])
        == (float(row["median_error_degrees"]) > median_cut or float(row["p75_error_degrees"]) > p75_cut)
        for row in rows
    )
    checks["policy_component_semantics"] = (
        "scale_consistency" not in config["policies"]["without_scale_consistency"]
        and "split_stack" not in config["policies"]["without_split_consistency"]
        and set(config["policies"]["full_contract"])
        == {"acquisition_qc", "coherence", "scale_consistency", "split_stack"}
    )
    checks["deployment_reference_blind"] = profile.get("reference_values_available_at_deployment") is False

    policy_rows: dict[str, list[dict[str, Any]]] = {}
    for policy in POLICIES:
        annotated: list[dict[str, Any]] = []
        for row in rows:
            component_values = row["diagnostics"]["components"]
            expected_score = max(float(component_values[name]) for name in config["policies"][policy])
            if not np.isclose(float(row["scores"][policy]), expected_score, rtol=0.0, atol=1e-12):
                checks[f"raw_score_{policy}"] = False
            clone = dict(row)
            clone["calibrated_risk"] = _predict(float(row["scores"][policy]), profile["risk_maps"][policy])
            annotated.append(clone)
        checks.setdefault(f"raw_score_{policy}", True)
        policy_rows[policy] = annotated

    threshold = float(profile["maximum_predicted_risk"])
    operating = {name: _operating(values, threshold) for name, values in policy_rows.items()}
    operating["always_emit"] = {
        "eligible": len(rows),
        "accepted": len(rows),
        "coverage": 1.0,
        "invalid": int(sum(bool(row["invalid"]) for row in rows)),
        "risk": _risk(rows),
    }
    full = [row for row in policy_rows["full_contract"] if float(row["calibrated_risk"]) <= threshold]
    count = len(full)
    matched = {
        name: {
            "accepted": count,
            "coverage": count / len(rows),
            "invalid": int(sum(bool(row["invalid"]) for row in _lowest(policy_rows[name], count))),
            "risk": _risk(_lowest(policy_rows[name], count)),
        }
        for name in ("acquisition_qc", "endpoint_qc")
    }
    matched["full_contract"] = {
        "accepted": count,
        "coverage": count / len(rows),
        "invalid": int(sum(bool(row["invalid"]) for row in full)),
        "risk": _risk(full),
    }
    aurc = {name: _aurc(values) for name, values in policy_rows.items()}
    risk_reductions = {name: matched[name]["risk"] - matched["full_contract"]["risk"] for name in ("acquisition_qc", "endpoint_qc")}
    aurc_differences = {name: aurc[name] - aurc["full_contract"] for name in ("acquisition_qc", "endpoint_qc")}
    ablation = {name: aurc[name] - aurc["full_contract"] for name in ("without_scale_consistency", "without_split_consistency")}
    clean = [row for row in rows if row["condition"] == "clean"]
    clean_full = [row for row in full if row["condition"] == "clean"]
    clean_summary = {
        "eligible": len(clean),
        "accepted": len(clean_full),
        "coverage": len(clean_full) / len(clean),
        "primary_median_error_degrees": float(np.median([row["median_error_degrees"] for row in clean])),
        "sigma4_median_error_degrees": float(np.median([row["sigma4_median_error_degrees"] for row in clean])),
        "gradient_median_error_degrees": float(np.median([row["gradient_median_error_degrees"] for row in clean])),
    }
    recomputed_summary = {
        "rois": len(confirmation),
        "cases": len(rows),
        "invalid_cases": int(sum(bool(row["invalid"]) for row in rows)),
        "operating": operating,
        "matched_coverage": matched,
        "risk_reductions": risk_reductions,
        "risk_coverage_auc": aurc,
        "aurc_differences": aurc_differences,
        "ablation_aurc_increases": ablation,
        "clean": clean_summary,
    }
    checks["summary_exact"] = _close(recomputed_summary, result["summary"])

    bootstrap = _bootstrap(
        policy_rows,
        threshold=threshold,
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]),
    )
    checks["bootstrap_exact"] = _close(bootstrap, result["bootstrap"])
    before = _decision_hash(policy_rows["full_contract"], threshold)
    mutated = []
    for row in policy_rows["full_contract"]:
        clone = dict(row)
        clone["invalid"] = not bool(row["invalid"])
        clone["median_error_degrees"] = 90.0 - float(row["median_error_degrees"])
        clone["p75_error_degrees"] = 90.0 - float(row["p75_error_degrees"])
        mutated.append(clone)
    after = _decision_hash(mutated, threshold)
    checks["label_blindness_receipt"] = (
        before == after
        and before == result["label_blindness_audit"]["before_sha256"]
        and after == result["label_blindness_audit"]["after_reference_mutation_sha256"]
    )
    checks["confirmation_success_gates"] = result["status"] == "pass" and all(result["success_gates"].values())
    source_receipt = _source_receipt(dataset_root, manifest, confirmation)
    checks["source_files_verified"] = not source_receipt["mismatches"] and source_receipt["files_expected"] > 0
    verified = all(checks.values())
    audit = {
        "schema_version": "nostos-pshg-acquisition-shift-audit/1.0",
        "status": "verified_pass" if verified else "verification_failed",
        "checks": checks,
        "source_receipt": source_receipt,
        "recomputed_summary": recomputed_summary,
        "recomputed_bootstrap": bootstrap,
        "decision_receipt": {"before_sha256": before, "after_reference_mutation_sha256": after},
        "audited_artifacts": {
            "protocol_sha256": _sha256(protocol_path),
            "config_sha256": _sha256(config_path),
            "profile_sha256": _sha256(profile_path),
            "lock_sha256": _sha256(lock_path),
            "source_manifest_sha256": _sha256(manifest_path),
            "result_sha256": _sha256(result_path),
            "rows_sha256": _sha256(rows_path),
        },
        "claim_boundary": result["claim_boundary"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return audit
