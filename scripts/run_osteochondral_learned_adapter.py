from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from scipy.stats import spearmanr
from torch.utils.data import DataLoader

import nostos.segmentation.osteochondral as learned_module
from nostos.segmentation.osteochondral import (
    OsteochondralSliceDataset,
    OsteochondralUNet,
    SliceRecord,
    binary_segmentation_loss,
    load_pair,
    postprocess_probability,
)
from nostos.validation.osteochondral_interface import (
    InterfaceParameters,
    band_iou,
    band_measurements,
    boundary_metrics,
    concordance_correlation,
    estimate_interface,
    reference_interface,
    threshold_comparator,
)

SEED = 8_262_603
SPACING_UM = 6.4
INDICES = tuple(range(8, 441, 16))
FAMILIES = ("ZX", "ZY")
FEATURES = (
    "normalized_mean_intensity", "normalized_intensity_sd", "angular_spectral_entropy",
    "tensor_coherency_12_8_um", "tensor_coherency_25_6_um", "variogram_anisotropy_25_6_um",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def patient_id(sample: str) -> str:
    return sample.split("_", 1)[0]


def patient_folds(patients: list[str]) -> list[list[str]]:
    ordered = sorted(patients, key=lambda value: hashlib.sha256(value.encode()).hexdigest())
    return [ordered[index::5] for index in range(5)]


def discover(root: Path) -> list[SliceRecord]:
    records: list[SliceRecord] = []
    for sample in sorted(path for path in root.iterdir() if path.is_dir()):
        for family, index in itertools.product(FAMILIES, INDICES):
            image = sample / "imgs" / f"{family}_{index}.png"
            mask = sample / "masks" / f"{family}_{index}.png"
            if image.is_file() and mask.is_file():
                records.append(SliceRecord(patient_id(sample.name), sample.name, family, index, image, mask))
    return records


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)


def train_fold(train: list[SliceRecord], validation: list[SliceRecord], output: Path, fold: int,
               *, epochs: int, batch_size: int, workers: int) -> tuple[OsteochondralUNet, dict]:
    seed_all(SEED + fold)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = OsteochondralUNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    train_data = OsteochondralSliceDataset(train, augment=True, seed=SEED + fold * 100)
    validation_data = OsteochondralSliceDataset(validation, augment=False, seed=SEED)
    generator = torch.Generator().manual_seed(SEED + fold)
    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True, num_workers=workers,
                              pin_memory=device.type == "cuda", generator=generator)
    validation_loader = DataLoader(validation_data, batch_size=batch_size, shuffle=False, num_workers=workers,
                                   pin_memory=device.type == "cuda")
    best, stale, history = float("inf"), 0, []
    checkpoint = output / f"fold_{fold}.pt"
    for epoch in range(epochs):
        train_data.set_epoch(epoch); model.train(); losses = []
        for image, mask in train_loader:
            image, mask = image.to(device, non_blocking=True), mask.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                loss = binary_segmentation_loss(model(image), mask)
            scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()
            losses.append(float(loss.detach()))
        model.eval(); validation_losses = []
        with torch.inference_mode():
            for image, mask in validation_loader:
                image, mask = image.to(device, non_blocking=True), mask.to(device, non_blocking=True)
                validation_losses.append(float(binary_segmentation_loss(model(image), mask)))
        value = float(np.mean(validation_losses))
        history.append({"epoch": epoch + 1, "train_loss": float(np.mean(losses)), "validation_loss": value})
        if value < best - 1e-5:
            best, stale = value, 0
            torch.save({"state_dict": model.state_dict(), "epoch": epoch + 1, "validation_loss": best}, checkpoint)
        else:
            stale += 1
        print(json.dumps({"fold": fold, **history[-1], "stale": stale}), flush=True)
        if stale >= 6:
            break
    saved = torch.load(checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(saved["state_dict"]); model.eval()
    return model, {"history": history, "selected_epoch": saved["epoch"], "best_validation_loss": saved["validation_loss"]}


def load_checkpoint(output: Path, fold: int) -> OsteochondralUNet:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    saved = torch.load(output / f"fold_{fold}.pt", map_location=device, weights_only=True)
    model = OsteochondralUNet().to(device)
    model.load_state_dict(saved["state_dict"]); model.eval()
    return model


def interpolate(path: np.ndarray) -> np.ndarray:
    finite = np.isfinite(path); columns = np.arange(path.size)
    if finite.sum() < 2:
        raise ValueError("fewer than two reference columns")
    return np.interp(columns, columns[finite], path[finite])


def collapse(rows: list[dict], key: str) -> dict[str, float]:
    samples: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        value = row.get(key)
        if value is not None and np.isfinite(value):
            samples.setdefault((row["patient"], row["sample"]), []).append(float(value))
    patients: dict[str, list[float]] = {}
    for (patient, _), values in samples.items():
        patients.setdefault(patient, []).append(float(np.median(values)))
    return {patient: float(np.median(values)) for patient, values in patients.items()}


def interval(values: dict[str, float]) -> list[float]:
    data = np.asarray([values[key] for key in sorted(values)])
    rng = np.random.default_rng(SEED)
    draws = np.median(data[rng.integers(0, len(data), (10_000, len(data)))], axis=1)
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


def paired_interval(a: dict[str, float], b: dict[str, float]) -> dict:
    keys = sorted(set(a) & set(b)); differences = np.asarray([a[k] - b[k] for k in keys])
    rng = np.random.default_rng(SEED)
    draws = np.median(differences[rng.integers(0, len(keys), (10_000, len(keys)))], axis=1)
    return {"median_difference_um": float(np.median(differences)),
            "bootstrap_95_interval_um": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]}


def comparator_error(path: np.ndarray, truth: np.ndarray) -> float | None:
    try:
        return float(boundary_metrics(path, truth, spacing_um=SPACING_UM)["median_absolute_error_um"])
    except ValueError:
        return None


def safe_measurements(image: np.ndarray, path: np.ndarray) -> tuple[dict[str, float | None], str | None]:
    try:
        return band_measurements(image, path, spacing_um=SPACING_UM), None
    except ValueError as error:
        return {feature: None for feature in FEATURES}, str(error)


def evaluate(model: OsteochondralUNet, records: list[SliceRecord], fold: int,
             classical: InterfaceParameters) -> list[dict]:
    device = next(model.parameters()).device; rows = []
    for number, record in enumerate(records, 1):
        image, target = load_pair(record)
        with torch.inference_mode():
            probability = torch.sigmoid(model(image[None].to(device))).cpu().numpy()[0, 0]
        prediction_mask = postprocess_probability(probability)
        reference_mask = target.numpy()[0] > 0.5
        truth = reference_interface(reference_mask)
        prediction = reference_interface(prediction_mask)
        if np.isfinite(prediction).sum() < 2 or np.isfinite(truth).sum() < 128:
            continue
        prediction = interpolate(prediction); truth_filled = interpolate(truth)
        metrics = boundary_metrics(prediction, truth, spacing_um=SPACING_UM)
        image_array = image.numpy()[0]
        threshold = threshold_comparator(image_array)
        classical_path, _ = estimate_interface(image_array, classical)
        union = np.logical_or(prediction_mask, reference_mask).sum()
        intersection = np.logical_and(prediction_mask, reference_mask).sum()
        reference_measurements, reference_abstention = safe_measurements(image_array, truth_filled)
        predicted_measurements, predicted_abstention = safe_measurements(image_array, prediction)
        row = {"fold": fold, "patient": record.patient, "sample": record.sample,
               "family": record.family, "index": record.index, **metrics,
               "full_mask_dice": float(2 * intersection / max(prediction_mask.sum() + reference_mask.sum(), 1)),
               "full_mask_iou": float(intersection / max(union, 1)),
               "band_iou_75_um": band_iou(prediction, truth, spacing_um=SPACING_UM),
               "threshold_error_um": comparator_error(threshold, truth),
               "classical_error_um": comparator_error(classical_path, truth),
               "reference_measurements": reference_measurements,
               "predicted_measurements": predicted_measurements,
               "reference_measurement_abstention": reference_abstention,
               "predicted_measurement_abstention": predicted_abstention}
        rows.append(row)
        if number % 50 == 0:
            print(json.dumps({"fold": fold, "evaluated": number, "retained": len(rows)}), flush=True)
    return rows


def summarize(rows: list[dict]) -> dict:
    fields = {key: collapse(rows, key) for key in ("full_mask_dice", "full_mask_iou", "median_absolute_error_um",
                                                    "p90_absolute_error_um", "within_30_um", "band_iou_75_um",
                                                    "threshold_error_um", "classical_error_um")}
    sample_features: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        item = sample_features.setdefault(row["sample"], {f"r:{f}": [] for f in FEATURES} |
                                                    {f"p:{f}": [] for f in FEATURES})
        for feature in FEATURES:
            item[f"r:{feature}"].append(row["reference_measurements"][feature])
            item[f"p:{feature}"].append(row["predicted_measurements"][feature])
    agreement, standardized = {}, []
    for feature in FEATURES:
        pairs = [(np.mean([x for x in v[f"r:{feature}"] if x is not None]),
                  np.mean([x for x in v[f"p:{feature}"] if x is not None]))
                 for v in sample_features.values()
                 if any(x is not None for x in v[f"r:{feature}"])
                 and any(x is not None for x in v[f"p:{feature}"])]
        if len(pairs) < 3:
            agreement[feature] = {"eligible_samples": len(pairs), "concordance_correlation": None,
                                  "spearman": None, "median_standardized_absolute_error": None}
            continue
        reference = np.asarray([pair[0] for pair in pairs]); predicted = np.asarray([pair[1] for pair in pairs])
        scale = max(float(np.std(reference, ddof=1)), np.finfo(float).eps)
        errors = np.abs(predicted - reference) / scale; standardized.extend(errors.tolist())
        rho = float(spearmanr(reference, predicted).statistic)
        agreement[feature] = {"eligible_samples": len(reference),
                              "concordance_correlation": concordance_correlation(reference, predicted),
                              "spearman": rho if np.isfinite(rho) else None,
                              "median_standardized_absolute_error": float(np.median(errors))}
    primary = {"patient_median_dice": float(np.median(list(fields["full_mask_dice"].values()))),
               "patient_median_interface_error_um": float(np.median(list(fields["median_absolute_error_um"].values()))),
               "patient_bootstrap_95_interval_um": interval(fields["median_absolute_error_um"]),
               "patient_median_p90_error_um": float(np.median(list(fields["p90_absolute_error_um"].values()))),
               "patient_median_within_30_um": float(np.median(list(fields["within_30_um"].values()))),
               "patient_median_band_iou_75_um": float(np.median(list(fields["band_iou_75_um"].values())))}
    comparisons = {"versus_threshold": paired_interval(fields["median_absolute_error_um"], fields["threshold_error_um"]),
                   "versus_classical": paired_interval(fields["median_absolute_error_um"], fields["classical_error_um"])}
    concordant = sum(v["concordance_correlation"] is not None and v["concordance_correlation"] >= .85
                     for v in agreement.values())
    median_standardized = float(np.median(standardized)) if standardized else None
    gates = {"all_patients_and_samples": len(fields["full_mask_dice"]) == 19 and len(sample_features) == 35,
             "dice_0_75": primary["patient_median_dice"] >= .75,
             "mae_30_um": primary["patient_median_interface_error_um"] <= 30,
             "mae_upper_45_um": primary["patient_bootstrap_95_interval_um"][1] <= 45,
             "within_30_um_70_percent": primary["patient_median_within_30_um"] >= .70,
             "band_iou_0_80": primary["patient_median_band_iou_75_um"] >= .80,
             "superior_to_both_comparators": all(v["bootstrap_95_interval_um"][1] < 0 for v in comparisons.values()),
             "downstream_agreement": concordant >= 4 and median_standardized is not None and median_standardized <= .20}
    return {"status": "technically_promising" if all(gates.values()) else "fail", "primary": primary,
            "comparators": comparisons, "downstream_measurement_agreement": agreement,
            "downstream_concordant_features": concordant,
            "downstream_median_standardized_absolute_error": median_standardized,
            "gates": gates, "patient_values": fields}


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen patient-grouped learned osteochondral adapter benchmark")
    parser.add_argument("dataset", type=Path); parser.add_argument("--development-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=12); parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--reuse-checkpoints", action="store_true")
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    records = discover(args.dataset); patients = sorted({r.patient for r in records}); folds = patient_folds(patients)
    if len(patients) != 19 or len({r.sample for r in records}) != 35:
        raise SystemExit(f"Expected 19 patients/35 samples, found {len(patients)}/{len({r.sample for r in records})}")
    development = json.loads(args.development_receipt.read_text(encoding="utf-8"))
    classical = InterfaceParameters(**development["selected_parameters"])
    prior_path = args.output / "osteochondral_learned_adapter.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if args.reuse_checkpoints and prior_path.is_file() else None
    all_rows, training = [], []
    for fold in range(5):
        test_patients = set(folds[fold]); validation_patients = set(folds[(fold + 1) % 5])
        train = [r for r in records if r.patient not in test_patients | validation_patients]
        validation = [r for r in records if r.patient in validation_patients]
        test = [r for r in records if r.patient in test_patients]
        if args.reuse_checkpoints:
            model = load_checkpoint(args.output, fold)
            trace = next((item for item in prior["training"] if item["fold"] == fold), {}) if prior else {}
            trace = {key: value for key, value in trace.items() if key in {"history", "selected_epoch", "best_validation_loss"}}
        else:
            model, trace = train_fold(train, validation, args.output, fold, epochs=args.epochs,
                                      batch_size=args.batch_size, workers=args.workers)
        all_rows.extend(evaluate(model, test, fold, classical))
        training.append({"fold": fold, "train_patients": sorted({r.patient for r in train}),
                         "validation_patients": sorted(validation_patients), "test_patients": sorted(test_patients),
                         "train_slices": len(train), "validation_slices": len(validation), "test_slices": len(test), **trace})
    result = summarize(all_rows)
    evaluated_keys = {(row["patient"], row["sample"], row["family"], row["index"]) for row in all_rows}
    omitted = [{"patient": r.patient, "sample": r.sample, "family": r.family, "index": r.index}
               for r in records if (r.patient, r.sample, r.family, r.index) not in evaluated_keys]
    result["gates"]["all_discovered_slices_evaluated"] = len(omitted) == 0
    result["status"] = "technically_promising" if all(result["gates"].values()) else "fail"
    payload = {"protocol_version": "nostos-osteochondral-learned-adapter/1.1", **result,
               "seed": SEED, "spacing_um": SPACING_UM, "records_discovered": len(records),
               "records_evaluated": len(all_rows), "fold_assignment": folds, "training": training,
               "prediction_coverage": len(all_rows) / len(records), "omitted_records": omitted,
               "implementation": {"module": str(Path(learned_module.__file__).resolve()),
                                  "module_sha256": sha256(Path(learned_module.__file__)),
                                  "script_sha256": sha256(Path(__file__))},
               "scope": "Post-failure development on one public PTA micro-CT dataset; not independent confirmation or clinical validation.",
               "slice_results": all_rows}
    destination = args.output / "osteochondral_learned_adapter.json"
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    compact = {key: value for key, value in payload.items() if key != "slice_results"}
    compact["implementation"] = {
        **payload["implementation"],
        "module": "src/nostos/segmentation/osteochondral.py",
    }
    compact["training"] = [
        {key: value for key, value in item.items() if key != "history"} for item in payload["training"]
    ]
    compact["full_slice_receipt"] = {
        "path": "<BULK_DATA_ROOT>/outputs/nostos0-osteochondral-learned-adapter-v1_1/osteochondral_learned_adapter.json",
        "sha256": sha256(destination),
    }
    compact_destination = args.output / "osteochondral_learned_adapter_summary.json"
    compact_destination.write_text(json.dumps(compact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), "status": payload["status"], "gates": payload["gates"]}, indent=2))


if __name__ == "__main__":
    main()
