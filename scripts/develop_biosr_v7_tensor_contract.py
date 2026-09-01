"""Evaluate the v7 physical-tensor contract on disclosed CCP, ER and Microtubules fields."""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    audit_pair_registration,
    image_sha256,
    read_mrc_bytes,
    sha256_file,
    shared_spectral_band_cycles_per_mm,
)
from nostos.validation.tensor_support_v7 import (
    evaluate_tensor_pair,
    measure_tensor_support,
    policy_accepts,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/paired_acquisition_support_v6.locked.json"
FAILURE_RECEIPT = ROOT / "manifests/paired_acquisition_support_v6_confirmation_failure_receipt.json"
DEFAULT_OUTPUT = ROOT / "outputs/nostos0-biosr-v7-tensor-contract-development"
SOURCES = {
    "CCPs": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\CCPs.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-ccp-threshold-calibration-v5/pair_index.json",
    },
    "ER": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\ER.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-er-threshold-calibration-v5/pair_index.json",
    },
    "Microtubules": {
        "archive": Path(r"<DATA_ROOT>\data\public\measurement-support-benchmark\biosr\archives\Microtubules.zip"),
        "pair_index": ROOT / "outputs/nostos0-biosr-v6-microtubules-initial-confirmation/pair_index.json",
    },
}
CONDITIONS = (
    "full_contract",
    "conventional_acquisition_qc",
    "full_without_jackknife",
    "full_without_perturbation",
    "full_without_identifiability",
    "always_emit",
)


def _process_cell(
    archive: str,
    records_payload: list[dict[str, Any]],
    config: dict[str, Any],
    derivative_scale_fraction: float,
    integration_scale_factor: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    records = [BioSRPairRecord(**item) for item in records_payload]
    first = records[0]
    scales = tuple(float(value) for value in config["physical_scales_um"])
    band = shared_spectral_band_cycles_per_mm(
        config, first.effective_input_spacing_um
    )
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as opened:
        reference_payload = opened.read(first.reference_member)
        reference_image = read_mrc_bytes(reference_payload)
        reference = measure_tensor_support(
            reference_image,
            grid_spacing_um=first.reference_spacing_um,
            effective_spacing_um=first.reference_spacing_um,
            scales_um=scales,
            spectral_band_cycles_per_mm=band,
            derivative_scale_fraction=derivative_scale_fraction,
            integration_scale_factor=integration_scale_factor,
        )
        for record in records:
            raw_payload = opened.read(record.input_member)
            raw = read_mrc_bytes(raw_payload)
            input_image = np.mean(raw.astype(np.float64), axis=0)
            registration = audit_pair_registration(
                input_image,
                reference_image,
                reference_spacing_um=record.reference_spacing_um,
                effective_input_spacing_um=record.effective_input_spacing_um,
            )
            measured = measure_tensor_support(
                input_image,
                grid_spacing_um=record.input_grid_spacing_um,
                effective_spacing_um=record.effective_input_spacing_um,
                scales_um=scales,
                spectral_band_cycles_per_mm=band,
                derivative_scale_fraction=derivative_scale_fraction,
                integration_scale_factor=integration_scale_factor,
            )
            rows.extend(
                evaluate_tensor_pair(
                    pair_id=record.pair_id,
                    reference_group_id=record.reference_group_id,
                    structure=record.structure,
                    effective_input_spacing_um=record.effective_input_spacing_um,
                    registration=registration,
                    input_measurement=measured,
                    reference_measurement=reference,
                    scales_um=scales,
                    metadata={
                        "cell_id": record.cell_id,
                        "signal_level_ordinal": record.signal_level,
                        "input_member": record.input_member,
                        "reference_member": record.reference_member,
                        "input_mean_pixel_sha256": image_sha256(input_image),
                        "reference_pixel_sha256": image_sha256(reference_image),
                        "development_role": (
                            "post_v6_failure_development"
                            if record.structure == "Microtubules"
                            else "preexisting_disclosed_development"
                        ),
                    },
                )
            )
    return {
        "cell_id": first.cell_id,
        "structure": first.structure,
        "rows": rows,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _cluster_upper(rows: list[dict[str, Any]], condition: str, seed: int) -> float | None:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["structure"], row["reference_group_id"])].append(row)
    if not grouped:
        return None
    strata: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (structure, _), group in grouped.items():
        accepted = [row for row in group if policy_accepts(row, condition)]
        strata[structure].append(
            (len(accepted), sum(bool(row["invalid"]) for row in accepted))
        )
    generator = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(10_000):
        accepted_total = 0
        invalid_total = 0
        for counts in strata.values():
            indices = generator.integers(0, len(counts), size=len(counts))
            for index in indices:
                accepted, invalid = counts[int(index)]
                accepted_total += accepted
                invalid_total += invalid
        if accepted_total:
            estimates.append(invalid_total / accepted_total)
    return float(np.quantile(estimates, 0.95)) if estimates else None


def _policy_summary(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if row["pair_registration_eligible"] and row["reference_eligible"]
    ]
    accepted = [row for row in eligible if policy_accepts(row, condition)]
    combinations = []
    for structure, family in sorted(
        {(row["structure"], row["endpoint_family"]) for row in eligible}
    ):
        subset = [
            row
            for row in eligible
            if row["structure"] == structure and row["endpoint_family"] == family
        ]
        selected = [row for row in subset if policy_accepts(row, condition)]
        failures = sum(bool(row["invalid"]) for row in selected)
        combinations.append(
            {
                "structure": structure,
                "endpoint_family": family,
                "eligible": len(subset),
                "accepted": len(selected),
                "coverage": len(selected) / len(subset),
                "invalid": failures,
                "risk": failures / len(selected) if selected else None,
                "reference_fields": len(
                    {row["reference_group_id"] for row in subset}
                ),
            }
        )
    invalid = sum(bool(row["invalid"]) for row in accepted)
    return {
        "eligible": len(eligible),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(eligible),
        "invalid": invalid,
        "risk": invalid / len(accepted) if accepted else None,
        "cluster_bootstrap_risk_upper95": _cluster_upper(
            eligible, condition, 26082917
        ),
        "combinations": combinations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--derivative-scale-fraction", type=float, default=0.5)
    parser.add_argument("--integration-scale-factor", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.derivative_scale_fraction <= 0 or args.integration_scale_factor <= 0:
        raise ValueError("Tensor scale factors must be positive.")
    if args.workers < 1:
        raise ValueError("workers must be positive.")
    failure = json.loads(FAILURE_RECEIPT.read_text(encoding="utf-8"))
    if failure["decision"]["microtubules_reclassified_for_next_version"] != "development_only":
        raise ValueError("Microtubules has not been explicitly reclassified for v7 development.")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    jobs: list[tuple[str, str, list[dict[str, Any]]]] = []
    source_receipts = []
    for structure, source in SOURCES.items():
        pair_index = json.loads(source["pair_index"].read_text(encoding="utf-8"))
        records = [BioSRPairRecord(**item) for item in pair_index["records"]]
        by_cell: dict[str, list[BioSRPairRecord]] = defaultdict(list)
        for record in records:
            if record.structure != structure:
                raise ValueError(f"Pair-index structure mismatch for {structure}.")
            by_cell[record.cell_id].append(record)
        jobs.extend(
            (
                str(source["archive"]),
                structure,
                [asdict(record) for record in cell_records],
            )
            for cell_records in by_cell.values()
        )
        source_receipts.append(
            {
                "structure": structure,
                "archive": str(source["archive"]),
                "archive_bytes": source["archive"].stat().st_size,
                "pair_index": str(source["pair_index"].relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "pair_index_sha256": sha256_file(source["pair_index"]),
                "fields": len(by_cell),
                "pairs": len(records),
            }
        )

    all_rows: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _process_cell,
                archive,
                records,
                config,
                args.derivative_scale_fraction,
                args.integration_scale_factor,
            ): (structure, records[0]["cell_id"])
            for archive, structure, records in jobs
        }
        for future in as_completed(futures):
            result = future.result()
            all_rows.extend(result["rows"])
            checkpoints.append(
                {
                    "structure": result["structure"],
                    "cell_id": result["cell_id"],
                    "rows": len(result["rows"]),
                    "elapsed_seconds": result["elapsed_seconds"],
                }
            )
            print(
                f"completed {result['structure']} {result['cell_id']} "
                f"in {result['elapsed_seconds']:.1f} s",
                flush=True,
            )
    all_rows.sort(key=lambda row: row["case_id"])
    policies = {condition: _policy_summary(all_rows, condition) for condition in CONDITIONS}
    full = policies["full_contract"]
    qc = policies["conventional_acquisition_qc"]
    payload = {
        "schema_version": "nostos-biosr-v7-tensor-contract-development/1.0",
        "status": "development_complete_pending_v7_freeze",
        "scope": {
            "structures": list(SOURCES),
            "reference_fields": sum(item["fields"] for item in source_receipts),
            "paired_acquisitions": sum(item["pairs"] for item in source_receipts),
            "f_actin_image_members_decoded": 0,
            "f_actin_endpoint_outcomes_computed": 0,
        },
        "selected_tensor": {
            "derivative_scale_fraction": args.derivative_scale_fraction,
            "integration_scale_factor": args.integration_scale_factor,
            "selection_basis": "explicit development candidate; no candidate becomes frozen until the separate field-clustered audit passes and the cross-candidate decision is sealed",
            "candidate_benchmark": {
                "path": "outputs/nostos0-biosr-v7-physical-tensor-development/candidate_benchmark.json",
                "sha256": sha256_file(
                    ROOT / "outputs/nostos0-biosr-v7-physical-tensor-development/candidate_benchmark.json"
                ),
            },
        },
        "fixed_dimensionless_policy_threshold": 1.0,
        "policies": policies,
        "development_gate": {
            "target_observed_risk": 0.10,
            "maximum_cluster_bootstrap_risk_upper95": 0.15,
            "minimum_overall_coverage": 0.80,
            "minimum_structure_family_coverage": 0.70,
            "maximum_coverage_loss_vs_qc": 0.10,
            "full_minus_qc_risk": full["risk"] - qc["risk"],
            "coverage_loss_vs_qc": qc["coverage"] - full["coverage"],
            "passes": bool(
                full["risk"] <= 0.10
                and full["cluster_bootstrap_risk_upper95"] <= 0.15
                and full["coverage"] >= 0.80
                and all(
                    item["coverage"] >= 0.70
                    and item["risk"] is not None
                    and item["risk"] <= 0.10
                    for item in full["combinations"]
                )
                and full["risk"] <= qc["risk"]
                and qc["coverage"] - full["coverage"] <= 0.10
            ),
        },
        "sources": source_receipts,
        "lineage": {
            "v6_failure_receipt_sha256": sha256_file(FAILURE_RECEIPT),
            "physical_tensor_sha256": sha256_file(
                ROOT / "src/nostos/features/physical_tensor.py"
            ),
            "tensor_contract_sha256": sha256_file(
                ROOT / "src/nostos/validation/tensor_support_v7.py"
            ),
            "runner_sha256": sha256_file(Path(__file__)),
        },
        "checkpoints": sorted(
            checkpoints, key=lambda item: (item["structure"], item["cell_id"])
        ),
        "claim_boundary": "Post-failure development on disclosed CCP, ER and consumed Microtubules fields; not confirmation and not evidence about F-actin.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    rows_path = args.output / "tensor_cases.jsonl"
    with rows_path.open("w", encoding="utf-8") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    payload["artifacts"] = {
        "tensor_cases": {
            "path": str(rows_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
            "bytes": rows_path.stat().st_size,
            "sha256": sha256_file(rows_path),
        }
    }
    output_path = args.output / "tensor_contract_development.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "path": str(output_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
                "development_gate_passed": payload["development_gate"]["passes"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
