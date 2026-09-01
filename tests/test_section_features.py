from pathlib import Path

import numpy as np
from PIL import Image

from nostos.features.section import extract_section_features
from nostos.segmentation.annotations import AnnotationRecord


def test_section_feature_row_contains_zsd_and_comparators(tmp_path: Path):
    size = 160
    _, x = np.mgrid[:size, :size]
    grayscale = (127 + 60 * np.sin(2 * np.pi * x / 12)).astype(np.uint8)
    image_array = np.repeat(grayscale[..., None], 3, axis=2)
    labels = np.zeros((size, size), dtype=np.uint8)
    labels[10:140, 10:150] = 1
    labels[140:150, 10:150] = 2
    image_path, mask_path = tmp_path / "image.png", tmp_path / "mask.png"
    Image.fromarray(image_array).save(image_path)
    Image.fromarray(labels).save(mask_path)
    record = AnnotationRecord("P001", "M1", "HE", image_path, mask_path, "train", "Medial")
    row = extract_section_features(record, pixel_size_um=10, tile_size=64, minimum_cartilage_fraction=0.6, boundary_exclusion_um=10)
    assert row["feature_success"]
    assert row["zsd_valid_tile_count"] > 0
    assert "global_fft_anisotropy" in row
    assert "texture_tensor_coherence_mean" in row
