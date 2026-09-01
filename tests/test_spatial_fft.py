import numpy as np
import pytest

from nostos.features.spatial_fft import extract_spatial_fft


def _stripes(angle_degrees: float, size: int = 256, period: float = 16.0) -> np.ndarray:
    y, x = np.mgrid[:size, :size]
    angle = np.deg2rad(angle_degrees)
    normal_coordinate = -x * np.sin(angle) + y * np.cos(angle)
    return np.sin(2 * np.pi * normal_coordinate / period)


def _axial_difference(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def test_fft_recovers_stripe_orientation() -> None:
    features = extract_spatial_fft(_stripes(35.0), pixel_size_um=1.71)
    assert _axial_difference(features.orientation_degrees, 35.0) < 2.0
    assert features.anisotropy > 0.8
    assert features.angular_entropy < 0.5


def test_rotation_changes_angle_but_preserves_scalar_order_features() -> None:
    image = _stripes(20.0)
    first = extract_spatial_fft(image, pixel_size_um=1.71)
    second = extract_spatial_fft(np.rot90(image), pixel_size_um=1.71)
    assert _axial_difference(second.orientation_degrees, first.orientation_degrees + 90.0) < 2.0
    assert abs(first.anisotropy - second.anisotropy) < 0.02
    assert abs(first.angular_entropy - second.angular_entropy) < 0.02


def test_common_physical_frequency_band_is_sampling_invariant() -> None:
    coarse_spacing = 0.10
    fine_spacing = 0.05
    period_um = 1.6
    coarse_y, coarse_x = np.mgrid[:128, :128]
    fine_y, fine_x = np.mgrid[:256, :256]
    coarse = np.sin(2 * np.pi * coarse_x * coarse_spacing / period_um)
    fine = np.sin(2 * np.pi * fine_x * fine_spacing / period_um)
    common_band = (100.0, 4_500.0)
    coarse_features = extract_spatial_fft(
        coarse,
        pixel_size_um=coarse_spacing,
        frequency_band_cycles_per_mm=common_band,
    )
    fine_features = extract_spatial_fft(
        fine,
        pixel_size_um=fine_spacing,
        frequency_band_cycles_per_mm=common_band,
    )
    relative_difference = abs(
        coarse_features.characteristic_frequency_cycles_per_mm
        - fine_features.characteristic_frequency_cycles_per_mm
    ) / fine_features.characteristic_frequency_cycles_per_mm
    assert relative_difference < 0.02
    assert coarse_features.analysis_min_frequency_cycles_per_mm == common_band[0]
    assert fine_features.analysis_max_frequency_cycles_per_mm == common_band[1]


def test_physical_frequency_band_cannot_exceed_nyquist() -> None:
    with pytest.raises(ValueError, match="exceeds the image Nyquist"):
        extract_spatial_fft(
            _stripes(35.0),
            pixel_size_um=1.0,
            frequency_band_cycles_per_mm=(10.0, 600.0),
        )
