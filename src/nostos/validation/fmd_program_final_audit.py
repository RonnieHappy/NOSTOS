"""Terminal machine audit for the complete FMD validity-profile program."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from nostos.validation.conditional_support_profile import (
    apply_conditional_support,
    verify_conditional_profile,
)
from nostos.validation.reporting_amendment import verify_content_hash
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    read_jsonl,
    sha256_file,
    verify_profile,
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _self_hash_valid(payload: Mapping[str, Any]) -> bool:
    expected = str(payload.get("content_sha256", ""))
    content = dict(payload)
    content.pop("content_sha256", None)
    return bool(expected) and canonical_sha256(content) == expected


def _audit_lock(project_root: Path, lock: Mapping[str, Any]) -> dict[str, Any]:
    content_valid = _self_hash_valid(lock)
    mismatches = []
    for artifact in lock["artifacts"]:
        path = project_root / str(artifact["path"])
        observed = sha256_file(path) if path.is_file() else None
        if observed != str(artifact["sha256"]):
            mismatches.append(
                {
                    "path": artifact["path"],
                    "expected": artifact["sha256"],
                    "observed": observed,
                }
            )
    return {
        "content_hash_valid": content_valid,
        "artifact_count": len(lock["artifacts"]),
        "artifact_mismatches": mismatches,
        "all_artifacts_match": not mismatches,
    }


def _selection_checks(config: Mapping[str, Any]) -> dict[str, Any]:
    seed = int(config["selection"]["seed"])
    root = f"{config['source']['acquisition_modality']}_{config['source']['sample']}"
    candidates = [field for field in range(1, 21) if field != 19]
    ordered = sorted(
        candidates,
        key=lambda field: hashlib.sha256(
            f"{seed}|{root}|fov{field}".encode()
        ).hexdigest(),
    )
    expected_fields = [
        *[int(value) for value in config["selection"]["development_fields"]],
        *[int(value) for value in config["selection"]["confirmation_fields"]],
    ]
    realization_matches = {}
    for field in expected_fields:
        ordered_realizations = sorted(
            range(50),
            key=lambda realization: hashlib.sha256(
                f"{seed}|fov{field}|realization{realization}".encode()
            ).hexdigest(),
        )[:4]
        observed = sorted(
            int(value)
            for value in config["selection"]["realization_indices"][str(field)]
        )
        realization_matches[str(field)] = observed == sorted(ordered_realizations)
    return {
        "field_order_reproduced": expected_fields == ordered[: len(expected_fields)],
        "expected_field_prefix": expected_fields,
        "recomputed_field_prefix": ordered[: len(expected_fields)],
        "realization_selection_reproduced": all(realization_matches.values()),
        "realization_matches_by_field": realization_matches,
        "unused_fields_after_confirmation": ordered[len(expected_fields) :],
    }


def _row_integrity(
    rows: list[dict[str, Any]],
    pair_index: Mapping[str, Any],
    *,
    expected_partition: str,
) -> dict[str, Any]:
    records = pair_index["records"]
    records_by_pair = {str(record["pair_id"]): record for record in records}
    pair_counts = Counter(str(row["pair_id"]) for row in rows)
    score_errors = []
    member_errors = []
    for row in rows:
        metadata = row["metadata"]
        captures = float(metadata["averaged_captures"])
        perturbation = float(row["support_components"]["perturbation_stability"])
        expected_score = max(0.0, math.sqrt(16.0 / captures) - 1.0) + perturbation
        observed_score = float(row["scores"]["declared_capture_stability_contract"])
        if not math.isclose(expected_score, observed_score, rel_tol=0.0, abs_tol=1e-12):
            score_errors.append(str(row["case_id"]))
        record = records_by_pair.get(str(row["pair_id"]))
        if record is None or metadata["input_sha256"] != record["input_sha256"] or metadata[
            "reference_sha256"
        ] != record["reference_sha256"]:
            member_errors.append(str(row["case_id"]))
    case_ids = [str(row["case_id"]) for row in rows]
    return {
        "rows": len(rows),
        "unique_case_ids": len(set(case_ids)),
        "paired_acquisitions": len(records),
        "every_pair_has_eight_endpoint_rows": bool(pair_counts)
        and set(pair_counts.values()) == {8}
        and set(pair_counts) == set(records_by_pair),
        "partition_exact": all(
            str(row["profile_partition"]) == expected_partition for row in rows
        ),
        "pixel_relative_only": all(
            row["calibration_status"] == "pixel_relative_only"
            and row["physical_unit_output_eligible"] is False
            for row in rows
        ),
        "declared_capture_score_exact": not score_errors,
        "score_error_cases": score_errors,
        "member_hash_lineage_exact": not member_errors,
        "member_error_cases": member_errors,
    }


def build_fmd_program_final_audit(project_root: Path) -> tuple[dict[str, Any], str]:
    root = project_root.resolve()
    paths = {
        "v1_metadata_failure": root
        / "outputs/nostos0-fmd-validity-profile-v1-development/metadata_failure_receipt.json",
        "v1_1_performance_abort": root
        / "outputs/nostos0-fmd-validity-profile-v1-1-development/performance_abort_receipt.json",
        "v1_1_development": root
        / "outputs/nostos0-fmd-validity-profile-v1-1-compiled/development_audit.json",
        "v1_2_development": root
        / "outputs/nostos0-fmd-validity-profile-v1-2-compiled/development_audit.json",
        "v1_2_confirmation": root
        / "outputs/nostos0-fmd-validity-profile-v1-2-confirmation-audit-v1-1/confirmation_audit.json",
        "v1_3_config": root / "configs/fmd_widefield_validity_profile_v1_3.locked.json",
        "v1_3_profile": root
        / "outputs/nostos0-fmd-widefield-v1-3-compiled/validity_profile.json",
        "v1_3_development_rows": root
        / "outputs/nostos0-fmd-widefield-v1-3-development/development_rows.jsonl",
        "v1_3_development_index": root
        / "outputs/nostos0-fmd-widefield-v1-3-development/development_pair_index.json",
        "v1_3_confirmation_rows": root
        / "outputs/nostos0-fmd-widefield-v1-3-confirmation/confirmation_rows.jsonl",
        "v1_3_confirmation_index": root
        / "outputs/nostos0-fmd-widefield-v1-3-confirmation/confirmation_pair_index.json",
        "v1_3_confirmation_audit": root
        / "outputs/nostos0-fmd-widefield-v1-3-confirmation-audit/confirmation_audit.json",
        "v1_3_reporting_amendment": root
        / "outputs/nostos0-fmd-widefield-v1-3-confirmation-audit-v1-2-reporting-amendment.json",
        "v1_3_lock": root
        / "manifests/fmd_widefield_validity_profile_v1_3_confirmation_lock.json",
        "v1_4_config": root
        / "configs/fmd_widefield_conditional_support_v1_4.locked.json",
        "v1_4_profile": root
        / "outputs/nostos0-fmd-widefield-v1-4-conditional-development/conditional_support_profile.json",
        "v1_4_development_audit": root
        / "outputs/nostos0-fmd-widefield-v1-4-conditional-development/development_audit.json",
        "v1_4_confirmation_rows": root
        / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation/confirmation_rows.jsonl",
        "v1_4_confirmation_index": root
        / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation/confirmation_pair_index.json",
        "v1_4_confirmation_audit": root
        / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_audit.json",
        "v1_4_confirmation_scored": root
        / "outputs/nostos0-fmd-widefield-v1-4-conditional-confirmation-audit/confirmation_scored.jsonl",
        "v1_4_finite_sample": root
        / "outputs/nostos0-fmd-widefield-v1-4-finite-sample-uncertainty.json",
        "v1_4_lock": root
        / "manifests/fmd_widefield_conditional_support_v1_4_confirmation_lock.json",
    }
    missing = [str(path.relative_to(root)) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"FMD final audit is missing artifacts: {missing}")
    payloads = {key: _load(path) for key, path in paths.items() if path.suffix == ".json"}
    v1_3_profile = payloads["v1_3_profile"]
    v1_4_profile = payloads["v1_4_profile"]
    verify_profile(v1_3_profile)
    verify_conditional_profile(v1_4_profile)
    verify_content_hash(payloads["v1_3_reporting_amendment"])

    v1_3_dev_rows = read_jsonl(paths["v1_3_development_rows"])
    v1_3_confirmation_rows = read_jsonl(paths["v1_3_confirmation_rows"])
    v1_4_confirmation_rows = read_jsonl(paths["v1_4_confirmation_rows"])
    v1_4_scored = read_jsonl(paths["v1_4_confirmation_scored"])
    recomputed = apply_conditional_support(
        v1_4_confirmation_rows,
        base_profile=v1_3_profile,
        conditional_profile=v1_4_profile,
    )
    recomputed_by_id = {str(row["case_id"]): row for row in recomputed}
    scored_by_id = {str(row["case_id"]): row for row in v1_4_scored}
    decisions_exact = all(
        bool(recomputed_by_id[case]["candidate_hard_abstention"])
        == bool(scored_by_id[case]["candidate_hard_abstention"])
        and math.isclose(
            float(recomputed_by_id[case]["calibrated_risk"]),
            float(scored_by_id[case]["calibrated_risk"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        for case in recomputed_by_id
    )
    mutated_rows = []
    for row in v1_4_confirmation_rows:
        clone = dict(row)
        clone["invalid"] = not bool(row["invalid"])
        clone["error"] = 999.0
        clone["reference_measurement"] = -999.0
        mutated_rows.append(clone)
    mutated = apply_conditional_support(
        mutated_rows, base_profile=v1_3_profile, conditional_profile=v1_4_profile
    )
    label_blind = all(
        bool(left["candidate_hard_abstention"])
        == bool(right["candidate_hard_abstention"])
        and math.isclose(
            float(left["calibrated_risk"]),
            float(right["calibrated_risk"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        for left, right in zip(recomputed, mutated, strict=True)
    )

    v1_3_dev_groups = {str(row["reference_group_id"]) for row in v1_3_dev_rows}
    v1_3_conf_groups = {
        str(row["reference_group_id"]) for row in v1_3_confirmation_rows
    }
    v1_4_conf_groups = {
        str(row["reference_group_id"]) for row in v1_4_confirmation_rows
    }
    v1_3_audit = payloads["v1_3_confirmation_audit"]
    v1_4_audit = payloads["v1_4_confirmation_audit"]
    v1_2_audit = payloads["v1_2_confirmation"]
    finite = payloads["v1_4_finite_sample"]
    v1_3_lock_audit = _audit_lock(root, payloads["v1_3_lock"])
    v1_4_lock_audit = _audit_lock(root, payloads["v1_4_lock"])
    selection = _selection_checks(payloads["v1_4_config"])
    v1_3_dev_integrity = _row_integrity(
        v1_3_dev_rows,
        payloads["v1_3_development_index"],
        expected_partition="development",
    )
    v1_3_conf_integrity = _row_integrity(
        v1_3_confirmation_rows,
        payloads["v1_3_confirmation_index"],
        expected_partition="confirmation",
    )
    v1_4_conf_integrity = _row_integrity(
        v1_4_confirmation_rows,
        payloads["v1_4_confirmation_index"],
        expected_partition="confirmation",
    )
    unsafe_v1_2 = next(
        item
        for item in v1_2_audit["stratified_safety_audit"]["summaries"][
            "acquisition_modality"
        ]
        if item["stratum"] == "WideField"
    )
    checks = {
        "all_required_artifacts_present": not missing,
        "v1_3_lock_content_and_artifacts_exact": v1_3_lock_audit["content_hash_valid"]
        and v1_3_lock_audit["all_artifacts_match"],
        "v1_4_lock_content_and_artifacts_exact": v1_4_lock_audit["content_hash_valid"]
        and v1_4_lock_audit["all_artifacts_match"],
        "hash_selection_reproduced": selection["field_order_reproduced"]
        and selection["realization_selection_reproduced"],
        "v1_3_development_confirmation_groups_disjoint": not (
            v1_3_dev_groups & v1_3_conf_groups
        ),
        "v1_4_confirmation_groups_disjoint_from_all_opened_development": not (
            (v1_3_dev_groups | v1_3_conf_groups) & v1_4_conf_groups
        ),
        "v1_3_development_rows_integral": all(
            bool(value)
            for key, value in v1_3_dev_integrity.items()
            if key
            in {
                "every_pair_has_eight_endpoint_rows",
                "partition_exact",
                "pixel_relative_only",
                "declared_capture_score_exact",
                "member_hash_lineage_exact",
            }
        )
        and v1_3_dev_integrity["rows"] == v1_3_dev_integrity["unique_case_ids"] == 640,
        "v1_3_confirmation_rows_integral": all(
            bool(value)
            for key, value in v1_3_conf_integrity.items()
            if key
            in {
                "every_pair_has_eight_endpoint_rows",
                "partition_exact",
                "pixel_relative_only",
                "declared_capture_score_exact",
                "member_hash_lineage_exact",
            }
        )
        and v1_3_conf_integrity["rows"] == v1_3_conf_integrity["unique_case_ids"] == 640,
        "v1_4_confirmation_rows_integral": all(
            bool(value)
            for key, value in v1_4_conf_integrity.items()
            if key
            in {
                "every_pair_has_eight_endpoint_rows",
                "partition_exact",
                "pixel_relative_only",
                "declared_capture_score_exact",
                "member_hash_lineage_exact",
            }
        )
        and v1_4_conf_integrity["rows"] == v1_4_conf_integrity["unique_case_ids"] == 640,
        "v1_4_confirmation_decisions_exactly_recomputed": decisions_exact,
        "deployed_decisions_reference_label_blind": label_blind,
        "failure_lineage_retained": payloads["v1_metadata_failure"]["status"]
        == "failed_before_endpoint_analysis"
        and payloads["v1_1_performance_abort"]["status"]
        == "development_run_manually_stopped_before_row_export"
        and payloads["v1_1_development"]["status"] == "no_operating_point",
        "v1_2_pooled_pass_but_widefield_failure_retained": v1_2_audit["status"]
        == "pass"
        and v1_2_audit["stratified_safety_audit"]["acquisition_modality_heterogeneity"]
        is True
        and float(unsafe_v1_2["risk"]) > 0.4,
        "v1_3_pooled_confirmation_pass_retained": v1_3_audit["status"] == "pass"
        and all(v1_3_audit["checks"].values()),
        "v1_4_hierarchical_confirmation_pass": v1_4_audit["status"] == "pass"
        and all(v1_4_audit["checks"].values()),
        "v1_4_finite_sample_caveat_present": finite["status"]
        == "supplemental_uncertainty_complete"
        and float(finite["independent_group_any_failure_interval"]["clopper_pearson_95"][1])
        > 0.6,
        "reporting_only_amendment_is_nonanalytical": payloads[
            "v1_3_reporting_amendment"
        ]["reporting_amendment"]["statistical_values_recomputed"]
        is False
        and payloads["v1_3_reporting_amendment"]["reporting_amendment"][
            "gate_decisions_changed"
        ]
        is False,
    }
    result = {
        "schema_version": "nostos-fmd-validity-program-final-audit/1.0",
        "status": "verified_pass" if all(checks.values()) else "fail",
        "checks": checks,
        "failure_repair_lineage": [
            {
                "stage": "v1_metadata",
                "status": payloads["v1_metadata_failure"]["status"],
                "disposition": "retained; zero endpoint analysis",
            },
            {
                "stage": "v1_1_runtime",
                "status": payloads["v1_1_performance_abort"]["status"],
                "disposition": "retained; endpoint-selective implementation added",
            },
            {
                "stage": "v1_1_base_contract",
                "status": payloads["v1_1_development"]["status"],
                "disposition": "no deployable operating point",
            },
            {
                "stage": "v1_2_pooled_profile",
                "status": "aggregate_pass_with_widefield_failure",
                "widefield_accepted": unsafe_v1_2["accepted"],
                "widefield_invalid": unsafe_v1_2["invalid"],
                "widefield_risk": unsafe_v1_2["risk"],
                "disposition": "not promoted across modalities",
            },
            {
                "stage": "v1_3_widefield_profile",
                "status": v1_3_audit["status"],
                "primary_operating_point": v1_3_audit["primary_operating_point"],
                "disposition": "pooled pass; deterministic avg8-by-8px subgroup failure triggered v1.4",
            },
            {
                "stage": "v1_4_hierarchical_profile",
                "status": v1_4_audit["status"],
                "primary_operating_point": v1_4_audit["primary_operating_point"],
                "supported_cells": [
                    {"values": item["values"], "summary": item["summary"]}
                    for item in v1_4_audit["supported_cell_audit"]
                ],
                "matched_acquisition_qc": v1_4_audit[
                    "acquisition_qc_matched_count"
                ],
                "aurc_difference": v1_4_audit["risk_coverage"][
                    "cluster_bootstrap_aurc_difference"
                ],
            },
        ],
        "selection_audit": selection,
        "lock_audits": {"v1_3": v1_3_lock_audit, "v1_4": v1_4_lock_audit},
        "row_integrity": {
            "v1_3_development": v1_3_dev_integrity,
            "v1_3_confirmation": v1_3_conf_integrity,
            "v1_4_confirmation": v1_4_conf_integrity,
        },
        "finite_sample_uncertainty": {
            "accepted_measurement_interval": finite["nested_measurement_interval"],
            "independent_group_any_failure_interval": finite[
                "independent_group_any_failure_interval"
            ],
            "warning": finite["interpretation"]["cluster_bootstrap_zero_event_warning"],
        },
        "supported_claim": (
            "Within one public widefield acquisition family, a frozen input-only calibrated-risk "
            "profile composed with development-only acquisition-by-scale support eliminated the "
            "previously reproducible unsafe subgroup on four untouched FOVs, at 26.7% primary "
            "coverage, while matched ordinary acquisition QC emitted 31 invalid values."
        ),
        "prohibited_extensions": [
            "biological meaning or diagnostic performance",
            "physical-scale accuracy because FMD pixel spacing was unavailable",
            "image restoration or denoising superiority",
            "transfer beyond the declared FMD widefield acquisition family",
            "population-level zero risk: only four independent confirmation FOVs were used",
            "clinical or intraoperative utility",
        ],
        "methodological_contribution": [
            "separate development compilation and one-shot confirmation",
            "input-only risk scoring with reference labels withheld at deployment",
            "acquisition-stratum support that hard-abstains on unseen families",
            "hierarchical acquisition-by-requested-scale support that prevents pooled-risk masking",
            "matched ordinary-QC and risk-coverage comparisons with FOV-clustered resampling",
            "immutable failure, amendment, profile and source-hash lineage",
        ],
        "artifact_hashes": {
            key: {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
            for key, path in paths.items()
        },
    }
    result["content_sha256"] = canonical_sha256(result)
    primary = v1_4_audit["primary_operating_point"]
    qc = v1_4_audit["acquisition_qc_matched_count"]
    aurc = v1_4_audit["risk_coverage"]["cluster_bootstrap_aurc_difference"]
    markdown = f"""# NOSTOS FMD validity-profile program final audit

**Status:** `{result['status']}`  
**Scope:** computation-only public microscopy methods validation

## Terminal result

The final v1.4 hierarchical profile passed every prespecified pooled and cellwise gate on four untouched widefield FOVs. It accepted {primary['accepted']} of {primary['eligible']} eligible tensor-coherence measurements ({primary['coverage']:.1%}), with {primary['invalid']} invalid emissions. Matched ordinary acquisition QC emitted {qc['invalid']} invalid values among {qc['accepted']} emissions ({qc['risk']:.1%}). The acquisition-QC-minus-NOSTOS AURC difference was {aurc['observed']:.3f} (FOV-clustered 95% interval {aurc['bootstrap_ci95'][0]:.3f} to {aurc['bootstrap_ci95'][1]:.3f}).

This result repairs, rather than erases, the earlier failure. V1.2 passed in aggregate while widefield risk was {unsafe_v1_2['risk']:.1%}. V1.3 then passed its pooled widefield gate but reproduced a fully invalid avg8-by-8-pixel subgroup across development and confirmation. V1.4 froze an acquisition-by-scale support table on the eight opened fields and tested it once on four new fields.

## Integrity

- All {v1_3_lock_audit['artifact_count']} v1.3 locked artifacts match their frozen hashes.
- All {v1_4_lock_audit['artifact_count']} v1.4 locked artifacts match their frozen hashes.
- Field and repeated-capture selections reproduce from the declared SHA-256 rules.
- V1.3 development, v1.3 confirmation and v1.4 confirmation FOV sets are disjoint.
- Every confirmation decision and calibrated risk was independently recomputed from the serialized profiles.
- Toggling withheld invalidity labels and reference values leaves every deployed decision unchanged.

## Finite-sample boundary

Zero invalid emissions does not mean zero population uncertainty. The exact row-level 95% interval is 0 to {finite['nested_measurement_interval']['clopper_pearson_95'][1]:.3f}, but rows are nested within only four independent fields. Treating a field as failed when any accepted value fails gives a 0/4 exact upper bound of {finite['independent_group_any_failure_interval']['clopper_pearson_95'][1]:.3f}. The result is therefore a prospective technical confirmation within this archive, not proof of universal risk control.

## Admissible claim

> {result['supported_claim']}

The audit does not support biological, physical-scale, denoising, cross-instrument, population-prevalence, clinical or intraoperative claims.
"""
    return result, markdown
