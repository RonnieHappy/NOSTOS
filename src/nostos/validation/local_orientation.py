"""Group-separated validation of local orientation along annotated SHG centerlines."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.selective_shg_transfer import _index, _load
from nostos.validation.consensus_reliability import _partition


PROTOCOL_SHA256 = "cbd701c1d9d602f0a1a9b62c0611c579bb0d6903f6f9a7e012518114f13b9cf6"
SCALES = (1.0, 2.0, 4.0, 8.0)


def _skeletonize(binary: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning without an optional image-processing dependency."""
    image = np.pad(np.asarray(binary, dtype=bool), 1)
    changed = True
    while changed:
        changed = False
        for first in (True, False):
            p2 = np.roll(image, 1, 0); p3 = np.roll(p2, -1, 1); p4 = np.roll(image, -1, 1)
            p5 = np.roll(np.roll(image, -1, 0), -1, 1); p6 = np.roll(image, -1, 0)
            p7 = np.roll(p6, 1, 1); p8 = np.roll(image, 1, 1); p9 = np.roll(p2, 1, 1)
            neighbors = p2.astype(int) + p3 + p4 + p5 + p6 + p7 + p8 + p9
            sequence = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            transitions = sum((~a) & b for a, b in zip(sequence[:-1], sequence[1:], strict=True))
            if first:
                constraint = ~(p2 & p4 & p6) & ~(p4 & p6 & p8)
            else:
                constraint = ~(p2 & p4 & p8) & ~(p2 & p6 & p8)
            remove = image & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1) & constraint
            remove[[0, -1], :] = False; remove[:, [0, -1]] = False
            if np.any(remove):
                image[remove] = False; changed = True
    return image[1:-1, 1:-1]


def _tensor_fields(image: np.ndarray, scales: tuple[float, ...] = SCALES) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gy, gx = np.gradient(np.asarray(image, dtype=float))
    angles, coherences, energies = [], [], []
    eps = np.finfo(float).eps
    for sigma in scales:
        jxx = ndimage.gaussian_filter(gx * gx, sigma=sigma, mode="reflect")
        jyy = ndimage.gaussian_filter(gy * gy, sigma=sigma, mode="reflect")
        jxy = ndimage.gaussian_filter(gx * gy, sigma=sigma, mode="reflect")
        delta = np.sqrt((jxx - jyy) ** 2 + 4 * jxy**2)
        energy = jxx + jyy
        angle = np.mod(0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2, np.pi)
        angles.append(np.degrees(angle)); coherences.append(delta / np.maximum(energy, eps)); energies.append(energy)
    return np.stack(angles), np.stack(coherences), np.stack(energies)


def _reference_tangents(label: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    skeleton = _skeletonize(label)
    coordinates = np.argwhere(skeleton)
    if not len(coordinates):
        return np.empty((0, 2), int), np.empty(0), np.empty(0)
    tree = cKDTree(coordinates)
    retained, angles, anisotropies = [], [], []
    for index, coordinate in enumerate(coordinates):
        if np.any(coordinate < 6) or np.any(coordinate >= np.asarray(label.shape) - 6):
            continue
        neighbors = coordinates[tree.query_ball_point(coordinate, r=5.0)]
        if len(neighbors) < 5:
            continue
        covariance = np.cov(neighbors.astype(float).T, bias=True)
        values, vectors = np.linalg.eigh(covariance)
        anisotropy = float((values[-1] - values[0]) / max(values.sum(), np.finfo(float).eps))
        if anisotropy < 0.70:
            continue
        vector = vectors[:, -1]
        # Coordinates are (y, x); angle is expressed from +x toward +y.
        angle = float(np.degrees(np.arctan2(vector[0], vector[1])) % 180)
        retained.append(coordinate); angles.append(angle); anisotropies.append(anisotropy)
    return np.asarray(retained, int), np.asarray(angles), np.asarray(anisotropies)


def _axial_errors(measured: np.ndarray, reference: np.ndarray) -> np.ndarray:
    difference = np.abs(measured - reference) % 180.0
    return np.minimum(difference, 180.0 - difference)


def _case_measurements(image: np.ndarray, label: np.ndarray) -> dict[str, np.ndarray]:
    coordinates, reference, reference_anisotropy = _reference_tangents(label)
    if not len(coordinates):
        empty = np.empty(0)
        return {"reference": empty, "reference_anisotropy": empty, "confidence": empty,
                "nostos_error": empty, "sigma2_error": empty, "sigma4_error": empty}
    angles, coherence, energy = _tensor_fields(image)
    yy, xx = coordinates[:, 0], coordinates[:, 1]
    local_angles = angles[:, yy, xx]
    local_coherence = coherence[:, yy, xx]
    local_energy = energy[:, yy, xx]
    medians = np.maximum(np.median(energy.reshape(len(SCALES), -1), axis=1), np.finfo(float).eps)
    selection_score = local_coherence * np.sqrt(local_energy / medians[:, None])
    selected = np.argmax(selection_score, axis=0)
    columns = np.arange(len(coordinates))
    selected_angle = local_angles[selected, columns]
    selected_coherence = local_coherence[selected, columns]
    maximum_energy = np.max(local_energy, axis=0)
    supported = local_energy >= 0.25 * maximum_energy
    spread = np.zeros(len(coordinates), dtype=float)
    for column in columns:
        values = local_angles[supported[:, column], column]
        spread[column] = max(
            (axial_angular_error_degrees(float(a), float(b)) for i, a in enumerate(values) for b in values[i + 1:]),
            default=0.0,
        )
    confidence = selected_coherence * np.exp(-spread / 20.0)
    return {
        "reference": reference, "reference_anisotropy": reference_anisotropy,
        "confidence": confidence, "nostos_error": _axial_errors(selected_angle, reference),
        "sigma2_error": _axial_errors(local_angles[1], reference),
        "sigma4_error": _axial_errors(local_angles[2], reference),
        "sigma2_coherence": local_coherence[1], "sigma4_coherence": local_coherence[2],
    }


def _select_threshold(confidence: np.ndarray, errors: np.ndarray) -> dict | None:
    order = np.argsort(confidence)[::-1]
    invalid = (errors[order] > 10.0).astype(int)
    cumulative_risk = np.cumsum(invalid) / np.arange(1, len(order) + 1)
    coverage = np.arange(1, len(order) + 1) / len(order)
    eligible = np.where((coverage >= 0.40) & (cumulative_risk <= 0.10))[0]
    if not len(eligible):
        return None
    index = int(eligible[-1])
    return {"threshold": float(confidence[order[index]]), "coverage": float(coverage[index]),
            "risk": float(cumulative_risk[index]), "accepted": index + 1}


def _group_bootstrap(groups: list[dict], *, draws: int = 10000) -> list[float]:
    rng = np.random.default_rng(7243213)
    invalid = np.asarray([row["accepted_invalid"] for row in groups], dtype=float)
    accepted = np.asarray([row["accepted_pixels"] for row in groups], dtype=float)
    estimates = []
    for _ in range(draws):
        indices = rng.integers(0, len(groups), len(groups))
        denominator = accepted[indices].sum()
        if denominator:
            estimates.append(float(invalid[indices].sum() / denominator))
    return [float(value) for value in np.quantile(estimates, (0.025, 0.975))] if estimates else [0.0, 1.0]


def run_validation(dataset_root: Path, output: Path) -> dict:
    train_root = dataset_root / "final_train_test" / "train"
    identifiers = _index(train_root)
    cases, arrays = [], []
    for number in sorted(identifiers, key=int):
        image_path = train_root / "images" / f"{number}.png"
        label_path = train_root / "labels" / f"{number}.png"
        image, label = _load(image_path), _load(label_path, nearest=True)
        measured = _case_measurements(image, label)
        group = identifiers[number].rsplit("_", 1)[0]
        cases.append({"patch": int(number), "identifier": identifiers[number], "source_group": group,
                      "partition": _partition(group), "eligible_pixels": int(len(measured["reference"])),
                      "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                      "label_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest()})
        arrays.append(measured)
    development_indices = [i for i, row in enumerate(cases) if row["partition"] == "development" and row["eligible_pixels"]]
    confirmation_indices = [i for i, row in enumerate(cases) if row["partition"] == "confirmation" and row["eligible_pixels"]]
    development_confidence = np.concatenate([arrays[i]["confidence"] for i in development_indices])
    development_error = np.concatenate([arrays[i]["nostos_error"] for i in development_indices])
    development_groups = len({cases[i]["source_group"] for i in development_indices})
    selection = _select_threshold(development_confidence, development_error) if development_groups >= 100 else None
    threshold = selection["threshold"] if selection else np.inf
    group_values: dict[str, dict] = {}
    confirmation_errors, confirmation_confidence = [], []
    comparator = {"sigma2": {"errors": [], "confidence": []}, "sigma4": {"errors": [], "confidence": []}}
    for index in confirmation_indices:
        row, values = cases[index], arrays[index]
        accepted = values["confidence"] >= threshold
        errors = values["nostos_error"]
        bucket = group_values.setdefault(row["source_group"], {"eligible_pixels": 0, "accepted_pixels": 0,
                                                                 "accepted_invalid": 0, "accepted_errors": []})
        bucket["eligible_pixels"] += len(errors); bucket["accepted_pixels"] += int(accepted.sum())
        bucket["accepted_invalid"] += int(np.sum(errors[accepted] > 10.0)); bucket["accepted_errors"].extend(errors[accepted].tolist())
        confirmation_errors.append(errors); confirmation_confidence.append(values["confidence"])
        for name in ("sigma2", "sigma4"):
            comparator[name]["errors"].append(values[f"{name}_error"])
            comparator[name]["confidence"].append(values[f"{name}_coherence"])
    all_errors = np.concatenate(confirmation_errors) if confirmation_errors else np.empty(0)
    all_confidence = np.concatenate(confirmation_confidence) if confirmation_confidence else np.empty(0)
    accepted = all_confidence >= threshold
    accepted_errors = all_errors[accepted]
    group_rows = []
    for group, values in sorted(group_values.items()):
        group_rows.append({"source_group": group, "eligible_pixels": values["eligible_pixels"],
                           "accepted_pixels": values["accepted_pixels"], "accepted_invalid": values["accepted_invalid"],
                           "accepted_median_error": float(np.median(values["accepted_errors"])) if values["accepted_errors"] else None})
    coverage = float(accepted.mean()) if len(accepted) else 0.0
    risk = float(np.mean(accepted_errors > 10.0)) if len(accepted_errors) else 1.0
    comparator_results = {}
    for name, values in comparator.items():
        errors = np.concatenate(values["errors"]); confidence = np.concatenate(values["confidence"])
        count = int(round(coverage * len(errors)))
        selected = np.argsort(confidence)[::-1][:count] if count else np.empty(0, int)
        comparator_results[name] = {"unconditional_median_error": float(np.median(errors)),
                                    "matched_coverage": count / len(errors) if len(errors) else 0.0,
                                    "matched_median_error": float(np.median(errors[selected])) if count else None,
                                    "matched_invalid_risk": float(np.mean(errors[selected] > 10.0)) if count else None}
    median_error = float(np.median(accepted_errors)) if len(accepted_errors) else None
    group_medians = [row["accepted_median_error"] for row in group_rows if row["accepted_median_error"] is not None]
    best_comparator = min((value["matched_median_error"] for value in comparator_results.values() if value["matched_median_error"] is not None), default=np.inf)
    interval = _group_bootstrap(group_rows)
    gates = {
        "eligible_groups_ge_100_and_pixels_ge_10000": len(group_rows) >= 100 and len(all_errors) >= 10000,
        "coverage_ge_0.40": coverage >= 0.40,
        "group_bootstrap_risk_upper_le_0.15": interval[1] <= 0.15,
        "accepted_median_error_le_5_degrees": median_error is not None and median_error <= 5.0,
        "median_group_median_error_le_7.5_degrees": bool(group_medians) and float(np.median(group_medians)) <= 7.5,
        "noninferior_to_best_fixed_scale_within_1_degree": median_error is not None and median_error <= best_comparator + 1.0,
    }
    payload = {"protocol_version": "nostos-local-orientation/1.0", "protocol_sha256": PROTOCOL_SHA256,
               "status": "pass" if selection is not None and all(gates.values()) else "fail",
               "development": {"eligible_groups": development_groups, "eligible_pixels": len(development_error),
                               "selection": selection, "unconditional_median_error": float(np.median(development_error)),
                               "unconditional_invalid_risk": float(np.mean(development_error > 10.0))},
               "confirmation": {"eligible_groups": len(group_rows), "eligible_pixels": len(all_errors),
                                "accepted_pixels": len(accepted_errors), "coverage": coverage, "invalid_risk": risk,
                                "risk_group_bootstrap95": interval, "accepted_median_error": median_error,
                                "median_group_median_error": float(np.median(group_medians)) if group_medians else None,
                                "comparators": comparator_results},
               "success_gates": gates,
               "scope": "Same-archive local SHG orientation validation against manual-centerline geometry; not independent acquisition.",
               "cases": cases, "confirmation_groups": group_rows}
    output.mkdir(parents=True, exist_ok=True)
    (output / "local_orientation_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload
