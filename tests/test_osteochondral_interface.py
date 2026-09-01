import numpy as np

from nostos.validation.osteochondral_interface import (
    InterfaceParameters,
    band_measurements,
    band_iou,
    boundary_metrics,
    estimate_interface,
    mask_from_interface,
    reference_interface,
    robust_normalize,
)


def _synthetic() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = 160, 128
    x = np.arange(width)
    path = 96 + 7 * np.sin(2 * np.pi * x / width)
    rows = np.arange(height)[:, None]
    image = 0.2 + 0.55 * (rows >= path[None, :])
    image += 0.04 * np.cos(x / 9)[None, :]
    mask = rows >= path[None, :]
    return image.astype(float), mask, path


def test_reference_and_boundary_metrics_are_in_physical_units() -> None:
    _, mask, _ = _synthetic()
    truth = reference_interface(mask)
    shifted = truth + 3
    metrics = boundary_metrics(shifted, truth, spacing_um=3.2)
    assert np.isclose(metrics["median_absolute_error_um"], 9.6)
    assert metrics["within_15_um"] == 1.0
    assert band_iou(truth, truth, spacing_um=3.2) == 1.0


def test_estimator_recovers_a_smooth_step_interface() -> None:
    image, mask, _ = _synthetic()
    params = InterfaceParameters(1.0, 0.25, 0.1, 1)
    prediction, confidence = estimate_interface(image, params)
    truth = reference_interface(mask)
    assert np.median(np.abs(prediction - truth)) <= 3.0
    assert np.isfinite(confidence)
    rebuilt = mask_from_interface(prediction, image.shape[0])
    assert rebuilt.shape == mask.shape
    features = band_measurements(image, truth, spacing_um=3.2)
    assert len(features) == 6
    assert all(np.isfinite(list(features.values())))


def test_flat_image_abstains_at_normalization() -> None:
    with np.testing.assert_raises(ValueError):
        robust_normalize(np.ones((64, 64)))
