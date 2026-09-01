import numpy as np
import pytest

from nostos.features.zsd import axial_difference_degrees, extract_zsd_tiles, summarize_zsd_tiles


def test_axial_difference_wraps_at_180_degrees():
    assert axial_difference_degrees(175, 5) == 10
    assert axial_difference_degrees(10, 100) == 90


def test_zsd_extraction_respects_segmented_depth():
    size = 160
    y, x = np.mgrid[:size, :size]
    image = (127 + 60 * np.sin(2 * np.pi * x / 12)).astype(np.uint8)
    labels = np.zeros((size, size), dtype=np.uint8)
    labels[10:140, 10:150] = 1
    labels[140:150, 10:150] = 2
    rows = extract_zsd_tiles(
        image,
        labels,
        pixel_size_um=10,
        tile_size=64,
        overlap_fraction=0.5,
        minimum_cartilage_fraction=0.6,
        boundary_exclusion_um=10,
    )
    assert rows
    summary = summarize_zsd_tiles(rows)
    assert summary["valid_tile_count"] == len(rows)


def test_relative_orientation_is_invariant_to_joint_section_rotation():
    size = 192
    _, x = np.mgrid[:size, :size]
    image = (127 + 60 * np.sin(2 * np.pi * x / 12)).astype(np.uint8)
    labels = np.zeros((size, size), dtype=np.uint8)
    labels[12:168, 12:180] = 1
    labels[168:180, 12:180] = 2
    options = dict(
        pixel_size_um=10,
        tile_size=64,
        overlap_fraction=0.5,
        minimum_cartilage_fraction=0.6,
        boundary_exclusion_um=10,
    )
    original = extract_zsd_tiles(image, labels, **options)
    rotated = extract_zsd_tiles(np.rot90(image), np.rot90(labels), **options)
    original_relative = np.median([row["fft_relative_to_depth_degrees"] for row in original])
    rotated_relative = np.median([row["fft_relative_to_depth_degrees"] for row in rotated])
    assert rotated_relative == pytest.approx(original_relative, abs=2)
