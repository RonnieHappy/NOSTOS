import numpy as np
from PIL import Image

from nostos.validation.selective_filament_transfer import _load_square


def test_load_square_preserves_binary_mask(tmp_path):
    image = np.zeros((80, 120), dtype=np.uint8)
    image[:, 30:90] = 200
    mask = image > 0
    image_path, mask_path = tmp_path / "image.png", tmp_path / "mask.png"
    Image.fromarray(image).save(image_path)
    Image.fromarray(mask).save(mask_path)
    loaded_image, loaded_mask = _load_square(image_path, mask_path)
    assert loaded_image.shape == loaded_mask.shape == (128, 128)
    assert loaded_mask.dtype == bool
    assert set(np.unique(loaded_mask)) <= {False, True}

