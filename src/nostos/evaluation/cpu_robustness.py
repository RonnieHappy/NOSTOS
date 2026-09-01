from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from nostos.evaluation.robustness import (
    apply_rotation,
    axial_angle_difference,
    evaluate_robustness_suite,
)
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.segmentation.weak_labels import propose_semantic_mask


def representative_tile(image: np.ndarray, mask: np.ndarray, size: int = 256) -> np.ndarray:
    candidates = []
    for top in range(0, image.shape[0] - size + 1, size // 2):
        for left in range(0, image.shape[1] - size + 1, size // 2):
            fraction = float(np.mean(mask[top : top + size, left : left + size] == 1))
            candidates.append((fraction, top, left))
    fraction, top, left = max(candidates)
    if fraction < .8:
        raise ValueError(f"no representative cartilage tile; maximum fraction={fraction:.3f}")
    return image[top : top + size, left : left + size]


def main() -> None:
    parser = argparse.ArgumentParser(description="CPU FFT acquisition-robustness panel")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--participants", type=int, default=20)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = pd.DataFrame(manifest["records"])
    records = records[(records["modality"] == "SafO") & (records["site"] == "Medial")]
    records = records.sort_values(["participant_id", "relative_path"]).drop_duplicates("participant_id")
    indices = np.linspace(0, len(records) - 1, args.participants).round().astype(int)
    records = records.iloc[indices]
    root = Path(manifest["dataset_root"])
    rows = []
    for _, record in records.iterrows():
        path = root / record["relative_path"]
        with Image.open(path) as opened:
            image = np.asarray(opened.convert("RGB"))
        mask = propose_semantic_mask(image, "SafO")
        tile = representative_tile(image, mask)
        pixel_size = float(record["pixel_size_um_x"])
        for result in evaluate_robustness_suite(tile, pixel_size_um=pixel_size):
            rows.append({"participant_id": record["participant_id"], **result})
        reference = extract_spatial_fft(tile, pixel_size_um=pixel_size)
        rotated = extract_spatial_fft(apply_rotation(tile, 90), pixel_size_um=pixel_size)
        expected = (reference.orientation_degrees + 90) % 180
        rows.append({
            "participant_id": record["participant_id"],
            "perturbation": "rotation_90",
            "success": True,
            "orientation_degrees_absolute_drift": axial_angle_difference(expected, rotated.orientation_degrees),
            "anisotropy_relative_drift": abs(rotated.anisotropy - reference.anisotropy) / max(abs(reference.anisotropy), np.finfo(float).eps),
            "angular_entropy_relative_drift": abs(rotated.angular_entropy - reference.angular_entropy) / max(abs(reference.angular_entropy), np.finfo(float).eps),
            "spectral_slope_relative_drift": abs(rotated.spectral_slope - reference.spectral_slope) / max(abs(reference.spectral_slope), np.finfo(float).eps),
            "characteristic_frequency_cycles_per_mm_relative_drift": abs(rotated.characteristic_frequency_cycles_per_mm - reference.characteristic_frequency_cycles_per_mm) / max(abs(reference.characteristic_frequency_cycles_per_mm), np.finfo(float).eps),
        })
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    metrics = [column for column in frame if column.endswith("_drift")]
    summary = frame.groupby("perturbation")[metrics].agg(["median", lambda value: np.quantile(value.dropna(), .95)]).reset_index()
    summary.columns = ["perturbation" if column[0] == "perturbation" else f"{column[0]}_{'p95' if column[1] == '<lambda_0>' else column[1]}" for column in summary.columns]
    summary.to_csv(args.output.with_name(args.output.stem + "_summary.csv"), index=False)
    report = {"participants": int(frame["participant_id"].nunique()), "tests": len(frame), "failures": int((~frame["success"].astype(bool)).sum())}
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
