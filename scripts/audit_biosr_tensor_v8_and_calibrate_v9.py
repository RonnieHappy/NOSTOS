"""Seal the v8 failure and calibrate the scale-conditioned v9 repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nostos.validation.paired_acquisition_support import sha256_file
from nostos.validation.scale_conditioned_support_v9 import (
    attach_v9_scale_conditioned_score,
    calibrate_v9_scale_conditioned_support,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v8_controlled_degradation_pilot_lock.json"
)
PILOT = ROOT / "outputs/nostos0-biosr-tensor-v8-controlled-degradation-pilot"
RECEIPT = PILOT / "pilot_receipt.json"
ROWS = PILOT / "tensor_cases.jsonl"
OUTPUT = ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-development"


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt["lock"]["sha256"] != sha256_file(LOCK):
        raise RuntimeError("v8 pilot receipt does not match the v8 lock.")
    if receipt["artifacts"]["tensor_cases"]["sha256"] != sha256_file(ROWS):
        raise RuntimeError("v8 tensor rows differ from the pilot receipt.")
    if receipt["pilot_evaluation"]["status"] != "fail":
        raise RuntimeError("v9 repair is authorized only after the sealed v8 failure.")
    if receipt["pilot_evaluation"]["assessable"] is not True:
        raise RuntimeError("The v8 failure was not assessable.")
    for item in lock["files"]:
        path = ROOT / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256_file(path) != item["sha256"]
        ):
            raise RuntimeError(f"v8 lock lineage failure: {item['path']}")

    rows = _read_jsonl(ROWS)
    if len(rows) != 1680:
        raise RuntimeError("v8 development requires exactly 1,680 sealed rows.")
    gates = {
        "minimum_negative_control_coverage": 0.80,
        "maximum_negative_control_risk": 0.10,
        "minimum_overall_coverage": 0.80,
        "maximum_overall_risk": 0.05,
        "maximum_cluster_bootstrap_risk_upper95": 0.10,
        "minimum_relative_risk_reduction_vs_qc": 0.25,
        "minimum_invalid_fraction_among_qc_only_rejections": 0.25,
        "minimum_bootstrap_probability_full_better": 0.90,
    }
    calibration = calibrate_v9_scale_conditioned_support(
        rows,
        minimum_samples_per_scale=4.0,
        primary_exponent=0.5,
        candidate_boundaries=(
            0.150,
            0.175,
            0.200,
            0.225,
            0.250,
            0.275,
            0.300,
            0.325,
            0.350,
        ),
        sensitivity_exponents=(0.0, 1.0, 1.5),
        gates=gates,
        draws=10_000,
        seed=26_082_982,
    )
    if calibration["selected"] is None:
        raise RuntimeError("v9 development found no admissible operating point.")
    selected = calibration["selected"]
    attached = attach_v9_scale_conditioned_score(
        rows,
        minimum_samples_per_scale=4.0,
        exponent=0.5,
        acceptance_boundary=float(selected["acceptance_boundary"]),
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    attached_path = OUTPUT / "development_tensor_cases_v9.jsonl"
    with attached_path.open("w", encoding="utf-8") as stream:
        for row in sorted(attached, key=lambda item: str(item["case_id"])):
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload = {
        "schema_version": "nostos-biosr-tensor-v9-scale-conditioned-development/1.0",
        "status": calibration["status"],
        "outcome_role": "development_only_outcome_informed",
        "v8_failure": {
            "status": receipt["pilot_evaluation"]["status"],
            "assessable": receipt["pilot_evaluation"]["assessable"],
            "full_coverage": receipt["pilot_evaluation"]["overall"][
                "full_contract"
            ]["coverage"],
            "full_risk": receipt["pilot_evaluation"]["overall"][
                "full_contract"
            ]["risk"],
            "qc_risk": receipt["pilot_evaluation"]["overall"][
                "conventional_acquisition_qc"
            ]["risk"],
            "comparator_invalid_emissions": receipt["pilot_evaluation"][
                "assessability"
            ]["comparator_invalid_emissions"],
            "invalid_reference_fields": receipt["pilot_evaluation"][
                "assessability"
            ]["invalid_reference_fields"],
            "failure_mechanism": (
                "Every eligible coherence row was accepted. Stable blur and "
                "resampling bias survived self-perturbation and the v7 resolution "
                "margin, so full-contract and QC risk were identical."
            ),
        },
        "repair": {
            "name": "scale_conditioned_acquisition_support",
            "formula": (
                "acquisition_qc_risk * (4 / samples_per_requested_scale)^0.5 "
                "/ acceptance_boundary"
            ),
            "v7_strong_blur_margin_role": (
                "retained as a diagnostic but removed from coherence acceptance "
                "after failing to detect stable degradation bias"
            ),
            "selection_is_outcome_informed": True,
            "independent_confirmation_required": True,
        },
        "development_gates": gates,
        "calibration": calibration,
        "lineage": {
            "v8_lock": _artifact(LOCK),
            "v8_receipt": _artifact(RECEIPT),
            "v8_rows": _artifact(ROWS),
            "auditor": _artifact(Path(__file__)),
            "scale_conditioned_support_implementation": _artifact(
                ROOT / "src/nostos/validation/scale_conditioned_support_v9.py"
            ),
        },
        "artifacts": {"v9_development_rows": _artifact(attached_path)},
        "claim_boundary": (
            "The selected v9 boundary is development evidence derived from v8 "
            "outcomes. It cannot be described as confirmed until it passes on "
            "different cells selected and locked before pixel access."
        ),
    }
    output_path = OUTPUT / "development_audit.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                **_artifact(output_path),
                "status": calibration["status"],
                "selected_exponent": calibration["primary_exponent"],
                "selected_boundary": selected["acceptance_boundary"],
                "coverage": selected["full"]["coverage"],
                "risk": selected["full"]["risk"],
                "risk_upper95": selected["full"][
                    "cluster_bootstrap_risk_upper95"
                ],
                "qc_risk": selected["qc"]["risk"],
                "bootstrap_probability_full_better": selected[
                    "risk_coverage_evidence"
                ]["bootstrap"]["probability_full_better"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
