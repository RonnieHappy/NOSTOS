from pathlib import Path

import numpy as np
from PIL import Image

from nostos.segmentation.prepare import standardize_segmentation_image


def test_brightfield_is_resampled_to_common_physical_scale(tmp_path: Path):
    source, output = tmp_path / "source.png", tmp_path / "prepared.png"
    Image.fromarray(np.zeros((300, 600, 3), dtype=np.uint8)).save(source)
    details = standardize_segmentation_image(source, output, input_pixel_size_um=1.72, model_pixel_size_um=5.16)
    with Image.open(output) as prepared:
        assert prepared.size == (200, 100)
    assert details["model_pixel_size_um"] == 5.16
    assert len(details["source_sha256"]) == 64
