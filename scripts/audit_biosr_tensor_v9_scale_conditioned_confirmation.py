"""Independent post-result audit of the locked BioSR tensor v9 confirmation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from nostos.validation.controlled_degradation_v8 import (
    deterministic_condition_seed,
)
from nostos.validation.paired_acquisition_support import sha256_file
from nostos.validation.scale_conditioned_support_v9 import (
    evaluate_v9_scale_conditioned_confirmation,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v9_scale_conditioned_confirmation.locked.json"
)
V8_CONFIG = (
    ROOT
    / "configs/paired_acquisition_tensor_v8_controlled_degradation_pilot.locked.json"
)
LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v9_scale_conditioned_confirmation_lock.json"
)
V7_LOCK = ROOT / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
V8_LOCK = (
    ROOT
    / "manifests/paired_acquisition_tensor_v8_controlled_degradation_pilot_lock.json"
)
INPUT = ROOT / "outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation"
RECEIPT = INPUT / "confirmation_receipt.json"
ROWS = INPUT / "tensor_cases.jsonl"
PAIR_INDEX = INPUT / "pair_index.json"
OUTPUT = ROOT / "outputs/nostos0-biosr-tensor-v9-final-audit"


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
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    v8_config = json.loads(V8_CONFIG.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    v7_lock = json.loads(V7_LOCK.read_text(encoding="utf-8"))
    v8_lock = json.loads(V8_LOCK.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    if receipt["lock"]["sha256"] != sha256_file(LOCK):
        raise RuntimeError("Confirmation receipt does not match the v9 lock.")
    if receipt["config"]["sha256"] != sha256_file(CONFIG):
        raise RuntimeError("Confirmation receipt does not match the v9 config.")
    if receipt["implementation"]["sha256"] != lock["implementation_sha256"]:
        raise RuntimeError("Confirmation implementation differs from the lock.")
    for item in lock["files"]:
        path = ROOT / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256_file(path) != item["sha256"]
        ):
            raise RuntimeError(f"v9 locked-file mismatch: {item['path']}")
    for path, key in ((ROWS, "tensor_cases"), (PAIR_INDEX, "pair_index")):
        artifact = receipt["artifacts"][key]
        if path.stat().st_size != int(artifact["bytes"]):
            raise RuntimeError(f"Receipt byte mismatch: {path}")
        if sha256_file(path) != artifact["sha256"]:
            raise RuntimeError(f"Receipt hash mismatch: {path}")
    archive_verification = []
    for structure, archive in lock["archives"].items():
        path = Path(archive["path"])
        if path.stat().st_size != int(archive["bytes"]):
            raise RuntimeError(f"Archive byte mismatch for {structure}.")
        observed = sha256_file(path)
        if observed != archive["sha256"]:
            raise RuntimeError(f"Archive hash mismatch for {structure}.")
        archive_verification.append(
            {
                "structure": structure,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": observed,
            }
        )

    pair_index = json.loads(PAIR_INDEX.read_text(encoding="utf-8"))
    records = pair_index["records"]
    if len(records) != 16 or receipt["base_pairs"] != 16:
        raise RuntimeError("v9 must contain exactly sixteen base pairs.")
    selected_by_structure = {
        structure: sorted(
            {
                str(record["cell_id"])
                for record in records
                if str(record["structure"]) == structure
            }
        )
        for structure in config["selection"]["selected_cells"]
    }
    for structure, selected in selected_by_structure.items():
        if set(selected) != set(config["selection"]["selected_cells"][structure]):
            raise RuntimeError(f"v9 pair-index selection mismatch for {structure}.")
        prior = set(v7_lock["confirmation"]["selected_cells"][structure])
        prior.update(v8_lock["selected_cells"][structure])
        if prior.intersection(selected):
            raise RuntimeError(f"v9 cells overlap earlier evidence for {structure}.")

    rows = _read_jsonl(ROWS)
    if len(rows) != 2240 or receipt["rows"] != 2240:
        raise RuntimeError("v9 must contain exactly 2,240 endpoint rows.")
    if len({str(row["case_id"]) for row in rows}) != len(rows):
        raise RuntimeError("Duplicate v9 case identifiers detected.")
    conditions = {item["id"]: item for item in v8_config["degradations"]}
    base_seed = int(config["randomness"]["base_seed"])
    support = config["v9_scale_conditioned_support"]
    formula_failures = []
    condition_counts: dict[str, int] = {key: 0 for key in conditions}
    for row in rows:
        metadata = row["metadata"]
        condition_id = str(metadata["degradation_id"])
        if metadata["degradation_specification"] != conditions[condition_id]:
            raise RuntimeError(f"Degradation specification mismatch: {condition_id}")
        expected_seed = deterministic_condition_seed(
            base_seed,
            pair_id=str(row["pair_id"]).split("|degradation_")[0],
            condition_id=condition_id,
        )
        if int(metadata["condition_seed"]) != expected_seed:
            raise RuntimeError(f"Condition seed mismatch: {row['case_id']}")
        condition_counts[condition_id] += 1
        if str(row["endpoint_family"]) != "tensor_coherence":
            if not math.isclose(
                float(row["scores"]["full_contract"]),
                float(row["scores"]["full_contract_v7"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                formula_failures.append(str(row["case_id"]))
            continue
        components = row["support_components"]
        raw = float(components["acquisition_qc"]) * (
            float(support["minimum_samples_per_scale"])
            / float(components["samples_per_scale"])
        ) ** float(support["scale_exponent"])
        normalized = raw / float(support["acceptance_boundary"])
        expected_full = max(
            float(components["acquisition_qc"]),
            float(components["physical_sampling"]),
            float(components["perturbation_stability"]),
            float(components["measurement_identifiability"]),
            normalized,
        )
        recorded = metadata["v9_scale_conditioned_support"]
        if not (
            math.isclose(
                float(recorded["raw_scale_conditioned_acquisition_risk"]),
                raw,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(recorded["normalized_score"]),
                normalized,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(row["scores"]["full_contract"]),
                expected_full,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            formula_failures.append(str(row["case_id"]))
    if formula_failures:
        raise RuntimeError(f"v9 formula audit failed: {formula_failures[:5]}")
    expected_per_condition = 16 * 5 * 2
    if any(value != expected_per_condition for value in condition_counts.values()):
        raise RuntimeError("Each degradation must contain exactly 160 endpoint rows.")

    recomputed = evaluate_v9_scale_conditioned_confirmation(
        rows, gates=config["confirmation_gates"]
    )
    if recomputed != receipt["confirmation_evaluation"]:
        raise RuntimeError("Recomputed v9 evaluation differs from the receipt.")
    if recomputed["status"] != "pass" or recomputed["passes"] is not True:
        raise RuntimeError("The locked v9 confirmation did not pass.")

    payload = {
        "schema_version": "nostos-biosr-tensor-v9-independent-final-audit/1.0",
        "status": "verified_pass",
        "confirmation_evaluation": recomputed,
        "verification": {
            "locked_files_verified": len(lock["files"]),
            "archives_rehashed": archive_verification,
            "selected_cells_are_disjoint_from_v7_and_v8": True,
            "base_pairs_verified": len(records),
            "endpoint_rows_verified": len(rows),
            "unique_case_identifiers": len(rows),
            "degradation_conditions_verified": condition_counts,
            "deterministic_condition_seeds_verified": True,
            "v9_formula_rows_verified": len(rows),
            "evaluation_recomputed_exactly": True,
        },
        "lineage": {
            "config": _artifact(CONFIG),
            "lock": _artifact(LOCK),
            "receipt": _artifact(RECEIPT),
            "rows": _artifact(ROWS),
            "pair_index": _artifact(PAIR_INDEX),
            "auditor": _artifact(Path(__file__)),
        },
        "decision": {
            "promote_v9_tensor_coherence_profile": True,
            "confirmed_scope": (
                "Selective tensor-coherence measurement support for linear and "
                "nonlinear BioSR F-actin under the frozen controlled-degradation "
                "challenge."
            ),
            "not_confirmed": [
                "universal cross-tissue validity",
                "orientation-distribution superiority",
                "biological ground truth",
                "image-restoration accuracy",
                "diagnosis or clinical utility",
                "Nature-level independent multi-laboratory validation",
            ],
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT / "final_audit.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                **_artifact(output_path),
                "status": payload["status"],
                "coverage": recomputed["full_contract"]["coverage"],
                "risk": recomputed["full_contract"]["risk"],
                "qc_risk": recomputed["conventional_acquisition_qc"]["risk"],
                "relative_risk_reduction": recomputed["operating_point"][
                    "relative_risk_reduction_vs_qc"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
