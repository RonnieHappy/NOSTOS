"""Audit only the frozen BioSR score-design partition and select a support formula.

This script is intentionally unable to consume threshold-calibration or confirmation
rows. It verifies every input receipt, reconstructs the three prospectively locked
input-only candidate scores, and reports both micro and macro risk-coverage results.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from nostos.validation.paired_acquisition_support import aurc, eligible_rows, sha256_file, write_rows_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_CONFIG = PROJECT_ROOT / "configs" / "paired_acquisition_score_design_candidates_v2.locked.json"
CANDIDATE_LOCK = PROJECT_ROOT / "manifests" / "paired_acquisition_support_score_design_candidates_v2_lock.json"


def verify_developmental_pilot_manifest(
    manifest_path: Path,
    row_paths: Sequence[Path],
) -> dict[str, Any]:
    """Verify an explicitly receipted small pilot without promoting it to confirmation."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "nostos-biosr-developmental-pilot/1.0":
        raise RuntimeError(f"Unsupported developmental-pilot manifest: {manifest_path}")
    if manifest.get("status") != "post_consolidation_deterministic_receipt":
        raise RuntimeError(f"Developmental-pilot manifest is not a final receipt: {manifest_path}")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise RuntimeError("Developmental-pilot manifest contains no inputs.")

    expected_paths = {
        (PROJECT_ROOT / str(item["endpoint_cases_path"])).resolve(): item
        for item in inputs
    }
    observed_paths = {path.resolve() for path in row_paths}
    if observed_paths != set(expected_paths):
        raise RuntimeError(
            "Pilot inputs do not exactly match the receipted set: "
            f"expected {sorted(map(str, expected_paths))}, observed {sorted(map(str, observed_paths))}"
        )

    for endpoint_path, item in expected_paths.items():
        receipt_path = (PROJECT_ROOT / str(item["archive_receipt_path"])).resolve()
        pair_index_path = endpoint_path.parent / "pair_index.json"
        for artifact in (endpoint_path, receipt_path, pair_index_path):
            if not artifact.is_file():
                raise FileNotFoundError(f"Missing pilot artifact: {artifact}")
        checks = (
            (endpoint_path, "endpoint_cases_sha256", None),
            (receipt_path, "archive_receipt_sha256", "archive_receipt_bytes"),
            (pair_index_path, "pair_index_sha256", None),
        )
        for artifact, hash_key, bytes_key in checks:
            observed_hash = sha256_file(artifact)
            if observed_hash != item.get(hash_key):
                raise RuntimeError(
                    f"Pilot artifact hash mismatch for {artifact}: "
                    f"expected {item.get(hash_key)}, observed {observed_hash}"
                )
            if bytes_key is not None and artifact.stat().st_size != int(item[bytes_key]):
                raise RuntimeError(f"Pilot artifact byte-count mismatch for {artifact}.")

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        selected_cells = sorted(str(value) for value in item["selected_cell_ids"])
        receipt_cells = sorted(str(checkpoint["cell_id"]) for checkpoint in receipt["checkpoints"])
        if receipt_cells != selected_cells:
            raise RuntimeError(
                f"Pilot cell identifiers disagree for {item['structure']}: "
                f"expected {selected_cells}, observed {receipt_cells}"
            )
        shared = manifest["shared"]
        expected_values = {
            "protocol_version": shared["protocol_version"],
            "stage": shared["stage"],
            "status": shared["receipt_status"],
            "structure": item["structure"],
            "config_sha256": shared["config_sha256"],
        }
        for key, expected in expected_values.items():
            if receipt.get(key) != expected:
                raise RuntimeError(
                    f"Pilot receipt field mismatch at {receipt_path}: {key}={receipt.get(key)!r}, "
                    f"expected {expected!r}"
                )
        if receipt.get("implementation", {}).get("sha256") != shared["implementation_sha256"]:
            raise RuntimeError(f"Pilot implementation hash mismatch at {receipt_path}.")
        summary = receipt["summary"]
        for observed, expected, label in (
            (summary["reference_fields"], item["reference_fields"], "reference fields"),
            (summary["pairs"], item["paired_acquisitions"], "paired acquisitions"),
            (summary["rows"], item["endpoint_cases"], "endpoint cases"),
        ):
            if int(observed) != int(expected):
                raise RuntimeError(f"Pilot {label} mismatch for {item['structure']}.")
    return manifest


def verify_candidate_lock() -> dict[str, Any]:
    """Verify the prospective candidate lock before any score comparison."""

    receipt = json.loads(CANDIDATE_LOCK.read_text(encoding="utf-8"))
    failures: list[dict[str, Any]] = []
    for item in receipt["files"]:
        path = PROJECT_ROOT / item["path"]
        observed = sha256_file(path) if path.is_file() else None
        observed_bytes = path.stat().st_size if path.is_file() else None
        if observed != item["sha256"] or observed_bytes != item["bytes"]:
            failures.append(
                {
                    "path": item["path"],
                    "expected_sha256": item["sha256"],
                    "observed_sha256": observed,
                    "expected_bytes": item["bytes"],
                    "observed_bytes": observed_bytes,
                }
            )
    if failures:
        raise RuntimeError(f"Score-design candidate lock failed: {failures}")
    return receipt


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
    return rows


def load_receipted_design_rows(
    paths: Sequence[Path],
    *,
    allow_developmental_pilot: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load completed score-design results and reject any partition leakage."""

    all_rows: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    implementation_hashes: set[str] = set()
    config_hashes: set[str] = set()
    for path in paths:
        receipt_path = path.parent / "archive_receipt.json"
        if not receipt_path.is_file():
            raise FileNotFoundError(f"Missing completion receipt beside {path}: {receipt_path}")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        permitted_statuses = {"complete_score_design"}
        if allow_developmental_pilot:
            permitted_statuses.add("smoke_test")
        if receipt.get("status") not in permitted_statuses or receipt.get("stage") != "score_design":
            raise RuntimeError(f"Refusing non-design receipt: {receipt_path}")
        expected_hash = receipt.get("artifacts", {}).get("endpoint_cases_sha256")
        observed_hash = sha256_file(path)
        if expected_hash != observed_hash:
            raise RuntimeError(
                f"Endpoint artifact hash mismatch for {path}: expected {expected_hash}, observed {observed_hash}"
            )
        rows = _read_jsonl(path)
        leaking = sorted({str(row.get("development_partition")) for row in rows} - {"score_design"})
        if leaking:
            raise RuntimeError(f"Forbidden non-score-design rows in {path}: {leaking}")
        all_rows.extend(rows)
        receipts.append(
            {
                "path": str(receipt_path),
                "structure": receipt["structure"],
                "endpoint_cases_sha256": observed_hash,
                "config_sha256": receipt["config_sha256"],
                "implementation_sha256": receipt["implementation"]["sha256"],
            }
        )
        implementation_hashes.add(receipt["implementation"]["sha256"])
        config_hashes.add(receipt["config_sha256"])
    if len(implementation_hashes) != 1:
        raise RuntimeError(f"Mixed implementation hashes: {sorted(implementation_hashes)}")
    if len(config_hashes) != 1:
        raise RuntimeError(f"Mixed config hashes: {sorted(config_hashes)}")
    identifiers = [str(row["case_id"]) for row in all_rows]
    if len(identifiers) != len(set(identifiers)):
        duplicates = sorted(identifier for identifier in set(identifiers) if identifiers.count(identifier) > 1)
        raise RuntimeError(f"Duplicate endpoint case identifiers: {duplicates[:10]}")
    return all_rows, receipts


def add_locked_candidate_scores(rows: list[dict[str, Any]], candidate_config: Mapping[str, Any]) -> None:
    """Add only the three prospectively locked candidate scores in place."""

    minimum_coherence = float(candidate_config["orientation_observability"]["minimum_interpretable_coherence"])
    coherence_by_pair_scale: dict[tuple[str, float], float] = {}
    for row in rows:
        if row["endpoint"] == "tensor_coherence":
            key = (str(row["pair_id"]), float(row["requested_scale_um"]))
            if key in coherence_by_pair_scale:
                raise RuntimeError(f"Duplicate tensor-coherence match for {key}")
            coherence_by_pair_scale[key] = float(row["input_measurement"])

    epsilon = np.finfo(float).eps
    for row in rows:
        components = row["support_components"]
        original = float(row["scores"]["full_contract"])
        orientation_risk = 0.0
        if row["endpoint"] == "tensor_orientation":
            key = (str(row["pair_id"]), float(row["requested_scale_um"]))
            if key not in coherence_by_pair_scale:
                raise RuntimeError(f"Missing matched tensor coherence for {key}")
            orientation_risk = minimum_coherence / max(coherence_by_pair_scale[key], epsilon)
        robustness = max(
            float(components["perturbation_stability"]),
            float(components["cross_scale_agreement"]),
            float(orientation_risk),
        )
        row["support_components"]["orientation_observability"] = float(orientation_risk)
        row["scores"]["v2_full_max"] = original
        row["scores"]["v2_full_max_plus_orientation_observability"] = float(
            max(original, orientation_risk)
        )
        row["scores"]["robustness_max_plus_orientation_observability"] = float(robustness)


def stratum_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    requested = row.get("requested_scale_um")
    scale = "global" if requested is None else f"{float(requested):.10g}"
    return str(row["structure"]), str(row["endpoint"]), scale


def _stratify(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str, str], list[Mapping[str, Any]]]:
    strata: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[stratum_key(row)].append(row)
    return dict(strata)


def summarize_candidates(
    rows: Sequence[Mapping[str, Any]],
    candidates: Sequence[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = eligible_rows(rows)
    strata = _stratify(cases)
    stratum_rows: list[dict[str, Any]] = []
    for key in sorted(strata):
        subset = strata[key]
        invalid = sum(bool(row["invalid"]) for row in subset)
        informative = 0 < invalid < len(subset)
        result: dict[str, Any] = {
            "structure": key[0],
            "endpoint": key[1],
            "requested_scale_um": key[2],
            "eligible_cases": len(subset),
            "reference_fields": len({str(row["reference_group_id"]) for row in subset}),
            "invalid_cases": invalid,
            "invalid_fraction": invalid / len(subset),
            "informative": informative,
        }
        for candidate in candidates:
            result[f"aurc__{candidate}"] = aurc(subset, candidate)
        stratum_rows.append(result)

    informative_rows = [row for row in stratum_rows if row["informative"]]
    summary: dict[str, Any] = {
        "endpoint_cases": len(rows),
        "eligible_endpoint_cases": len(cases),
        "reference_fields": len({str(row["reference_group_id"]) for row in cases}),
        "pairs": len({str(row["pair_id"]) for row in cases}),
        "strata": len(stratum_rows),
        "informative_strata": len(informative_rows),
        "constant_valid_strata": sum(row["invalid_cases"] == 0 for row in stratum_rows),
        "constant_invalid_strata": sum(row["invalid_cases"] == row["eligible_cases"] for row in stratum_rows),
        "candidates": {},
    }
    for candidate in candidates:
        per_structure: dict[str, float | None] = {}
        for structure in sorted({row["structure"] for row in informative_rows}):
            values = [
                float(row[f"aurc__{candidate}"])
                for row in informative_rows
                if row["structure"] == structure
            ]
            per_structure[structure] = float(np.mean(values)) if values else None
        macro_values = [float(row[f"aurc__{candidate}"]) for row in informative_rows]
        summary["candidates"][candidate] = {
            "micro_aurc": aurc(cases, candidate),
            "macro_informative_strata_aurc": float(np.mean(macro_values)) if macro_values else None,
            "structure_macro_informative_strata_aurc": per_structure,
        }
    return summary, stratum_rows


def _bootstrap_field_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    draws: int,
    seed: int,
) -> tuple[dict[str, list[str]], dict[str, np.ndarray]]:
    identifiers: dict[str, list[str]] = {}
    counts: dict[str, np.ndarray] = {}
    rng = np.random.default_rng(seed)
    for structure in sorted({str(row["structure"]) for row in rows}):
        fields = sorted(
            {
                str(row["reference_group_id"])
                for row in rows
                if str(row["structure"]) == structure
            }
        )
        if not fields:
            continue
        identifiers[structure] = fields
        probabilities = np.full(len(fields), 1.0 / len(fields), dtype=float)
        counts[structure] = rng.multinomial(len(fields), probabilities, size=draws)
    return identifiers, counts


def _weighted_aurc_draws(
    rows: Sequence[Mapping[str, Any]],
    condition: str,
    *,
    field_identifiers: Sequence[str],
    field_counts: np.ndarray,
) -> np.ndarray:
    """Vectorized cluster-bootstrap AURC with tied scores accepted together."""

    field_index = {identifier: index for index, identifier in enumerate(field_identifiers)}
    ordered = sorted(rows, key=lambda row: (float(row["scores"][condition]), str(row["case_id"])))
    group_indices = np.asarray([field_index[str(row["reference_group_id"])] for row in ordered], dtype=int)
    invalid = np.asarray([bool(row["invalid"]) for row in ordered], dtype=bool)
    scores = np.asarray([float(row["scores"][condition]) for row in ordered], dtype=float)
    total = np.sum(field_counts[:, group_indices], axis=1, dtype=float)
    area = np.zeros(field_counts.shape[0], dtype=float)
    cumulative_accepted = np.zeros_like(area)
    cumulative_invalid = np.zeros_like(area)
    previous_coverage = np.zeros_like(area)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and scores[end] == scores[index]:
            end += 1
        block_indices = group_indices[index:end]
        block_weights = np.sum(field_counts[:, block_indices], axis=1, dtype=float)
        invalid_indices = group_indices[index:end][invalid[index:end]]
        invalid_weights = (
            np.sum(field_counts[:, invalid_indices], axis=1, dtype=float)
            if len(invalid_indices)
            else np.zeros_like(area)
        )
        cumulative_accepted += block_weights
        cumulative_invalid += invalid_weights
        coverage = np.divide(
            cumulative_accepted,
            total,
            out=np.full_like(area, np.nan),
            where=total > 0,
        )
        risk = np.divide(
            cumulative_invalid,
            cumulative_accepted,
            out=np.zeros_like(area),
            where=cumulative_accepted > 0,
        )
        area += np.where(np.isfinite(coverage), (coverage - previous_coverage) * risk, 0.0)
        previous_coverage = np.where(np.isfinite(coverage), coverage, previous_coverage)
        index = end
    area[total == 0] = np.nan
    return area


def _nanmean_columns(values: Sequence[np.ndarray]) -> np.ndarray:
    """Column mean that preserves all-missing draws without runtime warnings."""

    matrix = np.vstack(values)
    finite = np.isfinite(matrix)
    counts = np.sum(finite, axis=0)
    totals = np.sum(np.where(finite, matrix, 0.0), axis=0)
    return np.divide(
        totals,
        counts,
        out=np.full(matrix.shape[1], np.nan, dtype=float),
        where=counts > 0,
    )


def clustered_bootstrap_candidate_differences(
    rows: Sequence[Mapping[str, Any]],
    candidates: Sequence[str],
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap paired macro-AURC differences at the reference-field unit."""

    cases = eligible_rows(rows)
    strata = _stratify(cases)
    informative = {
        key: subset
        for key, subset in strata.items()
        if 0 < sum(bool(row["invalid"]) for row in subset) < len(subset)
    }
    identifiers, sampled_counts = _bootstrap_field_counts(cases, draws=draws, seed=seed)
    macro_draws: dict[str, np.ndarray] = {}
    structure_macro_draws: dict[str, dict[str, np.ndarray]] = {}
    for candidate in candidates:
        by_structure: dict[str, list[np.ndarray]] = defaultdict(list)
        all_strata: list[np.ndarray] = []
        for key in sorted(informative):
            structure = key[0]
            values = _weighted_aurc_draws(
                informative[key],
                candidate,
                field_identifiers=identifiers[structure],
                field_counts=sampled_counts[structure],
            )
            by_structure[structure].append(values)
            all_strata.append(values)
        macro_draws[candidate] = _nanmean_columns(all_strata)
        structure_macro_draws[candidate] = {
            structure: _nanmean_columns(values)
            for structure, values in by_structure.items()
        }

    baseline = "v2_full_max"
    comparisons: dict[str, Any] = {}
    for candidate in candidates:
        difference = macro_draws[baseline] - macro_draws[candidate]
        finite = difference[np.isfinite(difference)]
        structure_results: dict[str, Any] = {}
        for structure in sorted(structure_macro_draws[baseline]):
            values = (
                structure_macro_draws[baseline][structure]
                - structure_macro_draws[candidate][structure]
            )
            values = values[np.isfinite(values)]
            structure_results[structure] = {
                "median_baseline_minus_candidate": float(np.median(values)),
                "ci95": [float(value) for value in np.quantile(values, [0.025, 0.975])],
            }
        comparisons[candidate] = {
            "finite_draws": int(len(finite)),
            "median_baseline_minus_candidate": float(np.median(finite)),
            "ci95": [float(value) for value in np.quantile(finite, [0.025, 0.975])],
            "probability_candidate_better_than_baseline": float(np.mean(finite > 0)),
            "structure_specific": structure_results,
        }
    return {
        "draws": draws,
        "seed": seed,
        "resampling_unit": "reference_group_id stratified by structure",
        "difference_direction": "positive values favor the candidate over v2_full_max",
        "comparisons": comparisons,
    }


def select_candidate(summary: Mapping[str, Any], candidate_config: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the locked non-inferiority, lowest-AURC, and simplicity rules."""

    baseline_name = "v2_full_max"
    tolerance = 0.01
    metrics = summary["candidates"]
    baseline = metrics[baseline_name]
    survivors: list[str] = []
    exclusions: dict[str, list[str]] = {}
    for name, result in metrics.items():
        reasons: list[str] = []
        for structure, baseline_value in baseline["structure_macro_informative_strata_aurc"].items():
            value = result["structure_macro_informative_strata_aurc"].get(structure)
            if baseline_value is not None and value is not None and value > baseline_value + tolerance:
                reasons.append(
                    f"{structure} macro AURC {value:.6g} exceeds baseline {baseline_value:.6g} by > {tolerance}"
                )
        if reasons:
            exclusions[name] = reasons
        else:
            survivors.append(name)
    if not survivors:
        raise RuntimeError("Locked selection rule excluded every candidate, including the baseline.")
    component_counts = {
        name: len(specification["components"])
        for name, specification in candidate_config["candidate_formulas"].items()
    }
    best_value = min(float(metrics[name]["macro_informative_strata_aurc"]) for name in survivors)
    tied = [
        name
        for name in survivors
        if float(metrics[name]["macro_informative_strata_aurc"]) <= best_value + tolerance
    ]
    selected = min(tied, key=lambda name: (component_counts[name], name))
    return {
        "status": "selected",
        "selected_candidate": selected,
        "best_observed_macro_aurc": best_value,
        "tie_tolerance": tolerance,
        "tie_set": sorted(tied),
        "survivors": sorted(survivors),
        "exclusions": exclusions,
        "component_counts": component_counts,
    }


def _write_csv(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=26_082_801)
    parser.add_argument(
        "--development-pilot-manifest",
        type=Path,
        help=(
            "Permit only the exactly receipted smoke-test inputs in this developmental-pilot manifest. "
            "Results remain non-confirmatory."
        ),
    )
    args = parser.parse_args()

    lock = verify_candidate_lock()
    candidate_config = json.loads(CANDIDATE_CONFIG.read_text(encoding="utf-8"))
    pilot_manifest = None
    if args.development_pilot_manifest is not None:
        pilot_manifest = verify_developmental_pilot_manifest(args.development_pilot_manifest, args.rows)
    rows, input_receipts = load_receipted_design_rows(
        args.rows,
        allow_developmental_pilot=pilot_manifest is not None,
    )
    add_locked_candidate_scores(rows, candidate_config)
    candidates = list(candidate_config["candidate_formulas"])
    summary, stratum_rows = summarize_candidates(rows, candidates)
    summary["clustered_bootstrap"] = clustered_bootstrap_candidate_differences(
        rows,
        candidates,
        draws=args.bootstrap_draws,
        seed=args.bootstrap_seed,
    )
    selection = select_candidate(summary, candidate_config)
    if pilot_manifest is not None:
        selection["status"] = "provisional_developmental_selection"
        selection["claim_boundary"] = (
            "This small pilot can expose failures and provisionally compare locked candidates; "
            "it cannot establish final thresholds, generalization, or clinical validity."
        )

    args.output.mkdir(parents=True, exist_ok=True)
    augmented_path = args.output / "score_design_endpoint_cases.jsonl"
    strata_path = args.output / "score_design_strata.csv"
    write_rows_jsonl(sorted(rows, key=lambda row: str(row["case_id"])), augmented_path)
    _write_csv(stratum_rows, strata_path)
    audit = {
        "schema_version": "nostos-biosr-score-design-audit/1.0",
        "partition": "score_design",
        "analysis_scope": "developmental_small_pilot" if pilot_manifest is not None else "complete_score_design",
        "developmental_pilot_manifest": (
            {
                "path": str(args.development_pilot_manifest),
                "sha256": sha256_file(args.development_pilot_manifest),
                "status": pilot_manifest["status"],
            }
            if pilot_manifest is not None
            else None
        ),
        "candidate_lock_sha256": sha256_file(CANDIDATE_LOCK),
        "candidate_lock_time_utc": lock["locked_at_utc"],
        "candidate_config_sha256": sha256_file(CANDIDATE_CONFIG),
        "input_receipts": input_receipts,
        "summary": summary,
        "selection": selection,
        "artifacts": {
            "score_design_endpoint_cases_sha256": sha256_file(augmented_path),
            "score_design_strata_sha256": sha256_file(strata_path),
        },
    }
    audit_path = args.output / "score_design_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "selection": selection}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
