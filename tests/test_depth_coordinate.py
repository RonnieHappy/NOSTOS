import numpy as np

from nostos.features.depth import cartilage_depth_coordinate, summarize_depth_bands


def test_depth_coordinate_runs_surface_to_deep_in_physical_space():
    labels = np.zeros((12, 10), dtype=np.uint8)
    labels[2:9, 2:8] = 1
    labels[9:11, 2:8] = 2
    coordinate = cartilage_depth_coordinate(labels, pixel_size_um=10, boundary_exclusion_um=10)
    assert np.nanmean(coordinate.normalized_depth[2]) < 0.1
    assert np.nanmean(coordinate.normalized_depth[8]) > 0.8
    assert not coordinate.eligible_cartilage[2].any()
    assert coordinate.eligible_cartilage[5].any()


def test_depth_band_summary_uses_prespecified_edges():
    depth = np.array([0.05, 0.2, 0.5, 0.9])
    values = np.array([1.0, 2.0, 3.0, 4.0])
    summary = summarize_depth_bands(depth, values)
    assert summary["depth_0.00_0.10"] == 1.0
    assert summary["depth_0.30_0.70"] == 3.0
