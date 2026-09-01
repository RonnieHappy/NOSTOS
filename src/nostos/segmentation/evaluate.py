from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

from .annotations import read_annotation_manifest, validate_annotation_manifest
from .infer import load_model, predict_section
from .metrics import section_segmentation_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate complete locked validation sections.")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("annotation_manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-pixel-size-um", type=float, default=5.16)
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    records = read_annotation_manifest(args.annotation_manifest)
    errors = validate_annotation_manifest(records, require_review_audit=True)
    if errors:
        raise ValueError("Invalid annotation manifest:\n" + "\n".join(errors))
    validation = [record for record in records if record.split == "validation"]
    if not validation:
        raise ValueError("no locked validation masks in manifest")
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = load_model(args.checkpoint, device)
    prediction_dir = args.output / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in validation:
        prediction = predict_section(model, record.image_path, record.stain, device=device)
        with Image.open(record.mask_path) as opened:
            target = np.asarray(opened.convert("L"))
        metrics = section_segmentation_metrics(
            prediction, target, pixel_size_um=args.model_pixel_size_um
        )
        stem = f"{record.participant_id}_{record.specimen_id}_{record.stain}"
        Image.fromarray(prediction, mode="L").save(prediction_dir / f"{stem}.png")
        confusion = metrics.pop("confusion_matrix")
        rows.append({
            "participant_id": record.participant_id,
            "specimen_id": record.specimen_id,
            "site": record.site,
            "stain": record.stain,
            **metrics,
            "confusion_matrix_json": json.dumps(confusion),
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(args.output / "section_metrics.csv", index=False)
    print(json.dumps({"device": str(device), "validation_sections": len(frame), "metrics": str(args.output / "section_metrics.csv")}, indent=2))


if __name__ == "__main__":
    main()
