import numpy as np

from nostos.evaluation.mask_uncertainty import perturb_cartilage_mask, zsd_mask_sensitivity


def _example():
    size = 128
    _, x = np.mgrid[:size, :size]
    image = 120 + 50 * np.sin(2 * np.pi * x / 10)
    labels = np.zeros((size, size), dtype=np.uint8)
    labels[8:110, 8:120] = 1
    labels[110:120, 8:120] = 2
    return image, labels


def test_physical_mask_erosion_and_dilation_change_cartilage_area():
    _, labels = _example()
    eroded = perturb_cartilage_mask(labels, delta_um=-20, pixel_size_um=10)
    dilated = perturb_cartilage_mask(labels, delta_um=20, pixel_size_um=10)
    assert np.sum(eroded == 1) < np.sum(labels == 1) < np.sum(dilated == 1)


def test_zsd_mask_sensitivity_preserves_failed_variants():
    image, labels = _example()
    rows = zsd_mask_sensitivity(
        image,
        labels,
        pixel_size_um=10,
        deltas_um=(-10, 0, 10),
        tile_size=32,
        overlap_fraction=0.5,
        minimum_cartilage_fraction=0.5,
        boundary_exclusion_um=10,
    )
    assert [row["delta_um"] for row in rows] == [-10, 0, 10]
    assert all("success" in row for row in rows)
