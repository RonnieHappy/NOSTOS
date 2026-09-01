"""Development and locked-transfer helpers for the TLT pSHG-XRD dataset.

The deposit pairs a conventional mean SHG image with derived pSHG maps.  The
SHG image is the only estimator input.  ``Phi2_thresholded`` and
``I2_thresholded`` are withheld references and must never enter an eligibility
or abstention decision.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage
from scipy.io import loadmat
from scipy.stats import spearmanr

from nostos.intraop.support_qc import acquisition_qc_on_support
from nostos.validation.family_risk_calibration import (
    calibrated_operating_summary,
    cross_fitted_family_risk,
    risk_coverage_auc,
)
from nostos.validation.local_orientation import _axial_errors, _tensor_fields


PIXEL_SPACING_UM = 384.5 / 512.0
ZONES = ("NM", "EM", "LM")
SPLIT_SALT = "nostos_tlt_pshg_xrd_v1"
DEVELOPMENT_SAMPLES = ("Sample3", "Sample1")
CONFIRMATION_SAMPLES = ("Sample2", "Sample4")
POLICY_NAMES = (
    "acquisition_qc",
    "endpoint_qc",
    "without_scale_consistency",
    "without_coherence",
    "full_contract",
)


def sample_hash(sample_id: str, *, salt: str = SPLIT_SALT) -> str:
    """Return the frozen specimen-level split hash."""

    return hashlib.sha256(f"{salt}|{sample_id}".encode("utf-8")).hexdigest()


def frozen_split(sample_ids: Sequence[str]) -> dict[str, list[str]]:
    """Reproduce the prelocked two-specimen development/confirmation split."""

    ordered = sorted({str(value) for value in sample_ids}, key=sample_hash)
    if ordered != ["Sample3", "Sample1", "Sample2", "Sample4"]:
        raise ValueError(f"Unexpected specimen identities or split order: {ordered}")
    return {"development": ordered[:2], "confirmation": ordered[2:]}


def _record_name(value: Any, fallback: str) -> str:
    text = str(np.asarray(value).item()) if np.asarray(value).shape == () else str(value)
    return text.strip() or fallback


def load_region_file(path: Path) -> list[dict[str, Any]]:
    """Load one deposited MATLAB region file without changing reference arrays."""

    payload = loadmat(path, squeeze_me=True, struct_as_record=False)
    if "Gdata4" not in payload:
        raise ValueError(f"{path.name}: missing Gdata4 structure")
    records = np.atleast_1d(payload["Gdata4"])
    output: list[dict[str, Any]] = []
    required = (
        "SHG",
        "Phi2_thresholded",
        "I2_thresholded",
        "Threshold",
        "name",
    )
    for index, record in enumerate(records):
        missing = [name for name in required if not hasattr(record, name)]
        if missing:
            raise ValueError(f"{path.name}/record-{index}: missing {missing}")
        image = np.asarray(record.SHG, dtype=np.float64)
        phi2 = np.asarray(record.Phi2_thresholded, dtype=np.float64)
        i2 = np.asarray(record.I2_thresholded, dtype=np.float64)
        if image.shape != (512, 512) or phi2.shape != image.shape or i2.shape != image.shape:
            raise ValueError(
                f"{path.name}/record-{index}: expected aligned 512 x 512 arrays"
            )
        if not np.isfinite(image).all() or float(np.std(image)) <= 0:
            raise ValueError(f"{path.name}/record-{index}: invalid SHG image")
        output.append(
            {
                "record_index": int(index),
                "record_name": _record_name(record.name, f"record-{index}"),
                "shg": image,
                "phi2_reference": phi2,
                "i2_reference": i2,
                "deposited_intensity_threshold": float(np.asarray(record.Threshold).item()),
            }
        )
    return output


def iter_fields(
    dataset_root: Path,
    samples: Iterable[str],
) -> Iterable[dict[str, Any]]:
    """Yield deposited fields while preserving specimen and zone identifiers."""

    selected = tuple(samples)
    if any(sample in CONFIRMATION_SAMPLES for sample in selected):
        raise PermissionError(
            "Confirmation arrays are sealed during development; use the locked "
            "confirmation entry point after freezing the protocol."
        )
    yield from _iter_fields_unchecked(dataset_root, selected)


def _iter_fields_unchecked(
    dataset_root: Path,
    samples: Iterable[str],
) -> Iterable[dict[str, Any]]:
    for sample in samples:
        for zone in ZONES:
            path = dataset_root / f"{sample}{zone}.mat"
            for record in load_region_file(path):
                yield {
                    **record,
                    "sample": sample,
                    "zone": zone,
                    "field_id": f"{sample}-{zone}-{record['record_index']:02d}",
                    "source_file": path.name,
                }


def _transform(image: np.ndarray, name: str) -> np.ndarray:
    data = np.asarray(image, dtype=np.float64)
    if name == "raw":
        return data
    if name == "log1p":
        return np.log1p(np.maximum(data, 0.0))
    raise KeyError(name)


def _reference_mask(reference: np.ndarray, edge_pixels: int) -> np.ndarray:
    mask = np.isfinite(reference)
    if edge_pixels:
        mask[:edge_pixels] = False
        mask[-edge_pixels:] = False
        mask[:, :edge_pixels] = False
        mask[:, -edge_pixels:] = False
    return mask


def screen_clean_candidates(
    dataset_root: Path,
    *,
    transforms: Sequence[str] = ("raw", "log1p"),
    scales_um: Sequence[float] = (1.5, 3.0, 6.0, 12.0),
    reference_offsets_degrees: Sequence[float] = (0.0, 90.0),
    edge_pixels: int = 8,
) -> dict[str, Any]:
    """Screen a small, predeclared clean-input grid on development specimens only."""

    fields = list(iter_fields(dataset_root, DEVELOPMENT_SAMPLES))
    rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for transform in transforms:
        for field in fields:
            image = _transform(field["shg"], transform)
            sigma_pixels = tuple(float(scale) / PIXEL_SPACING_UM for scale in scales_um)
            angles, coherence, energy = _tensor_fields(image, scales=sigma_pixels)
            reference_base = np.asarray(field["phi2_reference"], dtype=float)
            mask = _reference_mask(reference_base, edge_pixels)
            if int(mask.sum()) < 1000:
                raise ValueError(f"{field['field_id']}: insufficient deposited reference")
            for scale_index, scale_um in enumerate(scales_um):
                for offset in reference_offsets_degrees:
                    reference = np.mod(reference_base[mask] + float(offset), 180.0)
                    errors = _axial_errors(angles[scale_index][mask], reference)
                    rows.append(
                        {
                            "field_id": field["field_id"],
                            "sample": field["sample"],
                            "zone": field["zone"],
                            "transform": transform,
                            "scale_um": float(scale_um),
                            "sigma_pixels": float(sigma_pixels[scale_index]),
                            "reference_offset_degrees": float(offset),
                            "adjudicable_pixels": int(mask.sum()),
                            "median_error_degrees": float(np.median(errors)),
                            "p75_error_degrees": float(np.percentile(errors, 75.0)),
                            "axial_alignment": float(
                                np.mean(np.cos(2.0 * np.radians(errors)))
                            ),
                            "median_coherence": float(np.median(coherence[scale_index][mask])),
                            "median_energy": float(np.median(energy[scale_index][mask])),
                        }
                    )

    keys = (
        "transform",
        "scale_um",
        "sigma_pixels",
        "reference_offset_degrees",
    )
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[key] for key in keys), []).append(row)
    for key, values in grouped.items():
        sample_medians: dict[str, float] = {}
        for sample in DEVELOPMENT_SAMPLES:
            sample_rows = [
                float(row["median_error_degrees"])
                for row in values
                if row["sample"] == sample
            ]
            sample_medians[sample] = float(np.median(sample_rows))
        candidates.append(
            {
                **dict(zip(keys, key, strict=True)),
                "fields": len(values),
                "median_field_median_error_degrees": float(
                    np.median([row["median_error_degrees"] for row in values])
                ),
                "median_field_p75_error_degrees": float(
                    np.median([row["p75_error_degrees"] for row in values])
                ),
                "median_field_axial_alignment": float(
                    np.median([row["axial_alignment"] for row in values])
                ),
                "sample_median_errors_degrees": sample_medians,
            }
        )
    candidates.sort(
        key=lambda row: (
            float(row["median_field_median_error_degrees"]),
            float(row["median_field_p75_error_degrees"]),
            str(row["transform"]),
            float(row["scale_um"]),
            float(row["reference_offset_degrees"]),
        )
    )
    return {
        "schema_version": "nostos.tlt_pshg_xrd.clean_candidate_screen.v1",
        "status": "development_only_confirmation_sealed",
        "dataset_doi": "10.5281/zenodo.10979115",
        "pixel_spacing_um": PIXEL_SPACING_UM,
        "development_samples": list(DEVELOPMENT_SAMPLES),
        "confirmation_samples_opened": False,
        "fields": len(fields),
        "candidates": candidates,
        "selected_candidate": candidates[0],
        "rows": rows,
        "claim_boundary": "Development-only coordinate and physical-scale selection; no confirmation or transfer claim.",
    }


def write_screen(result: Mapping[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "candidate_screen.json").write_text(
        json.dumps(dict(result), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _resize_back(image: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return np.asarray(image, dtype=np.float64).copy()
    height, width = image.shape
    small = ndimage.zoom(
        image,
        zoom=(1.0 / factor, 1.0 / factor),
        order=1,
        mode="reflect",
        prefilter=False,
    )
    restored = ndimage.zoom(
        small,
        zoom=(height / small.shape[0], width / small.shape[1]),
        order=1,
        mode="reflect",
        prefilter=False,
    )
    output = np.full((height, width), float(np.median(restored)), dtype=np.float64)
    y = min(height, restored.shape[0])
    x = min(width, restored.shape[1])
    output[:y, :x] = restored[:y, :x]
    return output


def apply_condition(
    image: np.ndarray,
    condition: Mapping[str, Any],
    *,
    field_id: str,
    seed: int,
) -> np.ndarray:
    """Apply the predeclared single-image degradation sequence in raw units."""

    shifted = np.asarray(image, dtype=np.float64).copy()
    blur = float(condition.get("blur_sigma_pixels", 0.0))
    if blur > 0:
        shifted = ndimage.gaussian_filter(shifted, sigma=blur, mode="reflect")
    resample = int(condition.get("resample_factor", 1))
    if resample > 1:
        shifted = _resize_back(shifted, resample)
    contrast = float(condition.get("contrast_factor", 1.0))
    if contrast != 1.0:
        median = float(np.median(shifted))
        shifted = median + contrast * (shifted - median)
    target_snr = condition.get("noise_snr_db")
    if target_snr is not None:
        rng = np.random.default_rng(
            _stable_seed(seed, field_id, str(condition["id"]))
        )
        scale = float(np.std(shifted)) / (10.0 ** (float(target_snr) / 20.0))
        shifted = shifted + rng.normal(0.0, scale, size=shifted.shape)
    return np.maximum(shifted, 0.0)


def _gradient_direction(image: np.ndarray, sigma_pixels: float) -> np.ndarray:
    smoothed = ndimage.gaussian_filter(image, sigma=sigma_pixels, mode="reflect")
    gy, gx = np.gradient(smoothed)
    return np.degrees(np.mod(np.arctan2(gy, gx) + np.pi / 2.0, np.pi))


def _input_support(image: np.ndarray, edge_pixels: int) -> np.ndarray:
    finite = np.isfinite(image)
    positive = image[finite & (image > 0)]
    if not len(positive):
        return np.zeros(image.shape, dtype=bool)
    threshold = float(np.percentile(positive, 20.0))
    support = finite & (image >= threshold)
    if edge_pixels:
        support[:edge_pixels] = False
        support[-edge_pixels:] = False
        support[:, :edge_pixels] = False
        support[:, -edge_pixels:] = False
    return support


def _qc_risk(qc: Mapping[str, Any], constants: Mapping[str, Any]) -> float:
    if qc["status"] == "abstain":
        return 2.0
    endpoint_risk = float(qc["observed_endpoint_fraction"]) / float(
        constants["maximum_endpoint_fraction"]
    )
    residual_risk = float(constants["minimum_contrast_to_residual"]) / max(
        float(qc["contrast_to_residual"]), np.finfo(float).eps
    )
    focus = max(float(qc["tenengrad_focus_v2"]), 0.0)
    focus_risk = 1.0 / (1.0 + 20.0 * np.sqrt(focus))
    return float(max(endpoint_risk, residual_risk, focus_risk))


def _policy_scores(
    components: Mapping[str, float], policies: Mapping[str, Sequence[str]]
) -> dict[str, float]:
    output: dict[str, float] = {}
    for name, included in policies.items():
        missing = [component for component in included if component not in components]
        if missing:
            raise KeyError(f"Policy {name!r} references missing components: {missing}")
        output[name] = float(max(components[component] for component in included))
    return output


def _field_case(
    field: Mapping[str, Any],
    condition: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    measurement = config["measurement"]
    raw = apply_condition(
        np.asarray(field["shg"], dtype=float),
        condition,
        field_id=str(field["field_id"]),
        seed=int(config["calibration"]["seed"]),
    )
    image = _transform(raw, str(measurement["transform"]))
    primary_um = float(measurement["primary_scale_um"])
    comparison_um = float(measurement["comparison_scale_um"])
    sigma_pixels = (
        primary_um / PIXEL_SPACING_UM,
        comparison_um / PIXEL_SPACING_UM,
    )
    angles, coherence, _ = _tensor_fields(image, scales=sigma_pixels)
    gradient = _gradient_direction(image, sigma_pixels=float(sigma_pixels[0]))

    edge = int(measurement["edge_exclusion_pixels"])
    reference_base = np.asarray(field["phi2_reference"], dtype=float)
    reference_mask = _reference_mask(reference_base, edge)
    input_support = _input_support(image, edge)
    hard_abstention = int(input_support.sum()) < int(
        measurement["minimum_input_support_pixels"]
    )
    reference_eligible = int(reference_mask.sum()) >= int(
        measurement["minimum_adjudicable_pixels"]
    )
    if not reference_eligible:
        raise ValueError(f"{field['field_id']}: insufficient deposited reference")

    reference = np.mod(
        reference_base[reference_mask]
        + float(measurement["reference_offset_degrees"]),
        180.0,
    )
    primary_error = _axial_errors(angles[0][reference_mask], reference)
    comparison_error = _axial_errors(angles[1][reference_mask], reference)
    gradient_error = _axial_errors(gradient[reference_mask], reference)
    median_error = float(np.median(primary_error))
    p75_error = float(np.percentile(primary_error, 75.0))

    if hard_abstention:
        qc = {"status": "abstain", "reasons": ["insufficient_input_support"]}
        median_coherence = 0.0
        interscale = 90.0
        estimator = 90.0
    else:
        qc = acquisition_qc_on_support(image, input_support)
        median_coherence = float(np.median(coherence[0][input_support]))
        interscale = float(
            np.median(_axial_errors(angles[0][input_support], angles[1][input_support]))
        )
        estimator = float(
            np.median(_axial_errors(angles[0][input_support], gradient[input_support]))
        )
    constants = config["risk_components"]
    components = {
        "acquisition_qc": _qc_risk(qc, constants),
        "coherence": float(constants["minimum_median_coherence"])
        / max(median_coherence, np.finfo(float).eps),
        "scale_consistency": interscale
        / float(constants["maximum_interscale_disagreement_degrees"]),
        "estimator_consistency": estimator
        / float(constants["maximum_estimator_disagreement_degrees"]),
    }
    scores = _policy_scores(components, config["policies"])
    invalid = bool(
        median_error > float(measurement["invalid_median_error_degrees"])
        or p75_error > float(measurement["invalid_p75_error_degrees"])
    )
    return {
        "case_id": f"{field['field_id']}|{condition['id']}",
        "structure": "tlt_pshg",
        "reference_group_id": str(field["field_id"]),
        "sample": str(field["sample"]),
        "zone": str(field["zone"]),
        "field_id": str(field["field_id"]),
        "condition": str(condition["id"]),
        "endpoint": "local_orientation",
        "pair_registration_eligible": True,
        "reference_eligible": reference_eligible,
        "hard_abstention": hard_abstention,
        "adjudicable_pixels": int(reference_mask.sum()),
        "input_support_pixels": int(input_support.sum()),
        "median_error_degrees": median_error,
        "p75_error_degrees": p75_error,
        "comparison_median_error_degrees": float(np.median(comparison_error)),
        "gradient_median_error_degrees": float(np.median(gradient_error)),
        "organization_reference_mean_i2": float(
            np.nanmean(
                np.asarray(field["i2_reference"], dtype=float)[
                    _reference_mask(
                        np.asarray(field["i2_reference"], dtype=float), edge
                    )
                ]
            )
        ),
        "invalid": invalid,
        "diagnostics": {
            "acquisition_qc": qc,
            "median_coherence": median_coherence,
            "median_interscale_disagreement_degrees": interscale,
            "median_estimator_disagreement_degrees": estimator,
            "components": components,
        },
        "scores": scores,
    }


def generate_development_rows(
    dataset_root: Path, config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    fields = list(iter_fields(dataset_root, DEVELOPMENT_SAMPLES))
    rows = [
        _field_case(field, condition, config)
        for field in fields
        for condition in config["conditions"]
    ]
    rows.sort(key=lambda row: str(row["case_id"]))
    return rows


def run_contract_development(
    dataset_root: Path,
    config_path: Path,
    prelock_path: Path,
    output: Path,
) -> dict[str, Any]:
    """Fit field-separated risk maps without touching confirmation arrays."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    prelock = json.loads(prelock_path.read_text(encoding="utf-8"))
    if prelock["split"]["development"] != list(DEVELOPMENT_SAMPLES):
        raise ValueError("Development split differs from the frozen prelock.")
    if prelock["split"]["confirmation"] != list(CONFIRMATION_SAMPLES):
        raise ValueError("Confirmation split differs from the frozen prelock.")
    rows = generate_development_rows(dataset_root, config)
    policy_summaries: dict[str, Any] = {}
    risk_maps: dict[str, Any] = {}
    calibration = config["calibration"]
    for policy in POLICY_NAMES:
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
        summary["risk_coverage_auc"] = risk_coverage_auc(
            augmented, score_key="calibrated_risk"
        )
        policy_summaries[policy] = summary
        risk_maps[policy] = maps["orientation"].to_dict()
    clean = [row for row in rows if row["condition"] == "clean"]
    profile = {
        "schema_version": "nostos.tlt_pshg_xrd.validity_profile.v1",
        "status": "development_complete_confirmation_sealed",
        "prelock_sha256": hashlib.sha256(prelock_path.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "split": prelock["split"],
        "measurement": config["measurement"],
        "policies": config["policies"],
        "risk_maps": risk_maps,
        "maximum_predicted_risk": float(calibration["maximum_predicted_risk"]),
        "reference_values_available_at_deployment": False,
    }
    result = {
        "schema_version": "nostos.tlt_pshg_xrd.development.v1",
        "status": "development_complete_confirmation_sealed",
        "development": {
            "specimens": len(DEVELOPMENT_SAMPLES),
            "fields": len({row["field_id"] for row in rows}),
            "cases": len(rows),
            "invalid": int(sum(bool(row["invalid"]) for row in rows)),
            "invalid_risk": float(np.mean([bool(row["invalid"]) for row in rows])),
            "clean_median_field_error_degrees": float(
                np.median([row["median_error_degrees"] for row in clean])
            ),
            "clean_median_field_p75_error_degrees": float(
                np.median([row["p75_error_degrees"] for row in clean])
            ),
            "policy_summaries": policy_summaries,
        },
        "profile": profile,
        "claim_boundary": "Development-only support calibration on Samples 1 and 3; no transfer claim.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "development_rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output / "validity_profile.json").write_text(
        json.dumps(profile, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output / "development.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_confirmation_lock(lock: Mapping[str, Any], project_root: Path) -> None:
    pairs = (
        ("protocol_path", "protocol_sha256"),
        ("config_path", "config_sha256"),
        ("prelock_path", "prelock_sha256"),
        ("candidate_screen_path", "candidate_screen_sha256"),
        ("development_profile_path", "development_profile_sha256"),
        ("development_result_path", "development_result_sha256"),
        ("implementation_path", "implementation_sha256"),
    )
    for path_key, hash_key in pairs:
        if path_key not in lock or hash_key not in lock:
            raise ValueError(f"Confirmation lock is missing {path_key}/{hash_key}.")
        path = project_root / str(lock[path_key])
        if _sha256(path) != str(lock[hash_key]):
            raise ValueError(f"Confirmation lock hash mismatch for {path_key}.")
    if bool(lock.get("confirmation_arrays_opened", True)):
        raise ValueError("Lock does not certify that confirmation arrays were sealed.")
    if lock["split"]["development"] != list(DEVELOPMENT_SAMPLES):
        raise ValueError("Locked development split changed.")
    if lock["split"]["confirmation"] != list(CONFIRMATION_SAMPLES):
        raise ValueError("Locked confirmation split changed.")


def _source_receipt(
    dataset_root: Path, prelock: Mapping[str, Any]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for sample in CONFIRMATION_SAMPLES:
        for zone in ZONES:
            name = f"{sample}{zone}.mat"
            expected = prelock["files"][name]
            path = dataset_root / name
            digest = hashlib.md5(path.read_bytes()).hexdigest()  # repository checksum
            size = int(path.stat().st_size)
            rows.append(
                {
                    "file": name,
                    "bytes": size,
                    "expected_bytes": int(expected["bytes"]),
                    "md5": digest,
                    "expected_md5": str(expected["md5"]),
                    "verified": size == int(expected["bytes"])
                    and digest == str(expected["md5"]),
                }
            )
    return {
        "dataset_doi": "10.5281/zenodo.10979115",
        "files": rows,
        "verified_files": int(sum(bool(row["verified"]) for row in rows)),
        "total_files": len(rows),
        "total_bytes": int(sum(int(row["bytes"]) for row in rows)),
        "status": "verified" if all(bool(row["verified"]) for row in rows) else "failed",
    }


def generate_confirmation_rows(
    dataset_root: Path, config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    fields = list(_iter_fields_unchecked(dataset_root, CONFIRMATION_SAMPLES))
    rows = [
        _field_case(field, condition, config)
        for field in fields
        for condition in config["conditions"]
    ]
    rows.sort(key=lambda row: str(row["case_id"]))
    return rows


def _select_tied_nearest(
    rows: Sequence[Mapping[str, Any]],
    count: int,
    *,
    score_key: str,
) -> list[Mapping[str, Any]]:
    """Select complete tied-score groups with cumulative size nearest to count."""

    if count <= 0:
        return []
    ordered = sorted(
        rows, key=lambda row: (float(row[score_key]), str(row["case_id"]))
    )
    groups: list[list[Mapping[str, Any]]] = []
    index = 0
    while index < len(ordered):
        score = float(ordered[index][score_key])
        end = index + 1
        while end < len(ordered) and float(ordered[end][score_key]) == score:
            end += 1
        groups.append(ordered[index:end])
        index = end
    cumulative = np.cumsum([len(group) for group in groups])
    distances = np.abs(cumulative - min(count, len(ordered)))
    nearest = np.flatnonzero(distances == np.min(distances))
    # On an exact distance tie, use the larger complete group.  This avoids an
    # optimistic lower-coverage comparator while still never splitting ties.
    chosen = int(nearest[-1])
    return [row for group in groups[: chosen + 1] for row in group]


def _risk(rows: Sequence[Mapping[str, Any]]) -> float:
    return float(np.mean([bool(row["invalid"]) for row in rows])) if rows else 1.0


def _decision_hash(rows: Sequence[Mapping[str, Any]], threshold: float) -> str:
    payload = [
        (
            str(row["case_id"]),
            bool(float(row["scores"]["full_contract"]) <= threshold),
        )
        for row in rows
    ]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _organization_summary(clean: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def correlation(values: Sequence[Mapping[str, Any]]) -> float:
        result = spearmanr(
            [float(row["organization_reference_mean_i2"]) for row in values],
            [float(row["diagnostics"]["median_coherence"]) for row in values],
        ).statistic
        return float(result) if np.isfinite(result) else 0.0

    return {
        "fields": len(clean),
        "pooled_spearman": correlation(clean),
        "per_specimen_spearman": {
            sample: correlation([row for row in clean if row["sample"] == sample])
            for sample in CONFIRMATION_SAMPLES
        },
        "per_specimen_zone_means": {
            sample: {
                zone: {
                    "fields": len(
                        [
                            row
                            for row in clean
                            if row["sample"] == sample and row["zone"] == zone
                        ]
                    ),
                    "nostos_median_coherence": float(
                        np.mean(
                            [
                                row["diagnostics"]["median_coherence"]
                                for row in clean
                                if row["sample"] == sample and row["zone"] == zone
                            ]
                        )
                    ),
                    "pshg_mean_i2": float(
                        np.mean(
                            [
                                row["organization_reference_mean_i2"]
                                for row in clean
                                if row["sample"] == sample and row["zone"] == zone
                            ]
                        )
                    ),
                }
                for zone in ZONES
            }
            for sample in CONFIRMATION_SAMPLES
        },
    }


def _specimen_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    by_sample = {
        sample: [row for row in rows if row["sample"] == sample]
        for sample in CONFIRMATION_SAMPLES
    }
    rng = np.random.default_rng(seed)
    full_risk: list[float] = []
    differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    aurc_differences = {name: [] for name in ("acquisition_qc", "endpoint_qc")}
    for _ in range(draws):
        sampled_ids = rng.integers(0, len(CONFIRMATION_SAMPLES), len(CONFIRMATION_SAMPLES))
        sampled: list[dict[str, Any]] = []
        for replicate, index in enumerate(sampled_ids):
            sample = CONFIRMATION_SAMPLES[int(index)]
            for row in by_sample[sample]:
                clone = dict(row)
                clone["case_id"] = f"bootstrap-{replicate}|{row['case_id']}"
                sampled.append(clone)
        selected = [
            row
            for row in sampled
            if float(row["scores"]["full_contract"]) <= threshold
        ]
        if not selected:
            continue
        full_value = _risk(selected)
        full_risk.append(full_value)
        full_aurc = risk_coverage_auc(
            [{**row, "_score": row["scores"]["full_contract"]} for row in sampled],
            score_key="_score",
        )
        for name in differences:
            comparator = _select_tied_nearest(
                [{**row, "_score": row["scores"][name]} for row in sampled],
                len(selected),
                score_key="_score",
            )
            differences[name].append(_risk(comparator) - full_value)
            comparator_aurc = risk_coverage_auc(
                [{**row, "_score": row["scores"][name]} for row in sampled],
                score_key="_score",
            )
            aurc_differences[name].append(comparator_aurc - full_aurc)

    def interval(values: Sequence[float]) -> list[float]:
        if not values:
            return [0.0, 1.0]
        return [float(value) for value in np.quantile(values, (0.025, 0.975))]

    return {
        "draws_requested": int(draws),
        "draws_retained": len(full_risk),
        "unit": "specimen with nested fields and conditions retained",
        "full_risk_95": interval(full_risk),
        "matched_risk_difference_95": {
            name: interval(values) for name, values in differences.items()
        },
        "aurc_difference_95": {
            name: interval(values) for name, values in aurc_differences.items()
        },
        "caution": "Only two independent specimens; intervals are descriptive and not population-generalization evidence.",
    }


def run_locked_confirmation(
    project_root: Path,
    dataset_root: Path,
    config_path: Path,
    prelock_path: Path,
    lock_path: Path,
    output: Path,
) -> dict[str, Any]:
    """Open the sealed confirmation specimens once and evaluate every frozen gate."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    prelock = json.loads(prelock_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    _verify_confirmation_lock(lock, project_root)
    source = _source_receipt(dataset_root, prelock)
    if source["status"] != "verified":
        raise ValueError("Confirmation source receipt failed before arrays were opened.")
    output.mkdir(parents=True, exist_ok=True)
    (output / "unseal_receipt.json").write_text(
        json.dumps(
            {
                "status": "confirmation_unsealed_after_lock_verification",
                "lock_sha256": _sha256(lock_path),
                "source_receipt": source,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = generate_confirmation_rows(dataset_root, config)
    threshold = float(config["operating_rule"]["maximum_full_contract_score"])
    full_selected = [
        row for row in rows if float(row["scores"]["full_contract"]) <= threshold
    ]
    target = len(full_selected)
    matched: dict[str, Any] = {}
    for name in ("acquisition_qc", "endpoint_qc"):
        augmented = [{**row, "_score": row["scores"][name]} for row in rows]
        selected = _select_tied_nearest(augmented, target, score_key="_score")
        matched[name] = {
            "accepted": len(selected),
            "coverage": float(len(selected) / len(rows)),
            "invalid": int(sum(bool(row["invalid"]) for row in selected)),
            "risk": _risk(selected),
            "score_threshold": float(max(row["_score"] for row in selected)),
        }
    matched["full_contract"] = {
        "accepted": target,
        "coverage": float(target / len(rows)),
        "invalid": int(sum(bool(row["invalid"]) for row in full_selected)),
        "risk": _risk(full_selected),
        "score_threshold": threshold,
    }
    operating = {
        "always_emit": {
            "accepted": len(rows),
            "coverage": 1.0,
            "invalid": int(sum(bool(row["invalid"]) for row in rows)),
            "risk": _risk(rows),
        },
        "full_contract": matched["full_contract"],
    }
    aurc = {}
    for name in POLICY_NAMES:
        augmented = [{**row, "_score": row["scores"][name]} for row in rows]
        aurc[name] = risk_coverage_auc(augmented, score_key="_score")
    per_specimen = {}
    for sample in CONFIRMATION_SAMPLES:
        subset = [row for row in rows if row["sample"] == sample]
        selected = [
            row
            for row in subset
            if float(row["scores"]["full_contract"]) <= threshold
        ]
        per_specimen[sample] = {
            "fields": len({row["field_id"] for row in subset}),
            "cases": len(subset),
            "accepted": len(selected),
            "coverage": float(len(selected) / len(subset)),
            "invalid": int(sum(bool(row["invalid"]) for row in selected)),
            "risk": _risk(selected),
        }

    clean = [row for row in rows if row["condition"] == "clean"]
    clean_selected = [
        row for row in clean if float(row["scores"]["full_contract"]) <= threshold
    ]
    organization = _organization_summary(clean)
    primary_clean = float(np.median([row["median_error_degrees"] for row in clean]))
    comparison_clean = float(
        np.median([row["comparison_median_error_degrees"] for row in clean])
    )
    gradient_clean = float(
        np.median([row["gradient_median_error_degrees"] for row in clean])
    )

    before = _decision_hash(rows, threshold)
    mutated = []
    for row in rows:
        clone = dict(row)
        clone["invalid"] = not bool(row["invalid"])
        clone["median_error_degrees"] = 90.0 - float(row["median_error_degrees"])
        clone["p75_error_degrees"] = 90.0 - float(row["p75_error_degrees"])
        clone["organization_reference_mean_i2"] = -float(
            row["organization_reference_mean_i2"]
        )
        mutated.append(clone)
    after = _decision_hash(mutated, threshold)
    label_blind = before == after

    risk_reductions = {
        name: float(matched[name]["risk"] - matched["full_contract"]["risk"])
        for name in ("acquisition_qc", "endpoint_qc")
    }
    aurc_differences = {
        name: float(aurc[name] - aurc["full_contract"])
        for name in ("acquisition_qc", "endpoint_qc")
    }
    ablation_increase = float(
        aurc["without_scale_consistency"] - aurc["full_contract"]
    )
    bootstrap = _specimen_bootstrap(
        rows,
        threshold=threshold,
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]),
    )
    rules = config["success_gates"]
    gates = {
        "confirmation_specimens_and_fields": len(
            {row["sample"] for row in rows}
        )
        == int(rules["confirmation_specimens"])
        and len({row["field_id"] for row in rows})
        >= int(rules["minimum_confirmation_fields"]),
        "invalid_cases_assessable": int(sum(bool(row["invalid"]) for row in rows))
        >= int(rules["minimum_invalid_cases"]),
        "full_coverage": matched["full_contract"]["coverage"]
        >= float(rules["minimum_full_coverage"]),
        "full_risk": matched["full_contract"]["risk"]
        <= float(rules["maximum_full_risk"]),
        "per_specimen_full_risk": all(
            item["risk"] <= float(rules["maximum_per_specimen_full_risk"])
            for item in per_specimen.values()
        ),
        "matched_risk_reduction_vs_acquisition_qc": risk_reductions[
            "acquisition_qc"
        ]
        >= float(rules["minimum_matched_risk_reduction_vs_acquisition_qc"]),
        "matched_risk_reduction_vs_endpoint_qc": risk_reductions["endpoint_qc"]
        >= float(rules["minimum_matched_risk_reduction_vs_endpoint_qc"]),
        "aurc_advantage": all(value > 0 for value in aurc_differences.values()),
        "scale_component_ablation": ablation_increase
        >= float(rules["minimum_ablation_aurc_increase"]),
        "clean_preservation": len(clean_selected) / len(clean)
        >= float(rules["minimum_clean_coverage"])
        and primary_clean <= float(rules["maximum_clean_median_error_degrees"]),
        "upstream_estimator_noninferiority": primary_clean
        <= comparison_clean + float(rules["upstream_noninferiority_margin_degrees"])
        and primary_clean
        <= gradient_clean + float(rules["upstream_noninferiority_margin_degrees"]),
        "organization_recovery": organization["pooled_spearman"]
        >= float(rules["minimum_pooled_organization_spearman"])
        and all(
            value >= float(rules["minimum_each_specimen_organization_spearman"])
            for value in organization["per_specimen_spearman"].values()
        ),
        "reference_label_blindness": label_blind,
        "source_and_lock_verification": source["status"] == "verified",
    }
    result = {
        "schema_version": "nostos.tlt_pshg_xrd.confirmation.v1",
        "status": "pass" if all(gates.values()) else "fail",
        "lock_sha256": _sha256(lock_path),
        "source_receipt": source,
        "summary": {
            "specimens": len({row["sample"] for row in rows}),
            "fields": len({row["field_id"] for row in rows}),
            "cases": len(rows),
            "invalid_cases": int(sum(bool(row["invalid"]) for row in rows)),
            "operating": operating,
            "matched_coverage": matched,
            "risk_reductions": risk_reductions,
            "risk_coverage_auc": aurc,
            "aurc_differences": aurc_differences,
            "scale_ablation_aurc_increase": ablation_increase,
            "per_specimen": per_specimen,
            "clean": {
                "eligible": len(clean),
                "accepted": len(clean_selected),
                "coverage": float(len(clean_selected) / len(clean)),
                "primary_median_field_error_degrees": primary_clean,
                "comparison_median_field_error_degrees": comparison_clean,
                "gradient_median_field_error_degrees": gradient_clean,
            },
            "organization": organization,
        },
        "bootstrap": bootstrap,
        "label_blindness_audit": {
            "before_sha256": before,
            "after_reference_mutation_sha256": after,
            "unchanged": label_blind,
        },
        "success_gates": gates,
        "claim_boundary": config["claim_boundary"],
    }
    (output / "source_receipt.json").write_text(
        json.dumps(source, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output / "confirmation_rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output / "confirmation.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result
