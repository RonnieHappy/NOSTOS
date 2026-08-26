"""Frozen scale-declared local orientation validation on annotated SHG test images."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from nostos.validation.local_orientation import _axial_errors, _reference_tangents, _tensor_fields
from nostos.validation.selective_shg_transfer import _index, _load


PROTOCOL_SHA256 = "1e3c6b19ea8513a0c9d1604354e48fc704dabb7ffdaf215992d245e712b8ac98"
DATASET_DOI = "10.5281/zenodo.7243211"


def _bootstrap_median(group_errors: list[np.ndarray], draws: int = 10000, seed: int = 7243214) -> list[float]:
    sorted_groups = [np.sort(np.asarray(values, dtype=float)) for values in group_errors]
    candidates = np.sort(np.concatenate(sorted_groups))
    sizes = np.asarray([len(values) for values in sorted_groups], dtype=int)
    rng = np.random.default_rng(seed)
    estimates = np.empty(draws, dtype=float)
    for draw in range(draws):
        multiplicity = np.bincount(rng.integers(0, len(sorted_groups), len(sorted_groups)), minlength=len(sorted_groups))
        target = (int(np.dot(multiplicity, sizes)) - 1) // 2
        low, high = 0, len(candidates) - 1
        while low < high:
            middle = (low + high) // 2
            count = sum(int(mult) * int(np.searchsorted(values, candidates[middle], side="right"))
                        for mult, values in zip(multiplicity, sorted_groups, strict=True) if mult)
            if count > target:
                high = middle
            else:
                low = middle + 1
        estimates[draw] = candidates[low]
    return [float(value) for value in np.quantile(estimates, (0.025, 0.975))]


def _summarize(group_errors: dict[str, list[np.ndarray]], *, bootstrap: bool = False) -> dict:
    merged_by_group = [np.concatenate(values) for _, values in sorted(group_errors.items())]
    pooled = np.concatenate(merged_by_group)
    summary = {
        "eligible_groups": len(merged_by_group), "eligible_pixels": len(pooled),
        "median_error": float(np.median(pooled)), "p75_error": float(np.percentile(pooled, 75)),
        "median_group_median_error": float(np.median([np.median(values) for values in merged_by_group])),
        "axial_alignment": float(np.mean(np.cos(2 * np.radians(pooled)))),
    }
    if bootstrap:
        summary["median_error_group_bootstrap95"] = _bootstrap_median(merged_by_group)
    return summary


def run_external_test(dataset_root: Path, output: Path) -> dict:
    test_root = dataset_root / "final_train_test" / "test"
    identifiers = _index(test_root)
    errors = {"nostos_sigma2": {}, "sigma4": {}, "smoothed_gradient": {}}
    cases = []
    for number in sorted(identifiers, key=int):
        image_path = test_root / "images" / f"{number}.png"
        label_path = test_root / "labels" / f"{number}.png"
        image, label = _load(image_path), _load(label_path, nearest=True)
        coordinates, reference, _ = _reference_tangents(label)
        group = identifiers[number].rsplit("_", 1)[0]
        cases.append({"patch": int(number), "identifier": identifiers[number], "source_group": group,
                      "eligible_pixels": int(len(reference)),
                      "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                      "label_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest()})
        if not len(reference):
            continue
        angles, _, _ = _tensor_fields(image)
        yy, xx = coordinates[:, 0], coordinates[:, 1]
        smoothed = ndimage.gaussian_filter(image, sigma=2.0, mode="reflect")
        gy, gx = np.gradient(smoothed)
        gradient_angle = np.degrees(np.mod(np.arctan2(gy[yy, xx], gx[yy, xx]) + np.pi / 2, np.pi))
        values = {"nostos_sigma2": _axial_errors(angles[1, yy, xx], reference),
                  "sigma4": _axial_errors(angles[2, yy, xx], reference),
                  "smoothed_gradient": _axial_errors(gradient_angle, reference)}
        for name, measurement in values.items():
            errors[name].setdefault(group, []).append(measurement)
    primary = _summarize(errors["nostos_sigma2"], bootstrap=True)
    comparators = {name: _summarize(values) for name, values in errors.items() if name != "nostos_sigma2"}
    gates = {
        "eligible_groups_ge_100_and_pixels_ge_15000": primary["eligible_groups"] >= 100 and primary["eligible_pixels"] >= 15000,
        "median_error_le_10_degrees": primary["median_error"] <= 10.0,
        "bootstrap_upper_median_error_le_12_degrees": primary["median_error_group_bootstrap95"][1] <= 12.0,
        "median_group_median_error_le_12_degrees": primary["median_group_median_error"] <= 12.0,
        "p75_error_le_20_degrees": primary["p75_error"] <= 20.0,
        "axial_alignment_ge_0.75": primary["axial_alignment"] >= 0.75,
        "noninferior_to_sigma4_within_1_degree": primary["median_error"] <= comparators["sigma4"]["median_error"] + 1.0,
        "noninferior_to_smoothed_gradient_within_1_degree": primary["median_error"] <= comparators["smoothed_gradient"]["median_error"] + 1.0,
    }
    payload = {"protocol_version": "nostos-local-orientation-external-test/1.0",
               "protocol_sha256": PROTOCOL_SHA256,
               "dataset": {"doi": DATASET_DOI, "split": "official test; previously opened for a distinct global endpoint"},
               "status": "pass" if all(gates.values()) else "fail", "primary": primary,
               "comparators": comparators, "success_gates": gates,
               "scope": "Endpoint-new external-test validation of scale-declared local 2D orientation against manual-centerline geometry.",
               "cases": cases}
    output.mkdir(parents=True, exist_ok=True)
    (output / "local_orientation_external_test.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
