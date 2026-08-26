from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from nostos.app.server import _tile_features
from nostos.segmentation.weak_labels import propose_semantic_mask


METRICS = (
    "orientation_degrees",
    "anisotropy",
    "angular_entropy",
    "spectral_slope",
    "characteristic_frequency_cycles_per_mm",
    "tensor_coherence",
    "glcm_contrast",
    "glcm_homogeneity",
    "hessian_blob_scale_2px",
    "hessian_blob_scale_4px",
    "hessian_blob_scale_8px",
    "hessian_tube_scale_2px",
    "hessian_tube_scale_4px",
    "hessian_tube_scale_8px",
    "hessian_sheet_scale_2px",
    "hessian_sheet_scale_4px",
    "hessian_sheet_scale_8px",
    "variogram_horizontal_sep_2px",
    "variogram_horizontal_sep_4px",
    "variogram_horizontal_sep_8px",
    "variogram_horizontal_sep_16px",
    "variogram_vertical_sep_2px",
    "variogram_vertical_sep_4px",
    "variogram_vertical_sep_8px",
    "variogram_vertical_sep_16px",
)


def analyze_record(record: dict) -> dict:
    path = Path(record["absolute_path"])
    try:
        with Image.open(path) as opened:
            image = np.asarray(opened.convert("RGB"))
        pixel_size = float(record["pixel_size_um_x"])
        mask = propose_semantic_mask(image, str(record["modality"]))
        tiles, warnings = _tile_features(image, mask, pixel_size)
        row: dict[str, object] = {
            "participant_id": record["participant_id"],
            "site": record["site"],
            "stain": record["modality"],
            "relative_path": record["relative_path"],
            "pixel_size_um": pixel_size,
            "image_width": image.shape[1],
            "image_height": image.shape[0],
            "cartilage_fraction": float(np.mean(mask == 1)),
            "bone_fraction": float(np.mean(mask == 3)),
            "analyzed_tiles": len(tiles),
            "feature_success": len(tiles) >= 1,
            "qc_warning": " | ".join(warnings),
        }
        for metric in METRICS:
            values = np.asarray([tile[metric] for tile in tiles], dtype=float)
            row[f"{metric}_median"] = float(np.median(values)) if values.size else np.nan
            row[f"{metric}_iqr"] = float(np.quantile(values, 0.75) - np.quantile(values, 0.25)) if values.size else np.nan
        return row
    except Exception as error:
        return {
            "participant_id": record.get("participant_id"),
            "site": record.get("site"),
            "stain": record.get("modality"),
            "relative_path": record.get("relative_path"),
            "feature_success": False,
            "feature_error": f"{type(error).__name__}: {error}",
        }


def select_records(manifest: dict, stain: str, site: str, section_rank: int = 1) -> list[dict]:
    if section_rank < 1:
        raise ValueError("section_rank must be at least 1")
    root = Path(manifest["dataset_root"])
    records = pd.DataFrame(manifest["records"])
    selected = records[(records["modality"] == stain) & (records["site"] == site)].copy()
    selected = selected.sort_values(["participant_id", "relative_path"])
    selected["section_rank"] = selected.groupby("participant_id").cumcount() + 1
    selected = selected[selected["section_rank"] == section_rank]
    rows = selected.to_dict("records")
    for row in rows:
        row["absolute_path"] = str((root / row["relative_path"]).resolve())
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic CPU-first NOSTOS cohort analysis")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stain", choices=["HE", "SafO", "PLM"], default="SafO")
    parser.add_argument("--site", choices=["Medial", "Lateral"], default="Medial")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--section-rank", type=int, default=1, help="One-based lexicographic section rank per participant/site")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = select_records(manifest, args.stain, args.site, args.section_rank)
    if args.limit:
        records = records[: args.limit]
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(analyze_record, record): record for record in records}
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            rows.append(row)
            print(json.dumps({"completed": index, "total": len(records), "participant_id": row.get("participant_id"), "success": row.get("feature_success")}), flush=True)
    if not rows:
        raise ValueError("No records matched the requested stain, site and section rank")
    frame = pd.DataFrame(rows).sort_values("participant_id")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    report = {
        "sections": len(frame),
        "successes": int(frame["feature_success"].fillna(False).sum()),
        "stain": args.stain,
        "site": args.site,
        "section_rank": args.section_rank,
        "workers": args.workers,
        "output": str(args.output),
    }
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
