import numpy as np

from nostos.features.depth_atlas import (
    AtlasConfig,
    axial_difference_degrees,
    extract_depth_atlas,
)


def _layered_section(height=256, width=512):
    labels = np.zeros((height, width), dtype=np.uint8)
    labels[24:216, 16:-16] = 1
    labels[216:232, 16:-16] = 2
    labels[232:, 16:-16] = 3
    y, x = np.mgrid[:height, :width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    superficial = 127 + 90 * np.sin(2 * np.pi * y / 12)
    deep = 127 + 90 * np.sin(2 * np.pi * x / 12)
    gray = np.where(y < 100, superficial, deep)
    image[:] = np.clip(gray[..., None], 0, 255)
    return image, labels


def test_axial_difference_wraps_at_180():
    assert axial_difference_degrees(175, 5) == 10
    assert axial_difference_degrees(10, 100) == 90


def test_depth_atlas_detects_zonal_orientation_change():
    image, labels = _layered_section()
    config = AtlasConfig(
        tile_size_um=64,
        stride_fraction=0.5,
        minimum_cartilage_fraction=0.70,
        boundary_exclusion_um=2,
        depth_edges=(0.0, 0.4, 1.0),
        minimum_tiles_per_band=1,
    )
    tiles, profile, qc = extract_depth_atlas(image, labels, pixel_size_um=1.0, config=config)
    assert len(tiles) > 10
    assert qc["section_qc_pass"]
    shallow = profile.iloc[0].fft_tangent_deviation_degrees_median
    deep = profile.iloc[1].fft_tangent_deviation_degrees_median
    assert abs(shallow - deep) > 45
    assert qc["median_fft_tensor_disagreement_degrees"] < 5


def test_depth_atlas_configuration_requires_complete_depth_range():
    try:
        AtlasConfig(depth_edges=(0.1, 0.5, 1.0)).validate()
    except ValueError as error:
        assert "span 0 to 1" in str(error)
    else:
        raise AssertionError("invalid depth range was accepted")
