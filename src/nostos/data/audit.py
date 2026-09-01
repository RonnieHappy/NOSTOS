from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any

import tifffile

IMAGE_SUFFIXES = {".tif", ".tiff"}
PARTICIPANT_PATTERN = re.compile(r"^(?:p|patient|participant|subject)[-_ ]*(\d+)$", re.I)


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def infer_participant_id(path: Path, root: Path) -> str | None:
    for part in path.relative_to(root).parts:
        match = PARTICIPANT_PATTERN.search(part)
        if match:
            return match.group(1).zfill(3)
    return None


def load_documented_pixel_sizes(root: Path) -> dict[str, float]:
    candidates = list(root.rglob("image_information.xml"))
    if not candidates:
        return {}
    tree = ElementTree.parse(candidates[0])
    scales: dict[str, float] = {}
    for element in tree.getroot():
        match = re.match(r"(HE|SafO|PLM)_Image_scale$", element.tag, re.I)
        if not match or element.attrib.get("unit") != "microns_per_pixel":
            continue
        modality = {"he": "HE", "safo": "SafO", "plm": "PLM"}[match.group(1).lower()]
        scales[modality] = float(element.attrib["value"])
    return scales


def infer_modality(path: Path) -> str:
    text = " ".join(path.parts).lower()
    if "plm" in text or "polar" in text:
        return "PLM"
    if "safo" in text or "safranin" in text:
        return "SafO"
    if re.search(r"(?:^|[ _-])h(?:&|and)?e(?:[ _.-]|$)", text):
        return "HE"
    return "unknown"


def infer_site(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "medial" in parts:
        return "Medial"
    if "lateral" in parts:
        return "Lateral"
    return "unknown"


def read_tiff_header(path: Path) -> dict[str, Any]:
    """Read geometry and any standard physical-resolution tags without loading pixels."""
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        result: dict[str, Any] = {
            "height_pixels": int(page.imagelength),
            "width_pixels": int(page.imagewidth),
            "dtype": str(page.dtype),
            "page_count": len(tif.pages),
            "pixel_size_um_x": None,
            "pixel_size_um_y": None,
            "pixel_size_source": None,
        }
        x_resolution = page.tags.get("XResolution")
        y_resolution = page.tags.get("YResolution")
        resolution_unit = page.tags.get("ResolutionUnit")
        if x_resolution and y_resolution and resolution_unit:
            unit_value = int(resolution_unit.value)
            micrometers_per_unit = {2: 25_400.0, 3: 10_000.0}.get(unit_value)
            if micrometers_per_unit:
                x_pixels_per_unit = float(x_resolution.value[0]) / float(x_resolution.value[1])
                y_pixels_per_unit = float(y_resolution.value[0]) / float(y_resolution.value[1])
                if x_pixels_per_unit > 0 and y_pixels_per_unit > 0:
                    result["pixel_size_um_x"] = micrometers_per_unit / x_pixels_per_unit
                    result["pixel_size_um_y"] = micrometers_per_unit / y_pixels_per_unit
                    result["pixel_size_source"] = "tiff_resolution_tags"
        return result


def build_manifest(root: Path, include_checksums: bool = False) -> dict[str, Any]:
    root = root.resolve()
    images = sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    documented_pixel_sizes = load_documented_pixel_sizes(root)
    rejected_nominal_tiff_resolution = False

    for image in images:
        participant_id = infer_participant_id(image, root)
        if participant_id is None:
            warnings.append(f"No participant ID inferred: {image.relative_to(root)}")
        record: dict[str, Any] = {
            "participant_id": participant_id,
            "relative_path": image.relative_to(root).as_posix(),
            "modality": infer_modality(image),
            "site": infer_site(image),
            "bytes": image.stat().st_size,
        }
        try:
            header = read_tiff_header(image)
            tagged_pixel_size = header.get("pixel_size_um_x")
            if tagged_pixel_size is not None and not 0.05 <= float(tagged_pixel_size) <= 20.0:
                header["tiff_tag_pixel_size_um_x"] = header["pixel_size_um_x"]
                header["tiff_tag_pixel_size_um_y"] = header["pixel_size_um_y"]
                header["pixel_size_um_x"] = None
                header["pixel_size_um_y"] = None
                header["pixel_size_source"] = None
                rejected_nominal_tiff_resolution = True
            modality = record["modality"]
            if modality in documented_pixel_sizes:
                header["pixel_size_um_x"] = documented_pixel_sizes[modality]
                header["pixel_size_um_y"] = documented_pixel_sizes[modality]
                header["pixel_size_source"] = "image_information.xml"
            record.update(header)
        except Exception as error:
            record["header_error"] = f"{type(error).__name__}: {error}"
            warnings.append(f"TIFF header could not be read: {image.relative_to(root)}")
        if include_checksums:
            record["sha256"] = sha256(image)
        records.append(record)

    participants = sorted({r["participant_id"] for r in records if r["participant_id"]})
    metadata_files = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.suffix.lower() in {".xml", ".csv"}
    )

    if not images:
        warnings.append("No TIFF images found.")
    if len(participants) != 90:
        warnings.append(f"Expected 90 participants; inferred {len(participants)}.")
    if rejected_nominal_tiff_resolution:
        warnings.append(
            "Implausible nominal TIFF resolution tags were ignored in favor of repository calibration."
        )

    participant_inventory: dict[str, dict[str, Any]] = {}
    for participant_id in participants:
        selected = [record for record in records if record["participant_id"] == participant_id]
        modality_counts = {name: sum(record["modality"] == name for record in selected) for name in ("HE", "SafO", "PLM", "unknown")}
        site_counts = {name: sum(record["site"] == name for record in selected) for name in ("Medial", "Lateral", "unknown")}
        participant_inventory[participant_id] = {
            "image_count": len(selected),
            "modality_counts": modality_counts,
            "site_counts": site_counts,
            "has_all_modalities": all(modality_counts[name] > 0 for name in ("HE", "SafO", "PLM")),
            "has_both_sites": all(site_counts[name] > 0 for name in ("Medial", "Lateral")),
            "header_error_count": sum("header_error" in record for record in selected),
        }

    return {
        "schema_version": 1,
        "dataset_root": str(root),
        "participant_count": len(participants),
        "image_count": len(records),
        "participants": participants,
        "documented_pixel_sizes_um": documented_pixel_sizes,
        "metadata_files": metadata_files,
        "records": records,
        "participant_inventory": participant_inventory,
        "warnings": sorted(set(warnings)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an extracted NOSTOS public dataset.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checksums", action="store_true")
    args = parser.parse_args()

    manifest = build_manifest(args.root, include_checksums=args.checksums)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("participant_count", "image_count", "warnings")}, indent=2))


if __name__ == "__main__":
    main()
