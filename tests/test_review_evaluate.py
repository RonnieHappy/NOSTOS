from __future__ import annotations

import numpy as np

from nostos.segmentation.review_evaluate import evaluate_case


def test_identical_cartilage_masks_have_perfect_geometry_and_feature_agreement() -> None:
    yy, xx = np.mgrid[:128, :128]
    image = np.stack(((xx + yy) % 255, xx % 255, yy % 255), axis=-1).astype(np.uint8)
    mask = np.zeros((128, 128), dtype=bool)
    mask[16:112, 10:118] = True
    result = evaluate_case(image, mask, mask, spacing_um=2.0, tile_size_um=64.0)
    assert result["dice"] == 1.0
    assert result["iou"] == 1.0
    assert result["surface_hd95_um"] == 0.0
    assert result["articular_surface_median_error_um"] == 0.0
    assert result["tidemark_median_error_um"] == 0.0
    assert result["tile_agreement"] == 1.0
    assert result["angular_entropy_absolute_difference"] == 0.0


def test_boundary_shift_is_reported_in_physical_units() -> None:
    image = np.repeat(np.arange(128, dtype=np.uint8)[None, :, None], 128, axis=0)
    image = np.repeat(image, 3, axis=2)
    proposal = np.zeros((128, 128), dtype=bool)
    reference = np.zeros_like(proposal)
    proposal[20:100, 16:112] = True
    reference[25:105, 16:112] = True
    result = evaluate_case(image, proposal, reference, spacing_um=3.0, tile_size_um=96.0)
    assert result["articular_surface_median_error_um"] == 15.0
    assert result["tidemark_median_error_um"] == 15.0
    assert result["dice"] < 1.0
