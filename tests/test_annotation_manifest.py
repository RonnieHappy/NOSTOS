from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image

from nostos.segmentation.annotations import AnnotationRecord, validate_annotation_manifest


def _write_image(path: Path, array: np.ndarray) -> None:
    Image.fromarray(array).save(path)


def test_annotation_manifest_detects_participant_leakage(tmp_path: Path):
    image = tmp_path / "image.png"
    mask = tmp_path / "mask.png"
    _write_image(image, np.zeros((8, 8, 3), dtype=np.uint8))
    _write_image(mask, np.ones((8, 8), dtype=np.uint8))
    records = [
        AnnotationRecord("P001", "M", "HE", image, mask, "train"),
        AnnotationRecord("P001", "L", "SafO", image, mask, "test"),
    ]
    errors = validate_annotation_manifest(records)
    assert any("participant leakage" in error for error in errors)


def test_annotation_manifest_accepts_valid_record(tmp_path: Path):
    image = tmp_path / "image.png"
    mask = tmp_path / "mask.png"
    _write_image(image, np.zeros((8, 8, 3), dtype=np.uint8))
    _write_image(mask, np.ones((8, 8), dtype=np.uint8))
    record = AnnotationRecord("P001", "M", "PLM", image, mask, "validation")
    assert validate_annotation_manifest([record]) == []


def test_review_audit_checksum_is_required_for_training(tmp_path: Path):
    image = tmp_path / "image.png"
    mask = tmp_path / "mask.png"
    review = tmp_path / "review.json"
    _write_image(image, np.zeros((8, 8, 3), dtype=np.uint8))
    _write_image(mask, np.ones((8, 8), dtype=np.uint8))
    review.write_text(json.dumps({
        "source_image": image.name,
        "source_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "width": 8,
        "height": 8,
        "reviewer": "R1",
        "reviewed_at": "2026-08-24T00:00:00Z",
        "statement": "reviewed",
    }), encoding="utf-8")
    record = AnnotationRecord("P001", "M", "HE", image, mask, "train", "Medial", review)
    assert validate_annotation_manifest([record], require_review_audit=True) == []
