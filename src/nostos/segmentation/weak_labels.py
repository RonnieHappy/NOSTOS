from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def _components(mask: np.ndarray, minimum: int = 256, largest_only: bool = False) -> np.ndarray:
    labels, count = ndimage.label(mask)
    if not count:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    keep = np.asarray([int(np.argmax(sizes))]) if largest_only and sizes.max() >= minimum else np.flatnonzero(sizes >= minimum)
    return np.isin(labels, keep)


def _clean(mask: np.ndarray, radius: int = 3, *, largest_only: bool = False) -> np.ndarray:
    structure = ndimage.generate_binary_structure(2, 1)
    result = ndimage.binary_opening(mask, structure=structure, iterations=max(1, radius // 2))
    result = ndimage.binary_closing(result, structure=structure, iterations=radius)
    return _components(ndimage.binary_fill_holes(result), largest_only=largest_only)


def propose_semantic_mask(rgb: np.ndarray, stain: str) -> np.ndarray:
    """Create conservative stain-aware proposals, not reference annotations.

    IDs follow the locked ontology: 0 background, 1 articular cartilage,
    2 calcified cartilage/tidemark, 3 bone, 4 marrow/void, 5 artifact.
    """
    image = np.asarray(rgb, dtype=np.float32) / 255.0
    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("rgb must have shape [height, width, 3]")
    red, green, blue = image[..., 0], image[..., 1], image[..., 2]
    chroma = image.max(2) - image.min(2)
    stain = stain.strip().upper()
    output = np.zeros(image.shape[:2], dtype=np.uint8)

    if stain == "SAFO":
        cartilage_seed = (red - blue > 0.10) & (red - green > 0.05) & (chroma > 0.12)
        bone_seed = (blue - red > 0.03) & (blue - green > 0.02) & (chroma > 0.10)
        cartilage = _clean(cartilage_seed, 5, largest_only=True)
        bone = _clean(bone_seed & ~ndimage.binary_dilation(cartilage, iterations=3), 3)
    elif stain == "HE":
        optical = -np.log(np.clip(image, 1 / 255.0, 1.0))
        tissue = optical.mean(2) > 0.08
        # Hematoxylin-rich hyaline cartilage is blue/purple; eosin-rich bone is red/pink.
        cartilage_seed = tissue & ((blue - red > 0.015) | ((blue > green) & (red < 0.86)))
        bone_seed = tissue & (red - blue > 0.025)
        cartilage = _clean(cartilage_seed, 5, largest_only=True)
        bone = _clean(bone_seed & ~ndimage.binary_dilation(cartilage, iterations=3), 3)
    elif stain == "PLM":
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        smooth = ndimage.gaussian_filter(luminance, sigma=24)
        high_pass = luminance - smooth
        texture = np.sqrt(ndimage.gaussian_filter(high_pass * high_pass, sigma=8))
        threshold = max(0.006, float(np.quantile(texture, 0.72)))
        foreground = texture > threshold
        occupancy = ndimage.gaussian_filter(foreground.astype(np.float32), sigma=12)
        dense_tissue = ndimage.binary_closing(occupancy > 0.28, iterations=4)
        # Retain only the broad connected core. Trabeculae are bright but thin and
        # perforated, while uncalcified cartilage contains a wide solid interior.
        core = ndimage.distance_transform_edt(dense_tissue) > 24
        core = _components(core, minimum=256, largest_only=True)
        cartilage = ndimage.binary_dilation(core, iterations=24) & dense_tissue
        bone = _clean(foreground & ~ndimage.binary_dilation(cartilage, iterations=4), 2)
    else:
        raise ValueError(f"unsupported stain: {stain}")

    output[bone] = 3
    output[cartilage] = 1
    # A conservative physical-interface surrogate; reviewers must refine the tidemark.
    interface = ndimage.binary_dilation(cartilage, iterations=4) & ndimage.binary_dilation(bone, iterations=4)
    output[interface] = 2
    return output


def proposal_overlay(rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    palette = np.asarray(
        [[0, 0, 0], [36, 209, 126], [255, 212, 59], [255, 107, 69], [91, 140, 255], [225, 67, 140]],
        dtype=np.uint8,
    )
    source = np.asarray(rgb, dtype=np.uint8)[..., :3]
    colors = palette[np.asarray(mask, dtype=np.uint8)]
    shown = source.copy()
    active = mask != 0
    shown[active] = np.rint((1 - alpha) * source[active] + alpha * colors[active]).astype(np.uint8)
    return shown


def generate_manifest_proposals(
    manifest_path: Path,
    output_dir: Path,
    stains: set[str] | None = None,
    proposal_manifest: Path | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(manifest_path.open(newline="", encoding="utf-8-sig")))
    counts: dict[str, int] = {}
    proposal_rows: list[dict[str, str]] = []
    for row in rows:
        if stains is not None and row["stain"].upper() not in stains:
            continue
        image_path = (manifest_path.parent.parent / "data" / "annotations" / row["image_path"]).resolve()
        # Prefer paths relative to the annotation manifest itself when used elsewhere.
        if not image_path.exists():
            image_path = (manifest_path.parent / row["image_path"]).resolve()
        if not image_path.exists():
            image_path = (Path("data/annotations") / row["image_path"]).resolve()
        with Image.open(image_path) as opened:
            rgb = np.asarray(opened.convert("RGB"))
            mask = propose_semantic_mask(rgb, row["stain"])
        destination = output_dir / Path(row["mask_path"]).name.replace("_reviewed", "_proposal")
        Image.fromarray(mask, mode="L").save(destination, optimize=True)
        preview = output_dir / "previews" / destination.name.replace("_proposal", "_proposal_overlay")
        preview.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(proposal_overlay(rgb, mask)).save(preview, optimize=True)
        counts[row["stain"]] = counts.get(row["stain"], 0) + 1
        if proposal_manifest is not None:
            proposal_rows.append({
                **row,
                "image_path": Path("../images") / Path(row["image_path"]).name,
                "mask_path": Path(destination.name),
                "review_path": "",
            })
    if proposal_manifest is not None:
        proposal_manifest.parent.mkdir(parents=True, exist_ok=True)
        fields = ["participant_id", "specimen_id", "site", "stain", "split", "image_path", "mask_path", "review_path"]
        with proposal_manifest.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(proposal_rows)
    report = {"proposal_masks": sum(counts.values()), "by_stain": counts, "status": "unreviewed_weak_supervision_only"}
    (output_dir / "proposal_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate unreviewed stain-aware semantic mask proposals.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stain", action="append", help="Optional stain(s) to regenerate")
    parser.add_argument("--proposal-manifest", type=Path)
    args = parser.parse_args()
    stains = {value.upper() for value in args.stain} if args.stain else None
    print(json.dumps(generate_manifest_proposals(args.manifest, args.output, stains, args.proposal_manifest), indent=2))


if __name__ == "__main__":
    main()
