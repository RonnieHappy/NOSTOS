from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

ALLOWED_STAINS = {"HE", "SafO", "PLM"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def validate_review_audit(record: AnnotationRecord) -> list[str]:
    if record.review_path is None or not record.review_path.is_file():
        return [f"missing review audit: {record.image_path}"]
    try:
        audit = json.loads(record.review_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        return [f"invalid review audit {record.review_path}: {error}"]
    errors = []
    for field in ("source_image", "source_sha256", "reviewer", "reviewed_at", "statement"):
        if not audit.get(field):
            errors.append(f"review audit missing {field}: {record.review_path}")
    if audit.get("source_sha256") and audit["source_sha256"].lower() != _sha256(record.image_path):
        errors.append(f"review audit source checksum mismatch: {record.image_path}")
    if audit.get("width") and audit.get("height"):
        with Image.open(record.image_path) as image:
            if (int(audit["width"]), int(audit["height"])) != image.size:
                errors.append(f"review audit dimensions mismatch: {record.image_path}")
    return errors


@dataclass(frozen=True)
class AnnotationRecord:
    participant_id: str
    specimen_id: str
    stain: str
    image_path: Path
    mask_path: Path
    split: str
    site: str = "unknown"
    review_path: Path | None = None


def read_annotation_manifest(path: str | Path) -> list[AnnotationRecord]:
    manifest_path = Path(path)
    records: list[AnnotationRecord] = []
    with manifest_path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            records.append(
                AnnotationRecord(
                    participant_id=row["participant_id"].strip(),
                    specimen_id=row["specimen_id"].strip(),
                    stain=row["stain"].strip(),
                    image_path=(manifest_path.parent / row["image_path"]).resolve(),
                    mask_path=(manifest_path.parent / row["mask_path"]).resolve(),
                    split=row["split"].strip(),
                    site=row.get("site", "unknown").strip(),
                    review_path=(manifest_path.parent / row["review_path"]).resolve()
                    if row.get("review_path", "").strip()
                    else None,
                )
            )
    return records


def validate_annotation_manifest(
    records: list[AnnotationRecord],
    *,
    classes: int = 6,
    inspect_pixels: bool = True,
    require_review_audit: bool = False,
) -> list[str]:
    errors: list[str] = []
    participant_splits: dict[str, set[str]] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for record in records:
        participant_splits.setdefault(record.participant_id, set()).add(record.split)
        pair = (str(record.image_path), str(record.mask_path))
        if pair in seen_pairs:
            errors.append(f"duplicate image/mask pair: {record.image_path}")
        seen_pairs.add(pair)
        if record.stain not in ALLOWED_STAINS:
            errors.append(f"unsupported stain {record.stain!r}: {record.image_path}")
        if record.split not in {"train", "validation", "test"}:
            errors.append(f"unsupported split {record.split!r}: {record.image_path}")
        if record.site not in {"Medial", "Lateral", "unknown"}:
            errors.append(f"unsupported site {record.site!r}: {record.image_path}")
        if not record.image_path.is_file() or not record.mask_path.is_file():
            errors.append(f"missing image or mask: {record.image_path}, {record.mask_path}")
            continue
        if require_review_audit:
            errors.extend(validate_review_audit(record))
        with Image.open(record.image_path) as image, Image.open(record.mask_path) as mask:
            if image.size != mask.size:
                errors.append(f"dimension mismatch: {record.image_path}")
            if inspect_pixels:
                mask_array = np.asarray(mask)
                if mask_array.ndim == 3:
                    if not np.all(mask_array[..., :3] == mask_array[..., :1]):
                        errors.append(f"RGB mask channels are not identical: {record.mask_path}")
                    mask_array = mask_array[..., 0]
                labels = np.unique(mask_array)
                invalid = labels[(labels < 0) | (labels >= classes)]
                if invalid.size:
                    errors.append(f"invalid labels {invalid.tolist()}: {record.mask_path}")
    for participant, splits in participant_splits.items():
        if len(splits) > 1:
            errors.append(f"participant leakage: {participant} occurs in {sorted(splits)}")
    return errors
