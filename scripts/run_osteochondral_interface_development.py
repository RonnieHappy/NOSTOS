from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

import nostos.validation.osteochondral_interface as interface_module
from nostos.validation.osteochondral_interface import (
    InterfaceParameters,
    boundary_metrics,
    estimate_interface,
    reference_interface,
    threshold_comparator,
)


DEVELOPMENT_PATIENTS = {"O18", "29", "13", "23", "28", "26", "30", "27", "O19"}
INDICES = tuple(range(16, 433, 32))
SPACING_UM = 3.2
PROTOCOL_SHA256 = "D23D930FA6EE30A106ECA24DAD3DDA7856BF733E0A28E849B9D2628A3A1C1FC5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def patient_id(sample_id: str) -> str:
    return sample_id.split("_", 1)[0]


def load_records(root: Path) -> list[dict]:
    records: list[dict] = []
    for sample in sorted(path for path in root.iterdir() if path.is_dir()):
        patient = patient_id(sample.name)
        if patient not in DEVELOPMENT_PATIENTS:
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
            records.append({
                "patient": patient,
                "sample": sample.name,
                "family": family,
                "index": index,
                "image": image,
                "reference": reference,
            })
    return records


def patient_objective(rows: list[dict], accepted: np.ndarray | None = None) -> tuple[float, dict[str, float]]:
    if accepted is None:
        accepted = np.ones(len(rows), dtype=bool)
    sample_values: dict[tuple[str, str], list[float]] = {}
    for keep, row in zip(accepted, rows, strict=True):
        if keep:
            sample_values.setdefault((row["patient"], row["sample"]), []).append(row["error_um"])
    patient_values: dict[str, list[float]] = {}
    for (patient, _), values in sample_values.items():
        patient_values.setdefault(patient, []).append(float(np.median(values)))
    collapsed = {patient: float(np.median(values)) for patient, values in patient_values.items()}
    return float(np.mean(list(collapsed.values()))) if collapsed else float("inf"), collapsed


def bootstrap_upper(patient_values: dict[str, float], seed: int = 8_262_602) -> float:
    values = np.asarray(list(patient_values.values()), dtype=float)
    if values.size < 2:
        return float("inf")
    rng = np.random.default_rng(seed)
    draws = np.median(values[rng.integers(0, len(values), size=(10_000, len(values)))], axis=1)
    return float(np.percentile(draws, 97.5))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path, help="Extracted Data/pre_processed directory")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    records = load_records(args.dataset)
    if not records:
        raise SystemExit("No eligible development records found.")

    candidates: list[dict] = []
    parameter_grid = [
        InterfaceParameters(sigma, weight, penalty, sign)
        for sigma, weight, penalty, sign in itertools.product(
            (1.0, 2.0, 4.0), (0.0, 0.25, 0.5), (0.1, 0.5, 1.0), (-1, 1)
        )
    ]
    def evaluate(parameters: InterfaceParameters) -> dict:
        rows: list[dict] = []
        for record in records:
            prediction, confidence = estimate_interface(record["image"], parameters)
            metrics = boundary_metrics(prediction, record["reference"], spacing_um=SPACING_UM)
            rows.append({
                "patient": record["patient"], "sample": record["sample"],
                "error_um": metrics["median_absolute_error_um"], "confidence": confidence,
            })
        objective, patient_values = patient_objective(rows)
        return {
            "parameters": asdict(parameters), "patient_mean_of_sample_medians_um": objective,
            "patient_medians_um": patient_values,
        }
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        candidates = list(pool.map(evaluate, parameter_grid))
    candidates.sort(key=lambda item: item["patient_mean_of_sample_medians_um"])
    minimum_objective = candidates[0]["patient_mean_of_sample_medians_um"]
    tied = [item for item in candidates if item["patient_mean_of_sample_medians_um"] <= minimum_objective + 0.1]
    tied.sort(key=lambda item: (
        item["parameters"]["sigma_px"], item["parameters"]["contrast_weight"],
        item["parameters"]["jump_penalty"], item["parameters"]["contrast_sign"],
    ))
    selected = InterfaceParameters(**tied[0]["parameters"])

    selected_rows: list[dict] = []
    comparator_rows: list[dict] = []
    for record in records:
        prediction, confidence = estimate_interface(record["image"], selected)
        metrics = boundary_metrics(prediction, record["reference"], spacing_um=SPACING_UM)
        selected_rows.append({
            "patient": record["patient"], "sample": record["sample"],
            "family": record["family"], "index": record["index"],
            "error_um": metrics["median_absolute_error_um"], "confidence": confidence,
        })
        baseline = threshold_comparator(record["image"])
        if np.isfinite(baseline).sum() >= 128:
            baseline_metrics = boundary_metrics(baseline, record["reference"], spacing_um=SPACING_UM)
            comparator_rows.append({
                "patient": record["patient"], "sample": record["sample"],
                "error_um": baseline_metrics["median_absolute_error_um"],
            })

    confidence = np.asarray([row["confidence"] for row in selected_rows])
    selected_threshold: float | None = None
    threshold_audit: list[dict] = []
    for quantile in np.linspace(0.0, 0.30, 31):
        threshold = float(np.quantile(confidence, quantile))
        accepted = confidence >= threshold
        _, patient_values = patient_objective(selected_rows, accepted)
        coverage = float(np.mean(accepted))
        upper = bootstrap_upper(patient_values)
        threshold_audit.append({"threshold": threshold, "coverage": coverage, "bootstrap_upper_um": upper})
        if coverage >= 0.70 and upper <= 75.0:
            selected_threshold = threshold
            break
    accepted = np.ones(len(selected_rows), dtype=bool) if selected_threshold is None else confidence >= selected_threshold
    objective, patient_values = patient_objective(selected_rows, accepted)
    comparator_objective, comparator_patients = patient_objective(comparator_rows)

    output = {
        "protocol_version": "nostos-osteochondral-interface-development/1.0",
        "status": "development_only",
        "protocol_sha256": PROTOCOL_SHA256,
        "source_repository_commit": "aadc0dae99d06c58abb57062b5c97cecbd628527",
        "archive": {"bytes": args.archive.stat().st_size, "sha256": sha256(args.archive)},
        "implementation": {
            "module_sha256": sha256(Path(interface_module.__file__)),
            "development_runner_sha256": sha256(Path(__file__)),
        },
        "partition": {"patients": sorted(DEVELOPMENT_PATIENTS), "patient_count": len(DEVELOPMENT_PATIENTS)},
        "eligible_slices": len(records),
        "selected_parameters": asdict(selected),
        "selected_confidence_threshold": selected_threshold,
        "development_coverage": float(np.mean(accepted)),
        "development_patient_objective_um": objective,
        "development_patient_medians_um": patient_values,
        "comparator_patient_objective_um": comparator_objective,
        "comparator_patient_medians_um": comparator_patients,
        "candidate_audit": candidates,
        "confidence_threshold_audit": threshold_audit,
        "confirmation_lock": "No confirmation image or mask was opened before this receipt and implementation hash were written.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "osteochondral_interface_development.json"
    destination.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), "selected": asdict(selected), "slices": len(records)}, indent=2))


if __name__ == "__main__":
    main()
