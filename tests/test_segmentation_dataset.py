from pathlib import Path

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch")

from nostos.segmentation.annotations import AnnotationRecord
from nostos.segmentation.dataset import SegmentationTileDataset


def test_segmentation_dataset_shapes(tmp_path: Path):
    image = tmp_path / "image.png"
    mask = tmp_path / "mask.png"
    Image.fromarray(np.full((32, 32, 3), 127, dtype=np.uint8)).save(image)
    Image.fromarray(np.ones((32, 32), dtype=np.uint8)).save(mask)
    record = AnnotationRecord("P001", "M", "SafO", image, mask, "train")
    pixels, stain, labels = SegmentationTileDataset([record], tile_size=16)[0]
    assert pixels.shape == (3, 16, 16)
    assert labels.shape == (16, 16)
    assert stain.item() == 1
