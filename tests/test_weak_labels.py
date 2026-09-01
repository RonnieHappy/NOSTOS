import numpy as np

from nostos.segmentation.weak_labels import propose_semantic_mask


def test_safo_red_cartilage_and_blue_bone_are_separated():
    image = np.full((96, 128, 3), 245, dtype=np.uint8)
    image[16:72, 12:60] = [185, 55, 35]
    image[24:80, 72:116] = [30, 145, 190]
    mask = propose_semantic_mask(image, "SafO")
    assert np.mean(mask[24:64, 20:52] == 1) > 0.9
    assert np.mean(mask[32:72, 80:108] == 3) > 0.9


def test_unknown_stain_is_rejected():
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    try:
        propose_semantic_mask(image, "unknown")
    except ValueError as error:
        assert "unsupported stain" in str(error)
    else:
        raise AssertionError("unsupported stain was accepted")
