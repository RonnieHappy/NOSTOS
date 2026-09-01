"""Prospective freeze and confirmation for the Heaton in-vivo SHG benchmark."""

from __future__ import annotations

import hashlib
import json
import warnings
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from scipy.stats import spearmanr

from nostos.validation.curvealign_outputs import parse_field_outputs
from nostos.validation.family_risk_calibration import (
    IsotonicRiskMap,
    calibrated_operating_summary,
    cross_fitted_family_risk,
    risk_coverage_auc,
)
from nostos.validation.heaton_shg_transfer import (
    ENDPOINTS,
    apply_condition,
    measure_shg_field,
    select_perturbation_fields,
)


PAIRING = {
    "axial_resultant": "coefficient_of_alignment",
    "foreground_occupancy": "detected_pixel_fraction",
    "median_segment_straightness": "median_straightness",
    "median_segment_length_um": "median_length_um",
    "median_local_width_um": "median_width_um",
}
POLICIES = (
    "acquisition_qc",
    "endpoint_qc",
    "without_scale_consistency",
    "without_threshold_consistency",
    "without_nested_consistency",
    "full_contract",
)


def sha256_file(path: Path, chunk_bytes: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_image(path: Path) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*UIC.*", category=UserWarning)
        image = tifffile.imread(path)
    image = np.squeeze(np.asarray(image))
    if image.ndim != 2 or not np.isfinite(image).all():
        raise ValueError(f"Expected one finite 2-D SHG field: {path}")
    return image


def _output_roots(stage: Path) -> tuple[Path, Path]:
    curvealign = sorted({path.parent for path in stage.rglob("*_stats.csv")})
    ctfire = sorted({path.parent for path in stage.rglob("HistLEN_ctFIRE_*.csv")})
    if len(curvealign) != 1 or len(ctfire) != 1:
        raise ValueError(
            "Expected exactly one CurveAlign and one CT-FIRE output directory; "
            f"observed {curvealign} and {ctfire}."
        )
    return curvealign[0], ctfire[0]


def _comparators(stage: Path, receipt: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    curvealign_root, ctfire_root = _output_roots(stage)
    spacing = float(config["dataset"]["pixel_spacing_um"][0])
    return {
        str(row["field_stem"]): parse_field_outputs(
            stage,
            field_stem=str(row["field_stem"]),
            pixel_spacing_um=spacing,
            curvealign_root=curvealign_root,
            ctfire_root=ctfire_root,
        )
        for row in receipt["rows"]
    }


def _relative_floor(comparators: Mapping[str, Mapping[str, Any]], endpoint: str) -> float:
    comparator_key = PAIRING[endpoint]
    values = np.asarray([float(row[comparator_key]) for row in comparators.values()], dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError(f"Cannot calculate the denominator floor for {endpoint}.")
    return float(max(np.percentile(np.abs(values), 5.0), np.finfo(float).eps))


def invalid_endpoint(
    endpoint: str,
    observed: float | None,
    reference: float,
    *,
    denominator_floor: float,
    tolerances: Mapping[str, Any],
) -> tuple[bool, float | None]:
    """Apply the prospectively declared endpoint-specific invalidity rule."""

    if observed is None or not np.isfinite(observed) or not np.isfinite(reference):
        return True, None
    difference = abs(float(observed) - float(reference))
    if endpoint == "axial_resultant":
        metric = difference
        threshold = float(tolerances["axial_resultant_absolute"])
    elif endpoint == "median_segment_straightness":
        metric = difference
        threshold = float(tolerances["median_segment_straightness_absolute"])
    else:
        metric = difference / max(abs(float(reference)), float(denominator_floor))
        threshold_key = {
            "foreground_occupancy": "foreground_occupancy_relative",
            "median_segment_length_um": "median_segment_length_relative",
            "median_local_width_um": "median_local_width_relative",
        }[endpoint]
        threshold = float(tolerances[threshold_key])
    return bool(metric > threshold), float(metric)


def _clean_job(payload: tuple[str, dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    path_text, params, config = payload
    measured = measure_shg_field(
        _read_image(Path(path_text)),
        spacing_um=tuple(float(value) for value in config["dataset"]["pixel_spacing_um"]),
        params=params,
        config=config,
        internal_checks=False,
    )
    return measured


def _perturb_job(
    payload: tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any]]
) -> dict[str, Any]:
    path_text, field_stem, condition, params, config = payload
    shifted = apply_condition(
        _read_image(Path(path_text)),
        condition,
        field_id=field_stem,
        seed=int(config["risk_calibration"]["seed"]),
    )
    return measure_shg_field(
        shifted,
        spacing_um=tuple(float(value) for value in config["dataset"]["pixel_spacing_um"]),
        params=params,
        config=config,
        internal_checks=True,
    )


def _clean_rows(
    stage: Path,
    receipt: Mapping[str, Any],
    comparators: Mapping[str, Mapping[str, Any]],
    params: Mapping[str, Any],
    config: Mapping[str, Any],
    workers: int,
) -> list[dict[str, Any]]:
    source_rows = list(receipt["rows"])
    jobs = [(str(stage / row["staged_name"]), dict(params), dict(config)) for row in source_rows]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        measured = list(executor.map(_clean_job, jobs, chunksize=2))
    output = []
    for source, result in zip(source_rows, measured, strict=True):
        output.append(
            {
                "mouse": str(source["mouse"]),
                "field_stem": str(source["field_stem"]),
                "source_sha256": str(source["sha256"]),
                "nostos": result["endpoints"],
                "complete": bool(result["complete"]),
                "segment_count": int(result["segment_count"]),
                "comparator": dict(comparators[str(source["field_stem"])]),
            }
        )
    return output


def _case_rows(
    stage: Path,
    receipt: Mapping[str, Any],
    comparators: Mapping[str, Mapping[str, Any]],
    params: Mapping[str, Any],
    floors: Mapping[str, float],
    config: Mapping[str, Any],
    workers: int,
    *,
    structure: str,
) -> list[dict[str, Any]]:
    selected = select_perturbation_fields(receipt["rows"])
    jobs = []
    metadata = []
    for source in selected:
        for condition in config["conditions"]:
            jobs.append(
                (
                    str(stage / source["staged_name"]),
                    str(source["field_stem"]),
                    dict(condition),
                    dict(params),
                    dict(config),
                )
            )
            metadata.append((source, condition))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        measurements = list(executor.map(_perturb_job, jobs, chunksize=1))
    rows: list[dict[str, Any]] = []
    tolerances = config["invalidity_tolerances"]
    for (source, condition), measured in zip(metadata, measurements, strict=True):
        comparator = comparators[str(source["field_stem"])]
        for endpoint in ENDPOINTS:
            reference = float(comparator[PAIRING[endpoint]])
            invalid, error = invalid_endpoint(
                endpoint,
                measured["endpoints"].get(endpoint),
                reference,
                denominator_floor=float(floors[endpoint]),
                tolerances=tolerances,
            )
            rows.append(
                {
                    "case_id": f"{source['field_stem']}|{condition['id']}|{endpoint}",
                    "structure": structure,
                    "reference_group_id": str(source["mouse"]),
                    "mouse": str(source["mouse"]),
                    "field_stem": str(source["field_stem"]),
                    "condition": str(condition["id"]),
                    "endpoint": endpoint,
                    "pair_registration_eligible": True,
                    "reference_eligible": True,
                    "hard_abstention": bool(measured["hard_abstention"]),
                    "observed": measured["endpoints"].get(endpoint),
                    "reference": reference,
                    "error_metric": error,
                    "invalid": bool(invalid),
                    "scores": dict(measured["scores"]),
                    "risk_components": dict(measured["risk_components"]),
                }
            )
    rows.sort(key=lambda row: str(row["case_id"]))
    return rows


def _family_map() -> dict[str, list[str]]:
    return {endpoint: [endpoint] for endpoint in ENDPOINTS}


def _development_maps(
    rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    calibration = config["risk_calibration"]
    summaries: dict[str, Any] = {}
    maps: dict[str, Any] = {}
    for policy in POLICIES:
        augmented, fitted = cross_fitted_family_risk(
            rows,
            family_map=_family_map(),
            raw_score=policy,
            bins=int(calibration["bins"]),
            folds=int(calibration["folds"]),
            seed=int(calibration["seed"]),
        )
        summary = calibrated_operating_summary(
            augmented,
            maximum_predicted_risk=float(calibration["maximum_predicted_risk"]),
        )
        summary["risk_coverage_auc"] = risk_coverage_auc(augmented, score_key="calibrated_risk")
        summaries[policy] = summary
        maps[policy] = {endpoint: fitted[endpoint].to_dict() for endpoint in ENDPOINTS}
    return summaries, maps


def _correlations(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | None]:
    output: dict[str, float | None] = {}
    for endpoint, comparator in PAIRING.items():
        pairs = [
            (float(row["nostos"][endpoint]), float(row["comparator"][comparator]))
            for row in rows
            if row["nostos"].get(endpoint) is not None
            and np.isfinite(row["nostos"][endpoint])
            and np.isfinite(row["comparator"][comparator])
        ]
        if len(pairs) < 4:
            output[endpoint] = None
        else:
            rho = float(spearmanr(*zip(*pairs, strict=True)).statistic)
            output[endpoint] = rho if np.isfinite(rho) else None
    return output


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def freeze_confirmation_profile(
    stage: Path,
    config_path: Path,
    protocol_path: Path,
    development_path: Path,
    official_receipt_path: Path,
    output_dir: Path,
    lock_path: Path,
    workers: int,
) -> dict[str, Any]:
    """Compile Exp10-only evidence and authorize one untouched Exp15 run."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    development = json.loads(development_path.read_text(encoding="utf-8"))
    receipt_path = stage / "stage_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    official = json.loads(official_receipt_path.read_text(encoding="utf-8"))
    if receipt.get("experiment") != "Exp10" or receipt.get("status") != "development_stage_parameters_locked":
        raise PermissionError("The confirmation profile can only be frozen from locked Exp10.")
    if development.get("status") != "development_complete_confirmation_still_sealed":
        raise PermissionError("The adapter-development receipt does not preserve the Exp15 seal.")
    if official.get("status") != "complete" or int(official.get("input_images", -1)) != 34:
        raise ValueError("The official Exp10 comparator receipt is incomplete.")
    if development["config_sha256"] != sha256_file(config_path) or development["protocol_sha256"] != sha256_file(protocol_path):
        raise ValueError("The adapter-development receipt does not match the frozen inputs.")
    if development["stage_receipt_sha256"] != sha256_file(receipt_path):
        raise ValueError("The Exp10 stage changed after adapter development.")
    params = dict(development["winner"]["parameters"])
    comparators = _comparators(stage, receipt, config)
    floors = {endpoint: _relative_floor(comparators, endpoint) for endpoint in ENDPOINTS}
    clean_rows = _clean_rows(stage, receipt, comparators, params, config, workers)
    case_rows = _case_rows(
        stage,
        receipt,
        comparators,
        params,
        floors,
        config,
        workers,
        structure="heaton_exp10",
    )
    policy_summaries, risk_maps = _development_maps(case_rows, config)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_path = output_dir / "development_clean_rows.jsonl"
    case_path = output_dir / "development_perturbation_rows.jsonl"
    _write_jsonl(clean_path, clean_rows)
    _write_jsonl(case_path, case_rows)
    development_summary = {
        "schema_version": "nostos.heaton_shg_risk_development.v1",
        "status": "development_complete_confirmation_still_sealed",
        "clean_fields": len(clean_rows),
        "perturbation_cases": len(case_rows),
        "mice": len({row["mouse"] for row in case_rows}),
        "clean_correlations": _correlations(clean_rows),
        "policy_summaries": policy_summaries,
        "denominator_floors": floors,
        "selected_adapter": params,
        "claim_boundary": "Exp10 development only; no Exp15 pixels or outcomes used.",
    }
    summary_path = output_dir / "development_summary.json"
    summary_path.write_text(json.dumps(development_summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lock = {
        "schema_version": "nostos.heaton_shg_confirmation_lock.v1",
        "status": "locked_confirmation_authorized",
        "protocol_path": protocol_path.as_posix(),
        "protocol_sha256": sha256_file(protocol_path),
        "config_path": config_path.as_posix(),
        "config_sha256": sha256_file(config_path),
        "adapter_development_path": development_path.as_posix(),
        "adapter_development_sha256": sha256_file(development_path),
        "exp10_stage_receipt_sha256": sha256_file(receipt_path),
        "exp10_official_receipt_sha256": sha256_file(official_receipt_path),
        "development_summary_path": summary_path.as_posix(),
        "development_summary_sha256": sha256_file(summary_path),
        "development_clean_rows_sha256": sha256_file(clean_path),
        "development_perturbation_rows_sha256": sha256_file(case_path),
        "selected_adapter": params,
        "denominator_floors": floors,
        "risk_maps": risk_maps,
        "maximum_predicted_risk": float(config["risk_calibration"]["maximum_predicted_risk"]),
        "success_gates": dict(config["success_gates"]),
        "confirmation": {"experiment": "Exp15", "fields": 45, "mice": 8, "pixels_opened_at_lock": False},
        "claim_boundary": str(config["claim_boundary"]),
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    verify_lock(lock_path, config_path, protocol_path, development_path, summary_path, clean_path, case_path)
    return lock


def verify_lock(
    lock_path: Path,
    config_path: Path,
    protocol_path: Path,
    development_path: Path,
    summary_path: Path,
    clean_path: Path,
    case_path: Path,
) -> None:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    expected = {
        "config_sha256": sha256_file(config_path),
        "protocol_sha256": sha256_file(protocol_path),
        "adapter_development_sha256": sha256_file(development_path),
        "development_summary_sha256": sha256_file(summary_path),
        "development_clean_rows_sha256": sha256_file(clean_path),
        "development_perturbation_rows_sha256": sha256_file(case_path),
    }
    if lock.get("status") != "locked_confirmation_authorized":
        raise PermissionError("The Heaton confirmation lock is not authorized.")
    mismatches = {key: (lock.get(key), value) for key, value in expected.items() if lock.get(key) != value}
    if mismatches:
        raise ValueError(f"Immediate confirmation-lock verification failed: {mismatches}")


def _risk_map(payload: Mapping[str, Any]) -> IsotonicRiskMap:
    return IsotonicRiskMap(
        x_thresholds=tuple(float(value) for value in payload["x_thresholds"]),
        y_thresholds=tuple(float(value) for value in payload["y_thresholds"]),
        training_cases=int(payload["training_cases"]),
        training_invalid=int(payload["training_invalid"]),
        bins=int(payload["bins"]),
        prior_alpha=float(payload["prior_alpha"]),
        prior_beta=float(payload["prior_beta"]),
    )


def _annotate(rows: Sequence[Mapping[str, Any]], lock: Mapping[str, Any], policy: str) -> list[dict[str, Any]]:
    by_endpoint = {endpoint: _risk_map(lock["risk_maps"][policy][endpoint]) for endpoint in ENDPOINTS}
    output = []
    for row in rows:
        clone = dict(row)
        if bool(row["hard_abstention"]):
            clone["calibrated_risk"] = 1.0
        else:
            clone["calibrated_risk"] = float(
                by_endpoint[str(row["endpoint"])].predict([float(row["scores"][policy])])[0]
            )
        output.append(clone)
    return output


def _accepted(rows: Sequence[Mapping[str, Any]], threshold: float) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if not bool(row["hard_abstention"]) and float(row["calibrated_risk"]) <= threshold
    ]


def _operating(rows: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    selected = _accepted(rows, threshold)
    invalid = int(sum(bool(row["invalid"]) for row in selected))
    return {
        "eligible": len(rows),
        "accepted": len(selected),
        "coverage": float(len(selected) / len(rows)),
        "invalid": invalid,
        "risk": float(invalid / len(selected)) if selected else None,
    }


def _lowest(rows: Sequence[Mapping[str, Any]], count: int) -> list[Mapping[str, Any]]:
    return sorted(rows, key=lambda row: (float(row["calibrated_risk"]), str(row["case_id"])))[:count]


def _risk(rows: Sequence[Mapping[str, Any]]) -> float:
    return float(np.mean([bool(row["invalid"]) for row in rows])) if rows else 1.0


def _cluster_bootstrap_correlations(
    clean_rows: Sequence[Mapping[str, Any]], *, draws: int, seed: int
) -> dict[str, list[float] | None]:
    mice = sorted({str(row["mouse"]) for row in clean_rows})
    by_mouse = {mouse: [row for row in clean_rows if str(row["mouse"]) == mouse] for mouse in mice}
    rng = np.random.default_rng(seed)
    values = {endpoint: [] for endpoint in ENDPOINTS}
    for _ in range(draws):
        sampled = []
        for replicate, index in enumerate(rng.integers(0, len(mice), len(mice))):
            for row in by_mouse[mice[int(index)]]:
                clone = dict(row)
                clone["field_stem"] = f"bootstrap-{replicate}|{row['field_stem']}"
                sampled.append(clone)
        correlations = _correlations(sampled)
        for endpoint, value in correlations.items():
            if value is not None and np.isfinite(value):
                values[endpoint].append(float(value))
    return {
        endpoint: (
            [float(value) for value in np.quantile(np.asarray(samples), (0.025, 0.975))]
            if samples
            else None
        )
        for endpoint, samples in values.items()
    }


def _resample(rows: Sequence[Mapping[str, Any]], mice: Sequence[str], indices: np.ndarray) -> list[dict[str, Any]]:
    by_mouse = {mouse: [row for row in rows if str(row["mouse"]) == mouse] for mouse in mice}
    output = []
    for replicate, index in enumerate(indices):
        for row in by_mouse[mice[int(index)]]:
            clone = dict(row)
            clone["case_id"] = f"bootstrap-{replicate}|{row['case_id']}"
            output.append(clone)
    return output


def _safety_bootstrap(
    policy_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    threshold: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    mice = sorted({str(row["mouse"]) for row in policy_rows["full_contract"]})
    rng = np.random.default_rng(seed)
    full_risks = []
    matched_reductions = []
    for _ in range(draws):
        indices = rng.integers(0, len(mice), len(mice))
        sampled = {name: _resample(rows, mice, indices) for name, rows in policy_rows.items()}
        full = _accepted(sampled["full_contract"], threshold)
        if not full:
            continue
        full_risk = _risk(full)
        full_risks.append(full_risk)
        acquisition = _lowest(sampled["acquisition_qc"], len(full))
        matched_reductions.append(_risk(acquisition) - full_risk)
    interval = lambda values: [float(value) for value in np.quantile(np.asarray(values), (0.025, 0.975))]
    return {
        "draws_requested": int(draws),
        "draws_retained": len(full_risks),
        "full_risk_95": interval(full_risks) if full_risks else [0.0, 1.0],
        "matched_risk_reduction_vs_acquisition_qc_95": (
            interval(matched_reductions) if matched_reductions else [-1.0, 1.0]
        ),
    }


def run_confirmation(
    stage: Path,
    config_path: Path,
    protocol_path: Path,
    lock_path: Path,
    official_receipt_path: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    """Run the untouched Exp15 analysis once with no scientific refitting."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    receipt_path = stage / "stage_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    official = json.loads(official_receipt_path.read_text(encoding="utf-8"))
    if lock.get("status") != "locked_confirmation_authorized":
        raise PermissionError("Confirmation is not authorized by the supplied lock.")
    if lock["config_sha256"] != sha256_file(config_path) or lock["protocol_sha256"] != sha256_file(protocol_path):
        raise ValueError("The confirmation lock does not match the current config/protocol.")
    if receipt.get("experiment") != "Exp15" or receipt.get("status") != "confirmation_stage_parameters_locked":
        raise PermissionError("Confirmation requires the locked Exp15 stage.")
    if official.get("status") != "complete" or int(official.get("input_images", -1)) != 45:
        raise ValueError("The official Exp15 comparator receipt is incomplete.")
    params = dict(lock["selected_adapter"])
    floors = {key: float(value) for key, value in lock["denominator_floors"].items()}
    comparators = _comparators(stage, receipt, config)
    clean_rows = _clean_rows(stage, receipt, comparators, params, config, workers)
    case_rows = _case_rows(
        stage,
        receipt,
        comparators,
        params,
        floors,
        config,
        workers,
        structure="heaton_exp15",
    )
    correlations = _correlations(clean_rows)
    correlation_ci = _cluster_bootstrap_correlations(
        clean_rows,
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]),
    )
    policy_rows = {policy: _annotate(case_rows, lock, policy) for policy in POLICIES}
    threshold = float(lock["maximum_predicted_risk"])
    operating = {policy: _operating(rows, threshold) for policy, rows in policy_rows.items()}
    aurc = {policy: risk_coverage_auc(rows, score_key="calibrated_risk") for policy, rows in policy_rows.items()}
    full_selected = _accepted(policy_rows["full_contract"], threshold)
    matched_acquisition = _lowest(policy_rows["acquisition_qc"], len(full_selected))
    full_risk = _risk(full_selected)
    matched_reduction = _risk(matched_acquisition) - full_risk
    bootstrap = _safety_bootstrap(
        policy_rows,
        threshold=threshold,
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]) + 1,
    )
    clean_cases = [row for row in policy_rows["full_contract"] if row["condition"] == "clean"]
    clean_by_field: dict[str, list[Mapping[str, Any]]] = {}
    for row in clean_cases:
        clean_by_field.setdefault(str(row["field_stem"]), []).append(row)
    clean_retained = sum(
        len(rows) == len(ENDPOINTS) and all(row in full_selected for row in rows)
        for rows in clean_by_field.values()
    )
    clean_multiendpoint_retention = float(clean_retained / len(clean_by_field))
    successful = [
        endpoint
        for endpoint in ENDPOINTS
        if correlations[endpoint] is not None
        and float(correlations[endpoint]) >= float(config["success_gates"]["minimum_clean_spearman_rho"])
    ]
    lower_bound_success = all(
        correlation_ci[endpoint] is not None
        and float(correlation_ci[endpoint][0])
        >= float(config["success_gates"]["minimum_cluster_bootstrap_lower95_rho"])
        for endpoint in successful
    )
    direction_concordant = all(correlations[endpoint] is not None and float(correlations[endpoint]) > 0 for endpoint in ENDPOINTS)
    ablation_increases = {
        policy: float(aurc[policy] - aurc["full_contract"])
        for policy in (
            "without_scale_consistency",
            "without_threshold_consistency",
            "without_nested_consistency",
        )
    }
    gates_config = config["success_gates"]
    gates = {
        "successful_endpoint_pairs": len(successful) >= int(gates_config["minimum_successful_endpoint_pairs"]),
        "successful_endpoint_cluster_lower95": bool(successful) and lower_bound_success,
        "direction_concordant_all_endpoints": direction_concordant,
        "full_coverage": float(operating["full_contract"]["coverage"]) >= float(gates_config["minimum_full_coverage"]),
        "full_risk_upper95": float(bootstrap["full_risk_95"][1]) <= float(gates_config["maximum_full_risk_upper95"]),
        "matched_risk_reduction": matched_reduction >= float(gates_config["minimum_matched_risk_reduction"]),
        "matched_risk_reduction_ci_excludes_zero": float(bootstrap["matched_risk_reduction_vs_acquisition_qc_95"][0]) > 0,
        "clean_multiendpoint_retention": clean_multiendpoint_retention >= float(gates_config["minimum_clean_multiendpoint_retention"]),
        "component_ablation": max(ablation_increases.values()) >= float(gates_config["minimum_ablation_aurc_increase"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_path = output_dir / "confirmation_clean_rows.jsonl"
    cases_path = output_dir / "confirmation_perturbation_rows.jsonl"
    _write_jsonl(clean_path, clean_rows)
    _write_jsonl(cases_path, case_rows)
    result = {
        "schema_version": "nostos.heaton_shg_confirmation.v1",
        "status": "pass" if all(gates.values()) else "fail",
        "lock_sha256": sha256_file(lock_path),
        "exp15_stage_receipt_sha256": sha256_file(receipt_path),
        "exp15_official_receipt_sha256": sha256_file(official_receipt_path),
        "summary": {
            "clean_fields": len(clean_rows),
            "perturbation_endpoint_cases": len(case_rows),
            "mice": len({row["mouse"] for row in case_rows}),
            "clean_correlations": correlations,
            "clean_correlation_mouse_bootstrap95": correlation_ci,
            "successful_endpoints": successful,
            "operating": operating,
            "matched_acquisition_qc": {
                "accepted": len(matched_acquisition),
                "risk": _risk(matched_acquisition),
                "full_contract_risk": full_risk,
                "risk_reduction": matched_reduction,
            },
            "risk_coverage_auc": aurc,
            "ablation_aurc_increases": ablation_increases,
            "clean_multiendpoint_retention": clean_multiendpoint_retention,
        },
        "bootstrap": bootstrap,
        "success_gates": gates,
        "claim_boundary": str(config["claim_boundary"]),
    }
    result_path = output_dir / "confirmation.json"
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt_payload = {
        "status": "confirmation_executed_once",
        "result_sha256": sha256_file(result_path),
        "clean_rows_sha256": sha256_file(clean_path),
        "perturbation_rows_sha256": sha256_file(cases_path),
    }
    (output_dir / "confirmation_execution_receipt.json").write_text(
        json.dumps(receipt_payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result


__all__ = [
    "PAIRING",
    "POLICIES",
    "freeze_confirmation_profile",
    "invalid_endpoint",
    "run_confirmation",
    "sha256_file",
    "verify_lock",
]
