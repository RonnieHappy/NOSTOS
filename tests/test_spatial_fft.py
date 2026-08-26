import numpy as np

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
