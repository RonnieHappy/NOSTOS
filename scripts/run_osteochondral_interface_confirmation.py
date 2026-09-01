from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.stats import spearmanr

import nostos.validation.osteochondral_interface as interface_module
from nostos.validation.osteochondral_interface import (
    InterfaceParameters,
    band_iou,
    band_measurements,
    boundary_metrics,
    concordance_correlation,
    estimate_interface,
    mask_from_interface,
    reference_interface,
    threshold_comparator,
)


CONFIRMATION_PATIENTS = {"21", "22", "14", "25", "24", "O17", "32", "15", "31", "20"}
INDICES = tuple(range(16, 433, 32))
SPACING_UM = 3.2
PROTOCOL_SHA256 = "D23D930FA6EE30A106ECA24DAD3DDA7856BF733E0A28E849B9D2628A3A1C1FC5"
BOOTSTRAP_SEED = 8_262_602


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def patient_id(sample_id: str) -> str:
    return sample_id.split("_", 1)[0]


def interpolate_path(path: np.ndarray) -> np.ndarray:
    values = np.asarray(path, dtype=float)
    finite = np.isfinite(values)
    if finite.sum() < 2:
        raise ValueError("Interface has fewer than two valid columns.")
    columns = np.arange(len(values))
    return np.interp(columns, columns[finite], values[finite])


def load_records(root: Path) -> list[dict]:
    records: list[dict] = []
    for sample in sorted(path for path in root.iterdir() if path.is_dir()):
        patient = patient_id(sample.name)
        if patient not in CONFIRMATION_PATIENTS:
            continue
        for family, index in itertools.product(("ZX", "ZY"), INDICES):
            image_path = sample / "imgs" / f"{family}_{index}.png"
            mask_path = sample / "masks" / f"{family}_{index}.png"
            if not image_path.is_file() or not mask_path.is_file():
                continue
            with Image.open(image_path) as opened:
                image = np.asarray(opened).copy()
            with Image.open(mask_path) as opened:
                mask = np.asarray(opened).copy() > 0
            reference = reference_interface(mask)
            if int(np.isfinite(reference).sum()) < 128:
                continue
            records.append({"patient": patient, "sample": sample.name, "family": family,
                            "index": index, "image": image, "mask": mask, "reference": reference})
    return records


def collapse(rows: list[dict], key: str) -> dict[str, float]:
    samples: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        samples.setdefault((row["patient"], row["sample"]), []).append(float(row[key]))
    patients: dict[str, list[float]] = {}
    for (patient, _), values in samples.items():
        patients.setdefault(patient, []).append(float(np.median(values)))
    return {patient: float(np.median(values)) for patient, values in patients.items()}


def bootstrap_interval(values: dict[str, float], *, draws: int = 10_000) -> list[float]:
    array = np.asarray([values[key] for key in sorted(values)], dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = np.median(array[rng.integers(0, len(array), size=(draws, len(array)))], axis=1)
    return [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def paired_difference_interval(a: dict[str, float], b: dict[str, float]) -> tuple[float, list[float]]:
    keys = sorted(set(a) & set(b))
    differences = np.asarray([a[key] - b[key] for key in keys], dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = np.median(differences[rng.integers(0, len(differences), size=(10_000, len(differences)))], axis=1)
    return float(np.median(differences)), [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def dice(prediction: np.ndarray, target: np.ndarray) -> float:
    intersection = np.logical_and(prediction, target).sum()
    return float(2 * intersection / max(prediction.sum() + target.sum(), 1))


FEATURE_NAMES = (
    "normalized_mean_intensity", "normalized_intensity_sd", "angular_spectral_entropy",
    "tensor_coherency_12_8_um", "tensor_coherency_25_6_um", "variogram_anisotropy_25_6_um",
)


def safe_band_measurements(image: np.ndarray, path: np.ndarray) -> tuple[dict[str, float | None], str | None]:
    try:
        return band_measurements(image, path, spacing_um=SPACING_UM), None
    except ValueError as error:
        return {name: None for name in FEATURE_NAMES}, str(error)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--development-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    development = json.loads(args.development_receipt.read_text(encoding="utf-8"))
    if development["protocol_sha256"] != PROTOCOL_SHA256:
        raise SystemExit("Protocol hash mismatch; confirmation remains locked.")
    if development["implementation"]["module_sha256"] != sha256(Path(interface_module.__file__)):
        raise SystemExit("Estimator module changed after development; confirmation remains locked.")
    if development["archive"]["sha256"] != sha256(args.archive):
        raise SystemExit("Archive hash mismatch; confirmation remains locked.")
    parameters = InterfaceParameters(**development["selected_parameters"])
    threshold = development["selected_confidence_threshold"]
    records = load_records(args.dataset)
    rows: list[dict] = []
    for record in records:
        prediction, confidence = estimate_interface(record["image"], parameters)
        accepted = threshold is None or confidence >= float(threshold)
        if not accepted:
            continue
        metrics = boundary_metrics(prediction, record["reference"], spacing_um=SPACING_UM)
        reference_filled = interpolate_path(record["reference"])
        predicted_mask = mask_from_interface(prediction, record["image"].shape[0])
        baseline = threshold_comparator(record["image"])
        baseline_error: float | None = None
        if np.isfinite(baseline).sum() >= 128:
            baseline_error = boundary_metrics(baseline, record["reference"], spacing_um=SPACING_UM)["median_absolute_error_um"]
        reference_measurements, reference_abstention = safe_band_measurements(record["image"], reference_filled)
        predicted_measurements, predicted_abstention = safe_band_measurements(record["image"], prediction)
        row = {
            "patient": record["patient"], "sample": record["sample"], "family": record["family"],
            "index": record["index"], "confidence": confidence, **metrics,
            "band_iou_75_um": band_iou(prediction, record["reference"], spacing_um=SPACING_UM),
            "full_mask_dice": dice(predicted_mask, record["mask"]),
            "comparator_error_um": baseline_error,
            "reference_measurements": reference_measurements,
            "predicted_measurements": predicted_measurements,
            "reference_measurement_abstention": reference_abstention,
            "predicted_measurement_abstention": predicted_abstention,
        }
        rows.append(row)

    patient_mae = collapse(rows, "median_absolute_error_um")
    patient_p90 = collapse(rows, "p90_absolute_error_um")
    patient_within30 = collapse(rows, "within_30_um")
    patient_iou = collapse(rows, "band_iou_75_um")
    patient_dice = collapse(rows, "full_mask_dice")
    comparator_rows = [row for row in rows if row["comparator_error_um"] is not None]
    patient_comparator = collapse(comparator_rows, "comparator_error_um")
    difference, difference_interval = paired_difference_interval(patient_mae, patient_comparator)

    sample_features: dict[str, dict[str, list[dict[str, float]]]] = {}
    for row in rows:
        sample_features.setdefault(row["sample"], {"reference": [], "predicted": []})
        sample_features[row["sample"]]["reference"].append(row["reference_measurements"])
        sample_features[row["sample"]]["predicted"].append(row["predicted_measurements"])
    feature_names = list(FEATURE_NAMES)
    agreement: dict[str, dict[str, float | int | None]] = {}
    standardized_errors: list[float] = []
    for feature in feature_names:
        reference_values, predicted_values = [], []
        for sample in sorted(sample_features):
            pairs = [
                (reference_item[feature], predicted_item[feature])
                for reference_item, predicted_item in zip(
                    sample_features[sample]["reference"], sample_features[sample]["predicted"], strict=True
                )
                if reference_item[feature] is not None and predicted_item[feature] is not None
            ]
            if pairs:
                reference_values.append(float(np.mean([pair[0] for pair in pairs])))
                predicted_values.append(float(np.mean([pair[1] for pair in pairs])))
        reference_array = np.asarray(reference_values)
        predicted_array = np.asarray(predicted_values)
        if reference_array.size < 3:
            agreement[feature] = {"eligible_samples": int(reference_array.size), "concordance_correlation": None,
                                  "spearman": None, "median_standardized_absolute_error": None}
            continue
        scale = max(float(np.std(reference_array, ddof=1)), np.finfo(float).eps)
        standardized = np.abs(predicted_array - reference_array) / scale
        standardized_errors.extend(standardized.tolist())
        agreement[feature] = {
            "eligible_samples": int(reference_array.size),
            "concordance_correlation": concordance_correlation(reference_array, predicted_array),
            "spearman": float(spearmanr(reference_array, predicted_array).statistic),
            "median_standardized_absolute_error": float(np.median(standardized)),
        }

    patient_count = len(patient_mae)
    sample_count = len({row["sample"] for row in rows})
    eligible_count = len(records)
    coverage = len(rows) / max(eligible_count, 1)
    median_mae = float(np.median(list(patient_mae.values())))
    mae_interval = bootstrap_interval(patient_mae)
    median_p90 = float(np.median(list(patient_p90.values())))
    median_within30 = float(np.median(list(patient_within30.values())))
    median_iou = float(np.median(list(patient_iou.values())))
    concordant_count = sum(
        item["concordance_correlation"] is not None and item["concordance_correlation"] >= 0.85
        for item in agreement.values()
    )
    median_standardized_error = float(np.median(standardized_errors)) if standardized_errors else None
    gates = {
        "ten_patients_and_eighteen_samples": patient_count == 10 and sample_count >= 18,
        "four_hundred_slices": eligible_count >= 400,
        "coverage": coverage >= (0.80 if threshold is not None else 1.0),
        "median_mae_30_um": median_mae <= 30.0,
        "bootstrap_upper_45_um": mae_interval[1] <= 45.0,
        "p90_75_um": median_p90 <= 75.0,
        "within_30_um_70_percent": median_within30 >= 0.70,
        "band_iou_0_80": median_iou >= 0.80,
        "comparator_noninferiority_and_superiority_point": difference_interval[1] <= 3.2 and difference <= 0.0,
        "downstream_agreement": concordant_count >= 4 and median_standardized_error is not None and median_standardized_error <= 0.20,
    }
    payload = {
        "protocol_version": "nostos-osteochondral-interface-confirmation/1.0",
        "status": "pass" if all(gates.values()) else "fail",
        "protocol_sha256": PROTOCOL_SHA256,
        "archive": development["archive"],
        "implementation": development["implementation"],
        "partition": {"patients": sorted(CONFIRMATION_PATIENTS), "patient_count": patient_count,
                      "sample_count": sample_count},
        "parameters": development["selected_parameters"],
        "confidence_threshold": threshold,
        "eligible_slices": eligible_count, "accepted_slices": len(rows), "coverage": coverage,
        "primary": {"patient_median_mae_um": median_mae, "patient_bootstrap_95_interval_um": mae_interval,
                    "patient_values_um": patient_mae},
        "secondary": {"patient_median_p90_um": median_p90, "patient_median_within_30_um": median_within30,
                      "patient_median_band_iou_75_um": median_iou,
                      "patient_median_full_mask_dice": float(np.median(list(patient_dice.values())))},
        "comparator": {"paired_median_difference_um": difference, "bootstrap_95_interval_um": difference_interval,
                       "patient_values_um": patient_comparator},
        "downstream_measurement_agreement": agreement,
        "downstream_concordant_features": concordant_count,
        "downstream_median_standardized_absolute_error": median_standardized_error,
        "measurement_abstentions": {
            "reference": sum(row["reference_measurement_abstention"] is not None for row in rows),
            "predicted": sum(row["predicted_measurement_abstention"] is not None for row in rows),
        },
        "gates": gates,
        "scope": "One training-free PTA micro-CT interface adapter and downstream measurement agreement; not Safranin-O mask, OA diagnosis or clinical validation.",
        "slice_results": rows,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "osteochondral_interface_confirmation.json"
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), "status": payload["status"], "gates": gates}, indent=2))


if __name__ == "__main__":
    main()
