"""Calibrate SHG abstention against within-field mapped perturbation drift."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nostos.validation.family_risk_calibration import (
    calibrated_operating_summary,
    cross_fitted_family_risk,
    risk_coverage_auc,
)
from nostos.validation.shg_coordinate_bridge import stability_invalid


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


def compile_profile(
    bridge_path: Path,
    exp10_path: Path,
    exp15_path: Path,
    output: Path,
) -> dict[str, Any]:
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    enabled = {
        endpoint: item
        for endpoint, item in bridge["endpoints"].items()
        if item["enabled_for_external_confirmation"]
    }
    source_rows = []
    for experiment, path in (("Exp10", exp10_path), ("Exp15", exp15_path)):
        for row in read_jsonl(path):
            clone = dict(row)
            clone["experiment"] = experiment
            clone["mouse"] = f"{experiment}|{row['mouse']}"
            clone["field_stem"] = f"{experiment}|{row['field_stem']}"
            source_rows.append(clone)
    clean = {
        (row["field_stem"], row["endpoint"]): row["observed"]
        for row in source_rows
        if row["condition"] == "clean" and row["endpoint"] in enabled
    }
    cases = []
    for row in source_rows:
        endpoint = row["endpoint"]
        if endpoint not in enabled:
            continue
        item = enabled[endpoint]
        invalid, drift = stability_invalid(
            item["selected_model"],
            row["observed"],
            clean.get((row["field_stem"], endpoint)),
            mode=item["error_mode"],
            tolerance=float(item["tolerance"]),
            denominator_floor=float(item["denominator_floor"]),
        )
        cases.append(
            {
                "case_id": f"{row['field_stem']}|{row['condition']}|{endpoint}",
                "structure": "heaton_shg_v2_stability",
                "reference_group_id": row["mouse"],
                "mouse": row["mouse"],
                "field_stem": row["field_stem"],
                "condition": row["condition"],
                "endpoint": endpoint,
                "pair_registration_eligible": True,
                "reference_eligible": True,
                "hard_abstention": bool(row["hard_abstention"]),
                "mapped_tolerance_normalized_drift": drift,
                "invalid": bool(invalid),
                "scores": row["scores"],
                "risk_components": row["risk_components"],
            }
        )
    family_map = {endpoint: [endpoint] for endpoint in enabled}
    maps = {}
    summaries = {}
    for policy in POLICIES:
        augmented, fitted = cross_fitted_family_risk(
            cases,
            family_map=family_map,
            raw_score=policy,
            bins=6,
            folds=4,
            seed=8312603,
        )
        summary = calibrated_operating_summary(augmented, maximum_predicted_risk=0.15)
        summary["risk_coverage_auc"] = risk_coverage_auc(augmented, score_key="calibrated_risk")
        summaries[policy] = summary
        maps[policy] = {endpoint: fitted[endpoint].to_dict() for endpoint in enabled}
    payload = {
        "schema_version": "nostos.heaton_shg_stability_profile_development.v2",
        "status": "post_failure_development_only_external_confirmation_required",
        "bridge": {
            "path": "configs/heaton_shg_coordinate_bridge_v2.development.json",
            "sha256": sha256_file(bridge_path),
        },
        "sources": {
            "exp10": {
                "path": "outputs/nostos0-heaton-in-vivo-shg-v1-risk-development/development_perturbation_rows.jsonl",
                "sha256": sha256_file(exp10_path),
            },
            "exp15": {
                "path": "outputs/nostos0-heaton-in-vivo-shg-v1-confirmation/confirmation_perturbation_rows.jsonl",
                "sha256": sha256_file(exp15_path),
                "original_role": "opened failed v1 confirmation; v2 development only",
            },
        },
        "independent_mice": len({row["mouse"] for row in cases}),
        "cases": len(cases),
        "enabled_endpoints": list(enabled),
        "disabled_endpoints": [
            endpoint
            for endpoint, item in bridge["endpoints"].items()
            if not item["enabled_for_external_confirmation"]
        ],
        "calibration": {
            "method": "endpoint_specific_quantile_binned_jeffreys_isotonic",
            "cluster_unit": "mouse",
            "folds": 4,
            "bins": 6,
            "seed": 8312603,
            "maximum_predicted_risk": 0.15,
            "risk_maps": maps,
            "cross_fitted_development_summaries": summaries,
        },
        "invalidity": (
            "A mapped perturbed endpoint is invalid when its drift from the same field's mapped clean "
            "endpoint exceeds the endpoint-specific frozen tolerance. Comparator coordinate agreement "
            "is evaluated separately on clean fields."
        ),
        "claim_boundary": (
            "Post-failure stability calibration on 16 already-open mice and programmed perturbations. "
            "No repaired transfer claim; all thresholds and maps require untouched external confirmation."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--exp10", type=Path, required=True)
    parser.add_argument("--exp15", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compile_profile(
        args.bridge.resolve(),
        args.exp10.resolve(),
        args.exp15.resolve(),
        args.output.resolve(),
    )
    full = result["calibration"]["cross_fitted_development_summaries"]["full_contract"]
    print(json.dumps({
        "status": result["status"],
        "mice": result["independent_mice"],
        "cases": result["cases"],
        "enabled": result["enabled_endpoints"],
        "full_contract": full,
    }, indent=2))


if __name__ == "__main__":
    main()
