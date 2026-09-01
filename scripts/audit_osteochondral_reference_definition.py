from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from scipy import ndimage

from nostos.segmentation.osteochondral import OsteochondralUNet, load_pair, postprocess_probability
from nostos.validation.osteochondral_interface import band_iou, boundary_metrics, reference_interface

from run_osteochondral_learned_adapter import (
    SEED,
    SPACING_UM,
    collapse,
    discover,
    interpolate,
    interval,
    patient_folds,
)

PROTOCOL_VERSION = "nostos-osteochondral-reference-audit/1.0"
POLICIES = ("top_any", "bottom_any", "top_largest", "bottom_largest")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def largest_component(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(np.asarray(mask, dtype=bool), structure=np.ones((3, 3), dtype=int))
    if count == 0:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(np.argmax(sizes))


def policy_interface(mask: np.ndarray, policy: str) -> np.ndarray:
    selected = np.asarray(mask, dtype=bool)
    if policy.endswith("largest"):
        selected = largest_component(selected)
    if policy.startswith("bottom"):
        reversed_path = reference_interface(selected[::-1])
        return np.where(np.isfinite(reversed_path), selected.shape[0] - 1 - reversed_path, np.nan)
    return reference_interface(selected)


def paired_interval(a: dict[str, float], b: dict[str, float]) -> dict[str, object]:
    keys = sorted(set(a) & set(b))
    differences = np.asarray([a[key] - b[key] for key in keys], dtype=float)
    rng = np.random.default_rng(SEED)
    draws = np.median(differences[rng.integers(0, len(keys), (10_000, len(keys)))], axis=1)
    return {
        "patients": len(keys),
        "median_difference_um": float(np.median(differences)),
        "bootstrap_95_interval_um": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))],
        "patients_absolute_change_ge_30_um": int(np.sum(np.abs(differences) >= 30.0)),
    }


def topology(mask: np.ndarray) -> dict[str, float | int]:
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    foreground = int(mask.sum())
    if foreground == 0:
        return {"components": 0, "largest_component_fraction": 0.0}
    sizes = np.bincount(labels.ravel())[1:]
    return {"components": int(count), "largest_component_fraction": float(sizes.max() / foreground)}


def load_model(directory: Path, fold: int) -> OsteochondralUNet:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(directory / f"fold_{fold}.pt", map_location=device, weights_only=True)
    model = OsteochondralUNet().to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def summarize(rows: list[dict], policy: str) -> dict[str, object]:
    eligible = [row for row in rows if row["policy"] == policy and row["retained"]]
    fields = {
        key: collapse(eligible, key)
        for key in ("median_absolute_error_um", "p90_absolute_error_um", "within_30_um", "band_iou_75_um")
    }
    disagreement = collapse(eligible, "reference_disagreement_um")
    return {
        "slices_evaluated": len(eligible),
        "patients_evaluated": len(fields["median_absolute_error_um"]),
        "patient_median_interface_error_um": float(np.median(list(fields["median_absolute_error_um"].values()))),
        "patient_bootstrap_95_interval_um": interval(fields["median_absolute_error_um"]),
        "patient_median_p90_error_um": float(np.median(list(fields["p90_absolute_error_um"].values()))),
        "patient_median_within_30_um": float(np.median(list(fields["within_30_um"].values()))),
        "patient_median_band_iou_75_um": float(np.median(list(fields["band_iou_75_um"].values()))),
        "patient_median_reference_disagreement_um": float(np.median(list(disagreement.values()))),
        "patient_reference_disagreement_values_um": disagreement,
        "patient_values": fields,
    }


def evaluate_model(name: str, checkpoint_dir: Path, records: list, folds: list[list[str]]) -> dict[str, object]:
    rows: list[dict] = []
    for fold in range(5):
        model = load_model(checkpoint_dir, fold)
        device = next(model.parameters()).device
        test_patients = set(folds[fold])
        test = [record for record in records if record.patient in test_patients]
        for number, record in enumerate(test, 1):
            image, target = load_pair(record)
            with torch.inference_mode():
                probability = torch.sigmoid(model(image[None].to(device))).cpu().numpy()[0, 0]
            prediction_mask = postprocess_probability(probability)
            prediction = reference_interface(prediction_mask)
            reference_mask = target.numpy()[0] > 0.5
            topo = topology(reference_mask)
            for policy in POLICIES:
                truth = policy_interface(reference_mask, policy)
                retained = np.isfinite(prediction).sum() >= 2 and np.isfinite(truth).sum() >= 128
                row = {
                    "model": name,
                    "fold": fold,
                    "patient": record.patient,
                    "sample": record.sample,
                    "family": record.family,
                    "index": record.index,
                    "policy": policy,
                    "retained": bool(retained),
                    **topo,
                }
                if retained:
                    predicted_filled = interpolate(prediction)
                    truth_filled = interpolate(truth)
                    row.update(boundary_metrics(predicted_filled, truth, spacing_um=SPACING_UM))
                    row["band_iou_75_um"] = band_iou(predicted_filled, truth, spacing_um=SPACING_UM)
                    top = policy_interface(reference_mask, "top_any")
                    common = np.isfinite(top) & np.isfinite(truth)
                    row["reference_disagreement_um"] = (
                        float(np.median(np.abs(top[common] - truth[common])) * SPACING_UM) if common.any() else None
                    )
                    row["truth_filled_median_row"] = float(np.median(truth_filled))
                rows.append(row)
            if number % 100 == 0:
                print(json.dumps({"model": name, "fold": fold, "processed": number}), flush=True)

    policies = {policy: summarize(rows, policy) for policy in POLICIES}
    unique_topology = [row for row in rows if row["policy"] == "top_any"]
    components = np.asarray([row["components"] for row in unique_topology], dtype=float)
    largest_fractions = np.asarray([row["largest_component_fraction"] for row in unique_topology], dtype=float)
    topology_summary = {
        "slices": len(unique_topology),
        "median_components": float(np.median(components)),
        "p95_components": float(np.percentile(components, 95)),
        "maximum_components": int(np.max(components)),
        "fraction_with_multiple_components": float(np.mean(components > 1)),
        "median_largest_component_fraction": float(np.median(largest_fractions)),
        "fraction_largest_component_below_0_90": float(np.mean(largest_fractions < 0.90)),
    }
    baseline = policies["top_any"]["patient_values"]["median_absolute_error_um"]
    comparisons = {}
    material = False
    for policy in POLICIES[1:]:
        values = policies[policy]["patient_values"]["median_absolute_error_um"]
        comparison = paired_interval(values, baseline)
        baseline_median = policies["top_any"]["patient_median_interface_error_um"]
        policy_median = policies[policy]["patient_median_interface_error_um"]
        comparison["relative_median_change"] = float((policy_median - baseline_median) / baseline_median)
        comparison["material_by_frozen_threshold"] = bool(
            abs(comparison["relative_median_change"]) >= 0.25
            or comparison["patients_absolute_change_ge_30_um"] >= 5
        )
        material = material or comparison["material_by_frozen_threshold"]
        comparisons[policy] = comparison
    return {"policies": policies, "reference_mask_topology": topology_summary,
            "comparisons_to_top_any": comparisons,
            "material_reference_sensitivity": material, "slice_results": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen post-test audit of osteochondral interface definitions")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--v1-checkpoints", type=Path, required=True)
    parser.add_argument("--v2-checkpoints", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compact-output", type=Path)
    args = parser.parse_args()
    records = discover(args.dataset)
    patients = sorted({record.patient for record in records})
    samples = sorted({record.sample for record in records})
    if len(records) != 1960 or len(patients) != 19 or len(samples) != 35:
        raise SystemExit(f"Expected 1960 slices/19 patients/35 samples, found {len(records)}/{len(patients)}/{len(samples)}")
    folds = patient_folds(patients)
    models = {
        "v1_1_dice": evaluate_model("v1_1_dice", args.v1_checkpoints, records, folds),
        "v2_0_boundary": evaluate_model("v2_0_boundary", args.v2_checkpoints, records, folds),
    }
    rankings = {}
    for policy in POLICIES:
        v1 = models["v1_1_dice"]["policies"][policy]["patient_median_interface_error_um"]
        v2 = models["v2_0_boundary"]["policies"][policy]["patient_median_interface_error_um"]
        preferred = "tie" if np.isclose(v1, v2) else ("v1_1_dice" if v1 < v2 else "v2_0_boundary")
        rankings[policy] = {"v1_1_um": v1, "v2_0_um": v2, "preferred": preferred}
    preferred = {value["preferred"] for value in rankings.values()}
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "reference_inadequate_for_definitive_interface_claim"
        if any(model["material_reference_sensitivity"] for model in models.values()) or len(preferred) > 1
        else "reference_policy_stable",
        "scope": "Frozen post-test sensitivity audit; no model retraining and no clinical validation.",
        "dataset": {"slices": len(records), "patients": len(patients), "samples": len(samples), "spacing_um": SPACING_UM},
        "source_provenance": {
            "paper": "https://arxiv.org/abs/1907.05089",
            "repository": "https://github.com/MIPT-Oulu/mCTSegmentation",
            "repository_commit_audited": "aadc0dae99d06c58abb57062b5c97cecbd628527",
            "source_evaluation_file": "code/evaluate_metrics.py",
        },
        "protocol_sha256": sha256(args.protocol),
        "script_sha256": sha256(Path(__file__)),
        "models": models,
        "model_rankings": rankings,
        "ranking_reversal": len(preferred) > 1,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    full_path = args.output / "osteochondral_reference_definition_audit.json"
    full_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    compact = json.loads(json.dumps(payload))
    for model in compact["models"].values():
        model.pop("slice_results", None)
    compact["full_receipt"] = {"path": "<BULK_DATA_ROOT>/outputs/nostos0-osteochondral-reference-audit-v1/osteochondral_reference_definition_audit.json", "sha256": sha256(full_path)}
    compact_path = args.output / "osteochondral_reference_definition_audit_summary.json"
    compact_path.write_text(json.dumps(compact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.compact_output is not None:
        args.compact_output.parent.mkdir(parents=True, exist_ok=True)
        args.compact_output.write_text(json.dumps(compact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(full_path), "status": payload["status"], "rankings": rankings}, indent=2))


if __name__ == "__main__":
    main()
