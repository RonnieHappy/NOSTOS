from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def standardize_segmentation_image(
    source: str | Path,
    destination: str | Path,
    *,
    input_pixel_size_um: float,
    model_pixel_size_um: float = 5.16,
) -> dict[str, float | int | str]:
    if input_pixel_size_um <= 0 or model_pixel_size_um <= 0:
        raise ValueError("pixel sizes must be positive")
    source, destination = Path(source), Path(destination)
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        original_width, original_height = image.size
        scale = input_pixel_size_um / model_pixel_size_um
        target = (max(1, round(original_width * scale)), max(1, round(original_height * scale)))
        if target != image.size:
            image = image.resize(target, Image.Resampling.BOX if scale < 1 else Image.Resampling.BICUBIC)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG", optimize=True)
    return {
        "source": str(source.resolve()),
        "source_sha256": sha256(source),
        "source_width": original_width,
        "source_height": original_height,
        "prepared_width": target[0],
        "prepared_height": target[1],
        "input_pixel_size_um": input_pixel_size_um,
        "model_pixel_size_um": model_pixel_size_um,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare common-scale images for reviewed segmentation masks.")
    parser.add_argument("selection_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-pixel-size-um", type=float, default=5.16)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_rows, provenance = [], []
    with args.selection_csv.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            source = Path(row["image_path"])
            stem = f'{row["participant_id"]}_{row["specimen_id"]}_{row["stain"]}'
            image_path = args.output / "images" / f"{stem}.png"
            mask_path = args.output / "masks" / f"{stem}_reviewed.png"
            details = standardize_segmentation_image(
                source,
                image_path,
                input_pixel_size_um=float(row["pixel_size_um"]),
                model_pixel_size_um=args.model_pixel_size_um,
            )
            provenance.append({**row, **details})
            manifest_rows.append({
                "participant_id": row["participant_id"],
                "specimen_id": row["specimen_id"],
                "site": row["site"],
                "stain": row["stain"],
                "split": row["split"],
                "image_path": image_path.relative_to(args.output).as_posix(),
                "mask_path": mask_path.relative_to(args.output).as_posix(),
                "review_path": (args.output / "masks" / f"{stem}_review.json").relative_to(args.output).as_posix(),
            })
    fields = ["participant_id", "specimen_id", "site", "stain", "split", "image_path", "mask_path", "review_path"]
    with (args.output / "annotation_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest_rows)
    (args.output / "source_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"prepared_images": len(manifest_rows), "reviewed_masks_required": len(manifest_rows)}, indent=2))


if __name__ == "__main__":
    main()
