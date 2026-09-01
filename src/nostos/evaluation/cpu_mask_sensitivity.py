from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from nostos.app.server import _tile_features
from nostos.evaluation.mask_uncertainty import perturb_cartilage_mask
from nostos.segmentation.weak_labels import propose_semantic_mask


def main() -> None:
    parser = argparse.ArgumentParser(description="Cartilage-boundary sensitivity for CPU FFT endpoints")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--participants", type=int, default=10)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = Path(manifest["dataset_root"])
    records = pd.DataFrame(manifest["records"])
    records = records[(records["modality"] == "SafO") & (records["site"] == "Medial")]
    records = records.sort_values(["participant_id", "relative_path"]).drop_duplicates("participant_id")
    records = records.iloc[np.linspace(0, len(records) - 1, args.participants).round().astype(int)]
    rows = []
    for _, record in records.iterrows():
        with Image.open(root / record["relative_path"]) as opened:
            image = np.asarray(opened.convert("RGB"))
        pixel_size = float(record["pixel_size_um_x"])
        labels = propose_semantic_mask(image, "SafO")
        reference_tiles, _ = _tile_features(image, labels, pixel_size)
        reference_entropy = float(np.median([tile["angular_entropy"] for tile in reference_tiles]))
        for delta in (-100.0, -50.0, 0.0, 50.0, 100.0):
            perturbed = perturb_cartilage_mask(labels, delta_um=delta, pixel_size_um=pixel_size)
            tiles, warnings = _tile_features(image, perturbed, pixel_size)
            entropy = float(np.median([tile["angular_entropy"] for tile in tiles])) if tiles else np.nan
            rows.append({
                "participant_id": record["participant_id"], "delta_um": delta,
                "tiles": len(tiles), "angular_entropy_median": entropy,
                "angular_entropy_relative_drift": abs(entropy - reference_entropy) / abs(reference_entropy) if np.isfinite(entropy) else np.nan,
                "success": bool(tiles), "qc_warning": " | ".join(warnings),
            })
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    summary = frame.groupby("delta_um").agg(
        participants=("participant_id", "nunique"), success_rate=("success", "mean"),
        entropy_drift_median=("angular_entropy_relative_drift", "median"),
        entropy_drift_p95=("angular_entropy_relative_drift", lambda value: np.quantile(value.dropna(), .95)),
    ).reset_index()
    summary.to_csv(args.output.with_name(args.output.stem + "_summary.csv"), index=False)
    report = {"participants": int(frame["participant_id"].nunique()), "conditions": len(frame), "failures": int((~frame["success"]).sum())}
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
