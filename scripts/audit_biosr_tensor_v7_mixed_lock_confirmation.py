"""Audit BioSR tensor confirmation evidence sealed under v7 and v7.1 locks.

The linear archive remains governed by the original v7 lock.  The nonlinear
archive is governed by the outcome-free v7.1 metadata amendment.  This audit
combines their endpoint rows only after verifying both immutable lineages and
proving that the measurement definitions and decision rules are identical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nostos.validation.biosr_tensor_confirmation_v7 import evaluate_v7_confirmation
from nostos.validation.paired_acquisition_support import sha256_file


ROOT = Path(__file__).resolve().parents[1]
V7_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7.locked.json"
V71_CONFIG = ROOT / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
V71_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_1_nonlinear_lock.json"
INPUTS = {
    "F-actin_linear": {
        "directory": ROOT
        / "outputs/nostos0-biosr-tensor-v7-f-actin-linear-confirmation",
        "protocol": "nostos-paired-acquisition-tensor/7.0",
        "lock_path": V7_LOCK,
        "receipt_lock_key": "confirmation_lock_sha256",
        "expected_rows": 960,
        "expected_pairs": 96,
    },
    "F-actin_nonlinear": {
        "directory": ROOT
        / "outputs/nostos0-biosr-tensor-v7-1-f-actin-nonlinear-confirmation",
        "protocol": (
            "nostos-paired-acquisition-tensor/7.1-nonlinear-metadata-amendment"
        ),
        "lock_path": V71_LOCK,
        "receipt_lock_key": "v7_1_lock_sha256",
        "expected_rows": 720,
        "expected_pairs": 72,
    },
}
OUTPUT = ROOT / "outputs/nostos0-biosr-tensor-v7-mixed-lock-combined-audit"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _assert_equal(left: Any, right: Any, label: str) -> None:
    if left != right:
        raise ValueError(f"Mixed-lock scientific compatibility failure: {label}.")


def _verify_lock_files(lock: dict[str, Any], *, label: str) -> dict[str, Any]:
    checked = 0
    for artifact in lock["files"]:
        path = ROOT / artifact["path"]
        if not path.is_file():
            raise FileNotFoundError(f"{label} locked file is missing: {path}")
        if path.stat().st_size != int(artifact["bytes"]):
            raise ValueError(f"{label} locked-file byte mismatch: {path}")
        if sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"{label} locked-file hash mismatch: {path}")
        checked += 1
    return {"label": label, "locked_files_verified": checked}


def _verify_archive(
    archive: dict[str, Any], *, structure: str
) -> dict[str, Any]:
    path = Path(archive["path"])
    if not path.is_file():
        raise FileNotFoundError(f"{structure} archive is missing: {path}")
    if path.stat().st_size != int(archive["bytes"]):
        raise ValueError(f"{structure} archive byte mismatch.")
    observed_sha256 = sha256_file(path)
    if observed_sha256 != archive["sha256"]:
        raise ValueError(f"{structure} archive hash mismatch.")
    return {
        "structure": structure,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": observed_sha256,
    }


def _scientific_compatibility(
    v7: dict[str, Any], v71: dict[str, Any]
) -> dict[str, Any]:
    exact_sections = ("endpoints", "reference_eligibility")
    for section in exact_sections:
        _assert_equal(v7[section], v71[section], section)

    physical_v7 = dict(v7["physical_tensor"])
    physical_v71 = dict(v71["physical_tensor"])
    amendment_rule = physical_v71.pop("amendment_rule")
    _assert_equal(physical_v7, physical_v71, "physical_tensor executable parameters")
    _assert_equal(
        amendment_rule,
        (
            "Physical scales, estimators and response geometry are unchanged from "
            "v7; only the nonlinear grid calibration used to express those scales "
            "in pixels changes."
        ),
        "physical_tensor amendment annotation",
    )

    spectral_v7 = dict(v7["spectral_analysis"])
    spectral_v71 = dict(v71["spectral_analysis"])
    spectral_pair_rule_v7 = spectral_v7.pop("pair_rule")
    spectral_pair_rule_v71 = spectral_v71.pop("pair_rule")
    _assert_equal(spectral_v7, spectral_v71, "spectral executable parameters")
    _assert_equal(
        spectral_pair_rule_v7.replace("v7.", "VERSION."),
        spectral_pair_rule_v71.replace("v7.1.", "VERSION."),
        "spectral pair-rule semantics",
    )

    support_v7 = json.loads(json.dumps(v7["support_contract"]))
    support_v71 = json.loads(json.dumps(v71["support_contract"]))
    support_v7["coherence_only_resolution_margin"].pop("selection_origin")
    support_v71["coherence_only_resolution_margin"].pop("selection_origin")
    _assert_equal(support_v7, support_v71, "support-contract executable parameters")

    comparators_v7 = dict(v7["comparators"])
    comparators_v71 = dict(v71["comparators"])
    comparator_scope_v7 = comparators_v7.pop("comparison_scope")
    comparator_scope_v71 = comparators_v71.pop("comparison_scope")
    _assert_equal(comparators_v7, comparators_v71, "comparator definitions")
    if "only for tensor coherence" not in comparator_scope_v7:
        raise ValueError("Unexpected v7 comparator scope annotation.")
    if "only for tensor coherence" not in comparator_scope_v71:
        raise ValueError("Unexpected v7.1 comparator scope annotation.")

    exact_top_level = (
        "dataset_record",
        "dataset_doi",
        "reference_sampling_rule",
        "mrc_header_spacing_absolute_tolerance_um",
        "field_of_view_relative_tolerance",
    )
    for key in exact_top_level:
        _assert_equal(v7[key], v71[key], key)

    confirmation_fields = (
        "fields_per_structure",
        "selection_salt",
        "all_signal_levels_in_selected_fields",
        "threshold_refitting_permitted",
        "endpoint_addition_or_removal_permitted",
        "primary_safety_rules",
        "separate_incremental_coherence_utility_rules",
    )
    for key in confirmation_fields:
        _assert_equal(v7["confirmation"][key], v71["confirmation"][key], key)

    original_structure = dict(v7["structures"]["F-actin_nonlinear"])
    amended_structure = dict(v71["structures"]["F-actin_nonlinear"])
    original_structure.pop("role")
    amended_structure.pop("role")
    _assert_equal(original_structure, amended_structure, "nonlinear structure specification")

    if float(v7["raw_sim_sampling_um"]) != 0.0626:
        raise ValueError("Unexpected original v7 nonlinear spacing.")
    if float(v71["raw_sim_sampling_um"]) != 0.0604:
        raise ValueError("Unexpected amended v7.1 nonlinear spacing.")
    return {
        "passes": True,
        "identical_sections": [
            *exact_sections,
            "physical_tensor executable parameters",
            "spectral_analysis executable parameters",
            "support_contract executable parameters",
            "comparators executable definitions",
        ],
        "identical_confirmation_fields": list(confirmation_fields),
        "permitted_documentation_only_differences": [
            "physical_tensor.amendment_rule added",
            "spectral_analysis.pair_rule version label",
            "support_contract.coherence_only_resolution_margin.selection_origin wording",
            "comparators.comparison_scope wording",
            "structure role wording",
        ],
        "only_scientific_difference": (
            "Nonlinear raw-grid calibration changed from 0.0626 um to "
            "0.0604 um; reference spacing follows the unchanged 3x rule."
        ),
        "measurement_definition_changed": False,
        "thresholds_or_gates_changed": False,
        "selected_fields_changed": False,
    }


def _verify_source(
    structure: str,
    specification: dict[str, Any],
    *,
    v7_lock: dict[str, Any],
    v71_lock: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    directory = Path(specification["directory"])
    receipt_path = directory / "archive_receipt.json"
    rows_path = directory / "tensor_cases.jsonl"
    receipt = _read_json(receipt_path)
    source_lock_path = Path(specification["lock_path"])
    source_lock = _read_json(source_lock_path)
    source_lock_sha256 = sha256_file(source_lock_path)

    if receipt["protocol_version"] != specification["protocol"]:
        raise ValueError(f"Protocol mismatch for {structure}.")
    if receipt["structure"] != structure:
        raise ValueError(f"Structure mismatch for {structure}.")
    if receipt[specification["receipt_lock_key"]] != source_lock_sha256:
        raise ValueError(f"Receipt-to-lock hash mismatch for {structure}.")
    if receipt["implementation"]["sha256"] != source_lock["implementation_sha256"]:
        raise ValueError(f"Implementation digest mismatch for {structure}.")
    if receipt["config"]["sha256"] != source_lock["config"]["sha256"]:
        raise ValueError(f"Config digest mismatch for {structure}.")

    artifact = receipt["artifacts"]["tensor_cases"]
    if (ROOT / artifact["path"]).resolve() != rows_path.resolve():
        raise ValueError(f"Receipt row path mismatch for {structure}.")
    if rows_path.stat().st_size != int(artifact["bytes"]):
        raise ValueError(f"Receipt row byte mismatch for {structure}.")
    if sha256_file(rows_path) != artifact["sha256"]:
        raise ValueError(f"Receipt row hash mismatch for {structure}.")

    rows = _read_jsonl(rows_path)
    if len(rows) != int(specification["expected_rows"]):
        raise ValueError(f"Unexpected row count for {structure}.")
    if len(rows) != int(receipt["rows"]):
        raise ValueError(f"Receipt row count mismatch for {structure}.")
    if len({str(row["pair_id"]) for row in rows}) != int(
        specification["expected_pairs"]
    ):
        raise ValueError(f"Unexpected pair count for {structure}.")
    if int(receipt["pairs"]) != int(specification["expected_pairs"]):
        raise ValueError(f"Receipt pair count mismatch for {structure}.")
    if any(row["structure"] != structure for row in rows):
        raise ValueError(f"Foreign structure row found in {structure} source.")

    selected = receipt["selection"]["selected_cells"]
    if structure == "F-actin_linear":
        expected_selected = v7_lock["confirmation"]["selected_cells"][structure]
    else:
        expected_selected = v71_lock["selected_cells"]
        _assert_equal(
            expected_selected,
            v7_lock["confirmation"]["selected_cells"][structure],
            "carried-forward nonlinear cells",
        )
    if selected != expected_selected:
        raise ValueError(f"Selected cells differ from lock for {structure}.")

    return rows, {
        "structure": structure,
        "receipt": _artifact(receipt_path),
        "tensor_rows": _artifact(rows_path),
        "source_lock": _artifact(source_lock_path),
        "implementation_sha256": receipt["implementation"]["sha256"],
        "selected_cells": selected,
        "reference_fields": len(selected),
        "paired_acquisitions": receipt["pairs"],
        "endpoint_rows": receipt["rows"],
    }


def main() -> None:
    v7_config = _read_json(V7_CONFIG)
    v71_config = _read_json(V71_CONFIG)
    v7_lock = _read_json(V7_LOCK)
    v71_lock = _read_json(V71_LOCK)

    compatibility = _scientific_compatibility(v7_config, v71_config)
    lock_verification = [
        _verify_lock_files(v7_lock, label="v7 linear/source lock"),
        _verify_lock_files(v71_lock, label="v7.1 nonlinear lock"),
    ]
    archive_verification = [
        _verify_archive(
            v7_lock["archives"]["F-actin_linear"],
            structure="F-actin_linear",
        ),
        _verify_archive(v71_lock["archive"], structure="F-actin_nonlinear"),
    ]

    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for structure, specification in INPUTS.items():
        source_rows, source = _verify_source(
            structure,
            specification,
            v7_lock=v7_lock,
            v71_lock=v71_lock,
        )
        rows.extend(source_rows)
        sources.append(source)
    if len(rows) != 1680:
        raise ValueError("Combined confirmation must contain exactly 1,680 rows.")
    if len({str(row["case_id"]) for row in rows}) != len(rows):
        raise ValueError("Combined confirmation contains duplicate case identifiers.")

    rules = {
        **v7_config["confirmation"]["primary_safety_rules"],
        **v7_config["confirmation"][
            "separate_incremental_coherence_utility_rules"
        ],
    }
    evaluation = evaluate_v7_confirmation(rows, rules=rules)
    safety_passes = bool(evaluation["measurement_safety"]["passes"])
    utility = evaluation["incremental_coherence_utility"]
    high_impact_superiority_established = safety_passes and utility["passes"] is True

    OUTPUT.mkdir(parents=True, exist_ok=True)
    combined_rows = OUTPUT / "combined_tensor_cases.jsonl"
    with combined_rows.open("w", encoding="utf-8") as stream:
        for row in sorted(rows, key=lambda item: str(item["case_id"])):
            stream.write(json.dumps(row, allow_nan=False) + "\n")

    payload = {
        "schema_version": (
            "nostos-biosr-tensor-v7-mixed-lock-combined-confirmation-audit/1.0"
        ),
        "status": evaluation["status"],
        "evaluation": evaluation,
        "decision": {
            "measurement_transfer_gate": "PASS" if safety_passes else "FAIL",
            "selective_qc_superiority_gate": utility["status"],
            "high_impact_validity_contract_superiority_established": (
                high_impact_superiority_established
            ),
            "next_validation_gate": (
                "A separately frozen controlled-degradation challenge with known "
                "failure labels must create comparator-invalid emissions and test "
                "silent-invalid risk at matched coverage. More clean BioSR samples "
                "cannot answer this question."
            ),
        },
        "scope": {
            "structures": sorted(INPUTS),
            "reference_fields": sum(item["reference_fields"] for item in sources),
            "paired_acquisitions": sum(
                int(item["paired_acquisitions"]) for item in sources
            ),
            "endpoint_rows": len(rows),
            "eligible_endpoint_rows": evaluation["measurement_safety"][
                "full_contract"
            ]["eligible"],
        },
        "mixed_lock_compatibility": compatibility,
        "lock_verification": lock_verification,
        "archive_verification": archive_verification,
        "sources": sources,
        "lineage": {
            "v7_config": _artifact(V7_CONFIG),
            "v7_1_config": _artifact(V71_CONFIG),
            "v7_lock": _artifact(V7_LOCK),
            "v7_1_lock": _artifact(V71_LOCK),
            "auditor": _artifact(Path(__file__)),
        },
        "artifacts": {"combined_tensor_cases": _artifact(combined_rows)},
        "interpretation": {
            "supported": (
                "The frozen tensor coherence and orientation-distribution "
                "measurements transferred safely across the selected linear and "
                "nonlinear F-actin acquisition families against SIM_gt_a."
            ),
            "not_supported": (
                "The evidence does not show that the complete validity contract "
                "outperforms conventional acquisition QC because the comparator "
                "made no invalid emissions in this clean confirmation tranche."
            ),
            "claim_boundary": (
                "Technical paired-acquisition measurement transfer only; not image "
                "restoration accuracy, ground-truth biology, diagnosis, clinical "
                "validity, or a universal cross-tissue claim."
            ),
        },
    }
    output_path = OUTPUT / "combined_confirmation_audit.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                **_artifact(output_path),
                "status": payload["status"],
                "decision": payload["decision"],
                "scope": payload["scope"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
