import numpy as np
import pytest
from scipy.ndimage import shift

from nostos.features.dynamic import analyze_dense_deformation, analyze_time_series


def _spot() -> np.ndarray:
    yy, xx = np.mgrid[:64, :64]
    return np.exp(-((yy - 31.0) ** 2 + (xx - 29.0) ** 2) / (2 * 4.0**2))


def test_phase_translation_has_calibrated_displacement() -> None:
    image = _spot()
    series = np.stack([image, shift(image, (3, -5), order=0, mode="wrap")])
    result = analyze_time_series(series, spacing=(2.0, 4.0), temporal_spacing=0.5)
    responses = {response.measurement: response for response in result.responses}
    assert responses["displacement_y"].values == (6.0,)
    assert responses["displacement_x"].values == (-20.0,)
    assert result.calibration.temporal_spacing == 0.5
    assert result.status == "valid"


def test_constant_series_abstains() -> None:
    result = analyze_time_series(np.ones((2, 32, 32)), spacing=(1.0, 1.0), temporal_spacing=1.0)
    assert result.status == "abstain"
    assert result.abstentions[0].code == "DYNAMIC_LOW_INFORMATION"


def test_dense_deformation_is_calibrated_and_reports_reliability() -> None:
    rng = np.random.default_rng(7)
    image = rng.normal(size=(96, 96))
    from scipy.ndimage import gaussian_filter
    image = gaussian_filter(image, 1.5)
    series = np.stack([image, shift(image, (2, -3), order=1, mode="reflect")])
    result = analyze_dense_deformation(
        series, spacing=(2.0, 4.0), temporal_spacing=0.5, field_stride=4,
    )
    responses = {response.measurement: response for response in result.responses}
    dy = np.asarray(responses["dense_displacement_y"].values)
    dx = np.asarray(responses["dense_displacement_x"].values)
    eligible = np.asarray(responses["dense_eligible"].values, dtype=bool)
    assert result.status == "valid"
    assert np.median(dy[eligible]) == pytest.approx(4.0, abs=0.5)
    assert np.median(dx[eligible]) == pytest.approx(-12.0, abs=0.8)
    assert responses["dense_displacement_y"].uncertainty is not None
    assert np.isfinite(responses["dense_displacement_y"].uncertainty).all()


def test_dense_deformation_constant_pair_abstains() -> None:
    result = analyze_dense_deformation(
        np.ones((2, 64, 64)), spacing=(1.0, 1.0), temporal_spacing=1.0,
    )
    assert result.status == "abstain"
    assert result.abstentions[0].code == "DENSE_DEFORMATION_LOW_INFORMATION"
