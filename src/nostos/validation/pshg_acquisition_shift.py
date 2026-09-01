"""Frozen PSHG acquisition-shift selective-validity benchmark."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from scipy import ndimage

from nostos.intraop.support_qc import acquisition_qc_on_support
from nostos.validation.family_risk_calibration import (
    IsotonicRiskMap,
    calibrated_operating_summary,
    cross_fitted_family_risk,
    risk_coverage_auc,
)
from nostos.validation.local_orientation import _axial_errors, _tensor_fields


POLICY_NAMES = (
    "acquisition_qc",
    "endpoint_qc",
    "without_scale_consistency",
    "without_split_consistency",
    "full_contract",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def split_rois(
    roi_names: Sequence[str],
    *,
    salt: str,
    development_rois: int,
    confirmation_rois: int,
) -> dict[str, list[str]]:
    """Return the prospectively frozen hash split without opening image pixels."""

    ordered = sorted(
        {str(name) for name in roi_names},
        key=lambda name: hashlib.sha256(f"{salt}|{name}".encode("utf-8")).hexdigest(),
    )
    required = int(development_rois) + int(confirmation_rois)
    if len(ordered) != required:
        raise ValueError(f"Expected exactly {required} ROIs, found {len(ordered)}.")
    return {
        "development": ordered[: int(development_rois)],
        "confirmation": ordered[int(development_rois) :],
    }


def _frame_paths(roi_root: Path) -> list[Path]:
    frames = sorted(
        roi_root.glob("*_FSHG_p*.tif"),
        key=lambda path: int(path.stem.rsplit("p", 1)[1]),
    )
    if len(frames) != 10:
        raise ValueError(f"{roi_root.name}: expected 10 FSHG frames, found {len(frames)}.")
    return frames


def _load_roi(roi_root: Path) -> dict[str, np.ndarray]:
    frames = np.stack([tifffile.imread(path).astype(np.float64) for path in _frame_paths(roi_root)])
    reference = tifffile.imread(roi_root / "FI.tif").astype(np.float64)
    r2 = tifffile.imread(roi_root / "R2.tif").astype(np.float64)
    snr = tifffile.imread(roi_root / "SNR.tif").astype(np.float64)
    if frames.ndim != 3 or frames.shape[1:] != reference.shape or r2.shape != reference.shape or snr.shape != reference.shape:
        raise ValueError(f"{roi_root.name}: PSHG arrays are not spatially aligned.")
    return {"frames": frames, "reference": reference, "r2": r2, "snr": snr}


def _resize_back(image: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return np.asarray(image, dtype=np.float64).copy()
    height, width = image.shape
    small = ndimage.zoom(image, zoom=(1.0 / factor, 1.0 / factor), order=1, mode="reflect", prefilter=False)
    restored = ndimage.zoom(
        small,
        zoom=(height / small.shape[0], width / small.shape[1]),
        order=1,
        mode="reflect",
        prefilter=False,
    )
    output = np.empty((height, width), dtype=np.float64)
    output[:] = float(np.median(restored))
    y = min(height, restored.shape[0])
    x = min(width, restored.shape[1])
    output[:y, :x] = restored[:y, :x]
    return output


def apply_condition(
    frames: np.ndarray,
    condition: Mapping[str, Any],
    *,
    roi_name: str,
    seed: int,
) -> np.ndarray:
    """Apply the frozen blur-motion-resampling-contrast-noise sequence."""

    shifted = np.asarray(frames, dtype=np.float64).copy()
    blur = float(condition.get("blur_sigma", 0.0))
    if blur > 0:
        shifted = np.stack(
            [ndimage.gaussian_filter(frame, sigma=blur, mode="reflect") for frame in shifted]
        )
    motion = float(condition.get("motion_radius", 0.0))
    if motion > 0:
        moved = []
        for index, frame in enumerate(shifted):
            phase = 2.0 * math.pi * index / len(shifted)
            displacement = (motion * math.sin(phase), motion * math.cos(phase))
            moved.append(
                ndimage.shift(
                    frame,
                    shift=displacement,
                    order=1,
                    mode="reflect",
                    prefilter=False,
                )
            )
        shifted = np.stack(moved)
    resample = int(condition.get("resample_factor", 1))
    if resample > 1:
        shifted = np.stack([_resize_back(frame, resample) for frame in shifted])
    contrast = float(condition.get("contrast_factor", 1.0))
    if contrast != 1.0:
        medians = np.median(shifted, axis=(1, 2), keepdims=True)
        shifted = medians + contrast * (shifted - medians)
    target_snr = condition.get("noise_snr_db")
    if target_snr is not None:
        noisy = []
        for index, frame in enumerate(shifted):
            rng = np.random.default_rng(
                _stable_seed(seed, roi_name, condition["id"], index)
            )
            scale = float(np.std(frame)) / (10.0 ** (float(target_snr) / 20.0))
            noisy.append(frame + rng.normal(0.0, scale, size=frame.shape))
        shifted = np.stack(noisy)
    return np.maximum(shifted, 0.0)


def _gradient_direction(image: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    smoothed = ndimage.gaussian_filter(image, sigma=sigma, mode="reflect")
    gy, gx = np.gradient(smoothed)
    return np.degrees(np.mod(np.arctan2(gy, gx) + np.pi / 2.0, np.pi))


def _qc_risk(qc: Mapping[str, Any], config: Mapping[str, Any]) -> float:
    constants = config["risk_components"]
    if qc["status"] == "abstain":
        return 2.0
    endpoint_risk = float(qc["observed_endpoint_fraction"]) / float(
        constants["maximum_endpoint_fraction"]
    )
    residual_risk = float(constants["minimum_contrast_to_residual"]) / max(
        float(qc["contrast_to_residual"]), np.finfo(float).eps
    )
    focus = max(float(qc["tenengrad_focus_v2"]), 0.0)
    focus_risk = 1.0 / (1.0 + 20.0 * math.sqrt(focus))
    return float(max(endpoint_risk, residual_risk, focus_risk))


def policy_scores(
    components: Mapping[str, float],
    policies: Mapping[str, Sequence[str]],
) -> dict[str, float]:
    output: dict[str, float] = {}
    for name, included in policies.items():
        if not included:
            raise ValueError(f"Policy {name!r} must contain at least one component.")
        missing = [component for component in included if component not in components]
        if missing:
            raise KeyError(f"Policy {name!r} references missing components: {missing}")
        output[name] = float(max(components[component] for component in included))
    return output


def _case_row(
    roi_root: Path,
    condition: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    loaded = _load_roi(roi_root)
    measurement = config["measurement"]
    clean_mean = np.mean(loaded["frames"], axis=0)
    eligible = (
        np.isfinite(loaded["reference"])
        & np.isfinite(loaded["r2"])
        & np.isfinite(loaded["snr"])
        & (loaded["r2"] >= float(measurement["minimum_reference_r2"]))
        & (loaded["snr"] >= float(measurement["minimum_reference_snr_db"]))
        & (clean_mean > 0)
    )
    edge = int(measurement["edge_exclusion_pixels"])
    eligible[:edge] = False
    eligible[-edge:] = False
    eligible[:, :edge] = False
    eligible[:, -edge:] = False
    support_pixels = int(np.sum(eligible))
    if support_pixels < int(measurement["minimum_adjudicable_pixels"]):
        raise ValueError(
            f"{roi_root.name}/{condition['id']}: only {support_pixels} adjudicable pixels."
        )

    shifted = apply_condition(
        loaded["frames"],
        condition,
        roi_name=roi_root.name,
        seed=int(config["calibration"]["seed"]),
    )
    image = np.mean(shifted, axis=0)
    sigma2 = float(measurement["integration_sigma_pixels"])
    sigma4 = float(measurement["comparison_sigma_pixels"])
    angles, coherence, _ = _tensor_fields(image, scales=(sigma2, sigma4))
    even_angle = _tensor_fields(np.mean(shifted[::2], axis=0), scales=(sigma2,))[0][0]
    odd_angle = _tensor_fields(np.mean(shifted[1::2], axis=0), scales=(sigma2,))[0][0]
    gradient = _gradient_direction(image, sigma=sigma2)

    yy, xx = np.nonzero(eligible)
    reference = np.mod(
        loaded["reference"][yy, xx] + float(measurement["reference_offset_degrees"]),
        180.0,
    )
    primary_errors = _axial_errors(angles[0, yy, xx], reference)
    sigma4_errors = _axial_errors(angles[1, yy, xx], reference)
    gradient_errors = _axial_errors(gradient[yy, xx], reference)
    median_error = float(np.median(primary_errors))
    p75_error = float(np.percentile(primary_errors, 75.0))

    qc = acquisition_qc_on_support(image, eligible)
    median_coherence = float(np.median(coherence[0, yy, xx]))
    interscale = float(np.median(_axial_errors(angles[0, yy, xx], angles[1, yy, xx])))
    split_stack = float(np.median(_axial_errors(even_angle[yy, xx], odd_angle[yy, xx])))
    constants = config["risk_components"]
    components = {
        "acquisition_qc": _qc_risk(qc, config),
        "coherence": float(constants["minimum_median_coherence"])
        / max(median_coherence, np.finfo(float).eps),
        "scale_consistency": interscale
        / float(constants["maximum_interscale_disagreement_degrees"]),
        "split_stack": split_stack
        / float(constants["maximum_split_stack_disagreement_degrees"]),
    }
    scores = policy_scores(components, config["policies"])
    invalid = bool(
        median_error > float(measurement["invalid_median_error_degrees"])
        or p75_error > float(measurement["invalid_p75_error_degrees"])
    )
    return {
        "case_id": f"{roi_root.name}|{condition['id']}",
        "structure": "pshg_breast",
        "reference_group_id": roi_root.name,
        "roi": roi_root.name,
        "condition": str(condition["id"]),
        "endpoint": "local_orientation",
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": False,
        "adjudicable_pixels": support_pixels,
        "median_error_degrees": median_error,
        "p75_error_degrees": p75_error,
        "sigma4_median_error_degrees": float(np.median(sigma4_errors)),
        "gradient_median_error_degrees": float(np.median(gradient_errors)),
        "invalid": invalid,
        "diagnostics": {
            "acquisition_qc": qc,
            "median_coherence": median_coherence,
            "median_interscale_disagreement_degrees": interscale,
            "median_split_stack_disagreement_degrees": split_stack,
            "components": components,
        },
        "scores": scores,
    }


def _dataset_split(dataset_root: Path, config: Mapping[str, Any]) -> dict[str, list[str]]:
    names = sorted(path.name for path in dataset_root.iterdir() if path.is_dir())
    split = config["split"]
    return split_rois(
        names,
        salt=str(split["salt"]),
        development_rois=int(split["development_rois"]),
        confirmation_rois=int(split["confirmation_rois"]),
    )


def _generate_rows(
    dataset_root: Path,
    config: Mapping[str, Any],
    roi_names: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for roi_name in roi_names:
        roi_root = dataset_root / roi_name
        for condition in config["conditions"]:
            rows.append(_case_row(roi_root, condition, config))
    rows.sort(key=lambda row: str(row["case_id"]))
    return rows


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _policy_development(
    rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    policy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    calibration = config["calibration"]
    augmented, maps = cross_fitted_family_risk(
        rows,
        family_map={"orientation": ["local_orientation"]},
        raw_score=policy,
        bins=int(calibration["bins"]),
        folds=int(calibration["folds"]),
        seed=int(calibration["seed"]),
        prior_alpha=float(calibration["prior_alpha"]),
        prior_beta=float(calibration["prior_beta"]),
    )
    summary = calibrated_operating_summary(
        augmented,
        maximum_predicted_risk=float(calibration["maximum_predicted_risk"]),
    )
    summary["risk_coverage_auc"] = risk_coverage_auc(augmented, score_key="calibrated_risk")
    return summary, maps["orientation"].to_dict()


def run_development(
    dataset_root: Path,
    config_path: Path,
    protocol_path: Path,
    output: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    split = _dataset_split(dataset_root, config)
    rows = _generate_rows(dataset_root, config, split["development"])
    policy_summaries: dict[str, Any] = {}
    risk_maps: dict[str, Any] = {}
    for policy in POLICY_NAMES:
        summary, risk_map = _policy_development(rows, config, policy)
        policy_summaries[policy] = summary
        risk_maps[policy] = risk_map
    invalid = int(sum(bool(row["invalid"]) for row in rows))
    profile = {
        "schema_version": "nostos-pshg-acquisition-shift-profile/1.0",
        "protocol_version": config["protocol_version"],
        "protocol_sha256": _sha256(protocol_path),
        "config_sha256": _sha256(config_path),
        "split": split,
        "policies": config["policies"],
        "risk_maps": risk_maps,
        "maximum_predicted_risk": float(config["calibration"]["maximum_predicted_risk"]),
        "reference_values_available_at_deployment": False,
    }
    result = {
        "protocol_version": config["protocol_version"],
        "status": "development_complete_confirmation_locked",
        "development": {
            "rois": len(split["development"]),
            "cases": len(rows),
            "invalid": invalid,
            "invalid_risk": float(invalid / len(rows)),
            "policy_summaries": policy_summaries,
        },
        "split": split,
        "profile": profile,
        "claim_boundary": config["claim_boundary"],
    }
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / "development_rows.jsonl", rows)
    (output / "validity_profile.json").write_text(
        json.dumps(profile, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output / "development.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result


def freeze_profile(
    dataset_root: Path,
    config_path: Path,
    protocol_path: Path,
    profile_path: Path,
    lock_path: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    split = _dataset_split(dataset_root, config)
    if profile["split"] != split:
        raise ValueError("Development profile split does not match the frozen hash split.")
    if profile["config_sha256"] != _sha256(config_path) or profile["protocol_sha256"] != _sha256(protocol_path):
        raise ValueError("Development profile does not match the current frozen protocol/configuration.")
    manifest_path = dataset_root / "download_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing source manifest: {manifest_path}")
    lock = {
        "schema_version": "nostos-pshg-acquisition-shift-lock/1.0",
        "protocol_version": config["protocol_version"],
        "protocol_path": protocol_path.as_posix(),
        "protocol_sha256": _sha256(protocol_path),
        "config_path": config_path.as_posix(),
        "config_sha256": _sha256(config_path),
        "profile_path": profile_path.as_posix(),
        "profile_sha256": _sha256(profile_path),
        "source_manifest_path": manifest_path.as_posix(),
        "source_manifest_sha256": _sha256(manifest_path),
        "split": split,
        "confirmation_pixels_opened": False,
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return lock


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


def _annotate_policy(
    rows: Sequence[Mapping[str, Any]], profile: Mapping[str, Any], policy: str
) -> list[dict[str, Any]]:
    model = _risk_map(profile["risk_maps"][policy])
    values = model.predict([float(row["scores"][policy]) for row in rows])
    annotated = []
    for row, predicted in zip(rows, values, strict=True):
        clone = dict(row)
        clone["calibrated_risk"] = float(predicted)
        annotated.append(clone)
    return annotated


def _operating(rows: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    accepted = [row for row in rows if float(row["calibrated_risk"]) <= threshold]
    invalid = int(sum(bool(row["invalid"]) for row in accepted))
    return {
        "eligible": len(rows),
        "accepted": len(accepted),
        "coverage": float(len(accepted) / len(rows)),
        "invalid": invalid,
        "risk": float(invalid / len(accepted)) if accepted else None,
    }


def _lowest_risk(rows: Sequence[Mapping[str, Any]], count: int) -> list[Mapping[str, Any]]:
    return sorted(rows, key=lambda row: (float(row["calibrated_risk"]), str(row["case_id"])))[:count]


def _risk(rows: Sequence[Mapping[str, Any]]) -> float:
    return float(np.mean([bool(row["invalid"]) for row in rows])) if rows else 1.0


def _resample_rows(rows: Sequence[Mapping[str, Any]], indices: np.ndarray, rois: Sequence[str]) -> list[dict[str, Any]]:
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


def _bootstrap(
    policy_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    threshold: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    rois = sorted({str(row["roi"]) for row in policy_rows["full_contract"]})
    rng = np.random.default_rng(seed)
    full_risk: list[float] = []
    risk_differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    aurc_differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    for _ in range(draws):
        indices = rng.integers(0, len(rois), len(rois))
        sampled = {
            name: _resample_rows(rows, indices, rois) for name, rows in policy_rows.items()
        }
        full_selected = [
            row
            for row in sampled["full_contract"]
            if float(row["calibrated_risk"]) <= threshold
        ]
        if not full_selected:
            continue
        full_value = _risk(full_selected)
        full_risk.append(full_value)
        count = len(full_selected)
        full_aurc = risk_coverage_auc(sampled["full_contract"], score_key="calibrated_risk")
        for name in risk_differences:
            selected = _lowest_risk(sampled[name], count)
            risk_differences[name].append(_risk(selected) - full_value)
            comparator_aurc = risk_coverage_auc(sampled[name], score_key="calibrated_risk")
            aurc_differences[name].append(comparator_aurc - full_aurc)

    def interval(values: Sequence[float]) -> list[float]:
        if not values:
            return [0.0, 1.0]
        return [float(value) for value in np.quantile(np.asarray(values), (0.025, 0.975))]

    return {
        "draws_requested": int(draws),
        "draws_retained": len(full_risk),
        "full_risk_95": interval(full_risk),
        "matched_risk_difference_95": {
            name: interval(values) for name, values in risk_differences.items()
        },
        "aurc_difference_95": {
            name: interval(values) for name, values in aurc_differences.items()
        },
    }


def _decision_hash(rows: Sequence[Mapping[str, Any]], threshold: float) -> str:
    payload = [
        (str(row["case_id"]), bool(float(row["calibrated_risk"]) <= threshold))
        for row in rows
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def run_confirmation(
    dataset_root: Path,
    config_path: Path,
    protocol_path: Path,
    profile_path: Path,
    lock_path: Path,
    output: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    manifest_path = dataset_root / "download_manifest.json"
    current_hashes = {
        "protocol_sha256": _sha256(protocol_path),
        "config_sha256": _sha256(config_path),
        "profile_sha256": _sha256(profile_path),
        "source_manifest_sha256": _sha256(manifest_path),
    }
    for key, value in current_hashes.items():
        if lock[key] != value:
            raise ValueError(f"Frozen lock mismatch for {key}.")
    split = _dataset_split(dataset_root, config)
    if split != lock["split"] or split != profile["split"]:
        raise ValueError("Confirmation split does not match the frozen lock/profile.")
    rows = _generate_rows(dataset_root, config, split["confirmation"])
    policy_rows = {
        policy: _annotate_policy(rows, profile, policy) for policy in POLICY_NAMES
    }
    threshold = float(profile["maximum_predicted_risk"])
    operating = {name: _operating(values, threshold) for name, values in policy_rows.items()}
    operating["always_emit"] = {
        "eligible": len(rows),
        "accepted": len(rows),
        "coverage": 1.0,
        "invalid": int(sum(bool(row["invalid"]) for row in rows)),
        "risk": float(np.mean([bool(row["invalid"]) for row in rows])),
    }
    aurc = {
        name: risk_coverage_auc(values, score_key="calibrated_risk")
        for name, values in policy_rows.items()
    }
    full_count = int(operating["full_contract"]["accepted"])
    full_selected = [
        row
        for row in policy_rows["full_contract"]
        if float(row["calibrated_risk"]) <= threshold
    ]
    matched = {
        name: {
            "accepted": full_count,
            "coverage": float(full_count / len(rows)),
            "invalid": int(sum(bool(row["invalid"]) for row in _lowest_risk(policy_rows[name], full_count))),
            "risk": _risk(_lowest_risk(policy_rows[name], full_count)),
        }
        for name in ("acquisition_qc", "endpoint_qc")
    }
    matched["full_contract"] = {
        "accepted": full_count,
        "coverage": float(full_count / len(rows)),
        "invalid": int(sum(bool(row["invalid"]) for row in full_selected)),
        "risk": _risk(full_selected),
    }
    bootstrap = _bootstrap(
        policy_rows,
        threshold=threshold,
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]),
    )
    clean = [row for row in rows if row["condition"] == "clean"]
    clean_full = [
        row
        for row in policy_rows["full_contract"]
        if row["condition"] == "clean" and float(row["calibrated_risk"]) <= threshold
    ]
    primary_clean = float(np.median([row["median_error_degrees"] for row in clean]))
    sigma4_clean = float(np.median([row["sigma4_median_error_degrees"] for row in clean]))
    gradient_clean = float(np.median([row["gradient_median_error_degrees"] for row in clean]))

    before = _decision_hash(policy_rows["full_contract"], threshold)
    mutated = []
    for row in policy_rows["full_contract"]:
        clone = dict(row)
        clone["invalid"] = not bool(row["invalid"])
        clone["median_error_degrees"] = 90.0 - float(row["median_error_degrees"])
        clone["p75_error_degrees"] = 90.0 - float(row["p75_error_degrees"])
        mutated.append(clone)
    after = _decision_hash(mutated, threshold)
    label_blind = before == after

    rules = config["success_gates"]
    full_risk = float(matched["full_contract"]["risk"])
    risk_reductions = {
        name: float(matched[name]["risk"] - full_risk)
        for name in ("acquisition_qc", "endpoint_qc")
    }
    aurc_differences = {
        name: float(aurc[name] - aurc["full_contract"])
        for name in ("acquisition_qc", "endpoint_qc")
    }
    ablation_increases = {
        name: float(aurc[name] - aurc["full_contract"])
        for name in ("without_scale_consistency", "without_split_consistency")
    }
    gates = {
        "exact_confirmation_rois_and_cases": len(split["confirmation"])
        == int(rules["confirmation_rois"])
        and len(rows) == int(rules["confirmation_cases"]),
        "invalid_cases_assessable": int(sum(bool(row["invalid"]) for row in rows))
        >= int(rules["minimum_invalid_cases"]),
        "full_coverage": float(operating["full_contract"]["coverage"])
        >= float(rules["minimum_full_coverage"]),
        "full_risk_upper95": float(bootstrap["full_risk_95"][1])
        <= float(rules["maximum_full_risk_upper95"]),
        "matched_risk_reduction_vs_acquisition_qc": risk_reductions["acquisition_qc"]
        >= float(rules["minimum_matched_risk_reduction"]),
        "matched_risk_reduction_vs_endpoint_qc": risk_reductions["endpoint_qc"]
        >= float(rules["minimum_matched_risk_reduction"]),
        "aurc_advantage_vs_acquisition_qc": aurc_differences["acquisition_qc"] > 0
        and float(bootstrap["aurc_difference_95"]["acquisition_qc"][0]) > 0,
        "aurc_advantage_vs_endpoint_qc": aurc_differences["endpoint_qc"] > 0
        and float(bootstrap["aurc_difference_95"]["endpoint_qc"][0]) > 0,
        "component_ablation": max(ablation_increases.values())
        >= float(rules["minimum_ablation_aurc_increase"]),
        "clean_preservation": len(clean_full) / len(clean)
        >= float(rules["minimum_clean_coverage"])
        and primary_clean <= float(rules["maximum_clean_median_error_degrees"]),
        "upstream_estimator_noninferiority": primary_clean
        <= sigma4_clean + float(rules["upstream_noninferiority_margin_degrees"])
        and primary_clean
        <= gradient_clean + float(rules["upstream_noninferiority_margin_degrees"]),
        "reference_label_blindness": label_blind,
    }
    result = {
        "protocol_version": config["protocol_version"],
        "status": "pass" if all(gates.values()) else "fail",
        "lock_sha256": _sha256(lock_path),
        "split": split,
        "summary": {
            "rois": len(split["confirmation"]),
            "cases": len(rows),
            "invalid_cases": int(sum(bool(row["invalid"]) for row in rows)),
            "operating": operating,
            "matched_coverage": matched,
            "risk_reductions": risk_reductions,
            "risk_coverage_auc": aurc,
            "aurc_differences": aurc_differences,
            "ablation_aurc_increases": ablation_increases,
            "clean": {
                "eligible": len(clean),
                "accepted": len(clean_full),
                "coverage": float(len(clean_full) / len(clean)),
                "primary_median_error_degrees": primary_clean,
                "sigma4_median_error_degrees": sigma4_clean,
                "gradient_median_error_degrees": gradient_clean,
            },
        },
        "bootstrap": bootstrap,
        "label_blindness_audit": {
            "before_sha256": before,
            "after_reference_mutation_sha256": after,
            "unchanged": label_blind,
        },
        "success_gates": gates,
        "claim_boundary": config["claim_boundary"],
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / "confirmation_rows.jsonl", rows)
    (output / "confirmation.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result
