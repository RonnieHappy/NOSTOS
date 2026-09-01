"""Consolidate the frozen NOSTOS-0 bone contract program into one receipt."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


RECEIPTS = {
    "download_integrity": "outputs/nostos0-bone-download-integrity/integrity_verification.json",
    "paired_shg_v1": (
        "outputs/nostos0-bone-contract-orientation-confirmation-v1/"
        "bone_orientation_confirmation.json"
    ),
    "mouse_shg_v2": "outputs/nostos0-bone-orientation-v2/bone_orientation_v2.json",
    "rat_network_v1": "outputs/nostos0-bone-network-3d/bone_network_3d.json",
    "rat_network_v2": "outputs/nostos0-bone-network-3d-v2/bone_network_3d.json",
    "human_nanoct_scalar_v1": (
        "outputs/nostos0-human-nanoct-transfer/human_nanoct_transfer.json"
    ),
    "human_nanoct_scalar_cases": (
        "outputs/nostos0-human-nanoct-transfer/case_rows.json"
    ),
    "human_nanoct_scale_v2": (
        "outputs/nostos0-human-nanoct-scale-response-v2/"
        "human_nanoct_scale_response.json"
    ),
    "uvpam_abstention": "outputs/nostos0-uvpam-abstention/uvpam_abstention.json",
}


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _condition_by_perturbation(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["perturbation"])].append(row)

    summary: dict[str, Any] = {}
    for perturbation, cases in sorted(grouped.items()):
        accepted = [row for row in cases if bool(row["accept"][condition])]
        invalid = sum(bool(row["invalid"]) for row in accepted)
        summary[perturbation] = {
            "cases": len(cases),
            "accepted": len(accepted),
            "coverage": len(accepted) / len(cases),
            "silent_invalid": invalid,
            "silent_invalid_risk": invalid / len(accepted) if accepted else None,
        }
    return summary


def _receipt_index(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads: dict[str, Any] = {}
    index: dict[str, Any] = {}
    missing: list[str] = []
    for identifier, relative in RECEIPTS.items():
        path = project_root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        payloads[identifier] = _load(path)
        index[identifier] = {
            "path": relative.replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    if missing:
        joined = "\n".join(missing)
        raise FileNotFoundError(f"Missing required bone-program receipts:\n{joined}")
    return payloads, index


def build_bone_program_summary(project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build the final machine-readable gate table and reviewer-facing summary."""

    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    payloads, receipt_index = _receipt_index(project_root)

    integrity = payloads["download_integrity"]
    shg_v1 = payloads["paired_shg_v1"]
    shg_v2 = payloads["mouse_shg_v2"]
    network_v1 = payloads["rat_network_v1"]
    network_v2 = payloads["rat_network_v2"]
    nano_v1 = payloads["human_nanoct_scalar_v1"]
    nano_cases = payloads["human_nanoct_scalar_cases"]
    nano_v2 = payloads["human_nanoct_scale_v2"]
    uvpam = payloads["uvpam_abstention"]

    shg_full = shg_v1["summary"]["SHG"]["full_contract"]
    shg_always = shg_v1["summary"]["SHG"]["always_emit"]
    network_full = network_v2["summary"]["full_contract"]
    network_always = network_v2["summary"]["always_emit"]
    nano_full = nano_v1["summary"]["full_contract"]
    nano_always = nano_v1["summary"]["always_emit"]
    uv_full = uvpam["summary"]["full_contract"]

    stages = [
        {
            "stage": "download_integrity",
            "role": "source_integrity",
            "status": "pass" if integrity["status"] == "pass" else "fail",
            "independent_units": None,
            "technical_cases": integrity["files"],
            "result": {
                "verified_files": integrity["files"],
                "verified_bytes": integrity["bytes"],
            },
            "claim_boundary": "Source-file integrity only.",
        },
        {
            "stage": "paired_shg_tpf_v1",
            "role": "compact_confirmation_with_partly_circular_invalidity",
            "status": "failed_coverage_gate",
            "independent_units": shg_v1["independent_units"],
            "technical_cases": shg_v1["rows"],
            "result": {
                "always_emit_coverage": shg_always["coverage"],
                "always_emit_risk": shg_always["silent_invalid_risk"],
                "full_contract_coverage": shg_full["coverage"],
                "full_contract_risk": shg_full["silent_invalid_risk"],
                "coverage_gate_at_least_0_70": shg_v1["gates"][
                    "shg_full_coverage_at_least_0_70"
                ],
            },
            "claim_boundary": shg_v1["claim_boundary"],
        },
        {
            "stage": "mouse_shg_support_v2",
            "role": "support_rule_development",
            "status": shg_v2["status"],
            "independent_units": 8,
            "technical_cases": None,
            "result": {
                "promoted_threshold_degrees": shg_v2["promoted_threshold_degrees"],
                "development": shg_v2["development"],
                "evaluation": shg_v2["evaluation"],
            },
            "claim_boundary": shg_v2["claim_boundary"],
        },
        {
            "stage": "rat_network_v1",
            "role": "stress_design_calibration",
            "status": "non_informative_no_invalid_cases",
            "independent_units": network_v1["independent_rats"],
            "technical_cases": network_v1["stress_cases"],
            "result": {
                "always_emit_risk": network_v1["summary"]["always_emit"][
                    "silent_invalid_risk"
                ],
                "full_contract_coverage": network_v1["summary"]["full_contract"][
                    "coverage"
                ],
            },
            "claim_boundary": network_v1["claim_boundary"],
        },
        {
            "stage": "rat_network_v2",
            "role": "post_failure_stress_calibration",
            "status": "risk_reduction_but_failed_coverage_gate",
            "independent_units": network_v2["independent_rats"],
            "technical_cases": network_v2["stress_cases"],
            "result": {
                "always_emit_coverage": network_always["coverage"],
                "always_emit_risk": network_always["silent_invalid_risk"],
                "full_contract_coverage": network_full["coverage"],
                "full_contract_risk": network_full["silent_invalid_risk"],
                "full_risk_coverage_auc": network_v2["risk_coverage_auc"][
                    "full_contract"
                ],
                "endpoint_qc_risk_coverage_auc": network_v2["risk_coverage_auc"][
                    "endpoint_qc"
                ],
                "master_coverage_gate_at_least_0_80": network_full["coverage"] >= 0.80,
            },
            "claim_boundary": network_v2["claim_boundary"],
        },
        {
            "stage": "human_nanoct_scalar_v1",
            "role": "opened_acquisition_transfer",
            "status": "failed_withheld_stress",
            "independent_units": "six_deposited_volumes_independence_not_asserted",
            "technical_cases": nano_v1["technical_cases"],
            "result": {
                "always_emit_coverage": nano_always["coverage"],
                "always_emit_risk": nano_always["silent_invalid_risk"],
                "full_contract_coverage": nano_full["coverage"],
                "full_contract_risk": nano_full["silent_invalid_risk"],
                "full_contract_by_perturbation": _condition_by_perturbation(
                    nano_cases, "full_contract"
                ),
            },
            "claim_boundary": nano_v1["claim_boundary"],
        },
        {
            "stage": "human_nanoct_scale_v2",
            "role": "post_failure_scale_response_development",
            "status": "risk_reduction_but_failed_coverage_gate",
            "independent_units": "same_six_opened_deposited_volumes",
            "technical_cases": nano_v2["scale_case_rows"],
            "result": {
                "summary_by_scale_um": nano_v2["summary_by_scale_um"],
                "gates_by_scale_um": nano_v2["gates_by_scale_um"],
            },
            "claim_boundary": nano_v2["claim_boundary"],
        },
        {
            "stage": "uvpam_semantic_abstention",
            "role": "negative_control",
            "status": "pass_narrow_governance_control",
            "independent_units": "six_filename_groups_not_asserted_specimens",
            "technical_cases": uvpam["sampled_tiles"],
            "result": {
                "requested_endpoint_coverage": uv_full["coverage"],
                "requested_endpoint_risk": uv_full["silent_invalid_risk"],
                "pixel_descriptors_emitted": uvpam["generic_pixel_descriptors_emitted"],
            },
            "claim_boundary": uvpam["claim_boundary"],
        },
    ]

    gate_table = [
        {
            "gate": "all_source_files_integrity_verified",
            "status": "pass" if integrity["status"] == "pass" else "fail",
            "value": f"{integrity['files']} files; {integrity['bytes']} bytes",
        },
        {
            "gate": "macro_risk_coverage_auc_reduction_at_least_20_percent",
            "status": "fail_not_estimable_across_all_frozen_strata",
            "value": None,
        },
        {
            "gate": "paired_specimen_bootstrap_interval_excludes_zero",
            "status": "fail_not_estimable_across_all_frozen_strata",
            "value": None,
        },
        {
            "gate": "overall_full_contract_coverage_at_least_0_80",
            "status": "fail",
            "value": {
                "paired_shg": shg_full["coverage"],
                "rat_network_v2": network_full["coverage"],
                "human_nanoct_scale_0.4": nano_v2["summary_by_scale_um"]["0.4"][
                    "full_contract"
                ]["coverage"],
                "human_nanoct_scale_0.8": nano_v2["summary_by_scale_um"]["0.8"][
                    "full_contract"
                ]["coverage"],
            },
        },
        {
            "gate": "every_endpoint_acquisition_stratum_coverage_at_least_0_70",
            "status": "fail",
            "value": "Multiple SHG, network and nanoCT strata were below 0.70.",
        },
        {
            "gate": "lower_silent_invalid_risk_for_every_endpoint_at_matched_coverage",
            "status": "fail_not_demonstrated",
            "value": None,
        },
        {
            "gate": "uncertainty_coverage_between_0.90_and_0.975",
            "status": "fail_not_estimated_for_complete_program",
            "value": None,
        },
        {
            "gate": "missing_calibration_and_semantic_support_trigger_abstention",
            "status": "pass_narrow_control",
            "value": "0/144 requested physical-collagen UV-PAM outputs emitted.",
        },
    ]

    payload: dict[str, Any] = {
        "protocol_version": "nostos-bone-contract-program-summary/1.0",
        "source_protocol": "docs/NOSTOS0_BONE_CONTRACT_ABLATION_PROTOCOL.md",
        "status": "complete_with_failed_primary_gates",
        "nature_methods_readiness": "not_ready",
        "clinical_readiness": "not_ready",
        "publication_interpretation": (
            "Complete negative/development evidence for the broad bone validity-contract "
            "hypothesis; bounded endpoint and governance results remain reportable."
        ),
        "stages": stages,
        "gate_table": gate_table,
        "receipt_index": receipt_index,
        "blocking_requirements": [
            "A frozen support contract that reaches useful coverage on an untouched acquisition family.",
            "A paired specimen-level primary risk-coverage analysis across eligible strata.",
            "Independent execution of the clean release by an external operator.",
            "Independent multi-laboratory or acquisition-family validation for a flagship methods claim.",
        ],
        "prohibited_claims": [
            "universal validity advantage",
            "automatic segmentation validity",
            "population-level bone biology",
            "diagnosis or treatment guidance",
            "tissue mechanics or intraoperative utility",
            "Nature Methods readiness",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "bone_contract_program_summary.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_path = output_dir / "bone_contract_program_summary.md"
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# NOSTOS-0 bone contract program: final evidence summary",
        "",
        f"**Program status:** `{payload['status']}`  ",
        f"**Nature Methods readiness:** `{payload['nature_methods_readiness']}`  ",
        f"**Clinical readiness:** `{payload['clinical_readiness']}`",
        "",
        payload["publication_interpretation"],
        "",
        "## Frozen gate table",
        "",
        "| Gate | Status | Value |",
        "| --- | --- | --- |",
    ]
    for row in payload["gate_table"]:
        value = row["value"]
        if isinstance(value, dict):
            value = "; ".join(f"{key}={item:.3f}" for key, item in value.items())
        if value is None:
            value = "Not estimable"
        lines.append(f"| {row['gate']} | `{row['status']}` | {value} |")

    lines.extend(
        [
            "",
            "## Stage disposition",
            "",
            "| Stage | Role | Status | Highest unit | Technical cases |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for stage in payload["stages"]:
        lines.append(
            "| {stage} | {role} | `{status}` | {units} | {cases} |".format(
                stage=stage["stage"],
                role=stage["role"],
                status=stage["status"],
                units=stage["independent_units"] or "not applicable",
                cases=stage["technical_cases"] if stage["technical_cases"] is not None else "not reported",
            )
        )

    lines.extend(["", "## Blocking requirements", ""])
    lines.extend(f"- {item}" for item in payload["blocking_requirements"])
    lines.extend(["", "## Prohibited claims", ""])
    lines.extend(f"- {item}" for item in payload["prohibited_claims"])
    lines.extend(
        [
            "",
            "Every input receipt is SHA-256 indexed in `bone_contract_program_summary.json`.",
            "",
        ]
    )
    return "\n".join(lines)
