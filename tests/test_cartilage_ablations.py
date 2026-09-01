import numpy as np

from nostos.evaluation.cartilage_ablations import _geometry_and_intensity, ablation_masks


def test_ablation_masks_remove_surface_and_void_neighborhoods():
    semantic = np.zeros((80, 100), dtype=np.uint8)
    semantic[10:70, 10:90] = 1
    semantic[35:45, 45:55] = 4
    image = np.full((80, 100, 3), 180, dtype=np.uint8)
    image[30:34, 30:34] = 0
    masks = ablation_masks(semantic, 10.0, image)
    assert masks["eroded_250um"].sum() < masks["eroded_100um"].sum() < masks["baseline_072"].sum()
    assert not masks["void_excluded_100um"][40, 40]
    assert not masks["surface_excluded_100um"][15, 50]
    assert masks["surface_excluded_100um"][30, 30]
    assert not masks["internal_hole_excluded_100um"][40, 40]
    assert not masks["extreme_dark_object_excluded_25um"][31, 31]


def test_geometry_and_optical_density_are_physical_and_finite():
    semantic = np.zeros((20, 20), dtype=np.uint8)
    semantic[5:15, 5:15] = 1
    image = np.full((20, 20, 3), (200, 100, 50), dtype=np.uint8)
    result = _geometry_and_intensity(image, semantic, 10.0)
    assert np.isclose(result["cartilage_area_mm2"], 0.01)
    assert result["od_blue_median"] > result["od_green_median"] > result["od_red_median"]
