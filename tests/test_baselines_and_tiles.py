import numpy as np

from nostos.data.tiles import iter_tiles
from nostos.features.baselines import cooccurrence_features, structure_tensor_features


def _stripes(angle_degrees: float, size: int = 256, period: float = 16.0) -> np.ndarray:
    y, x = np.mgrid[:size, :size]
    angle = np.deg2rad(angle_degrees)
    normal_coordinate = -x * np.sin(angle) + y * np.cos(angle)
    return np.sin(2 * np.pi * normal_coordinate / period)


def _axial_difference(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def test_structure_tensor_recovers_orientation() -> None:
    features = structure_tensor_features(_stripes(55.0))
    assert _axial_difference(features.orientation_degrees, 55.0) < 2.0
    assert features.coherence > 0.9


def test_cooccurrence_features_are_finite() -> None:
    features = cooccurrence_features(_stripes(0.0))
    assert all(np.isfinite(value) for value in features.__dict__.values())


def test_tiling_uses_shared_tissue_gate() -> None:
    image = np.zeros((128, 128), dtype=float)
    mask = np.zeros_like(image, dtype=bool)
    mask[:64, :64] = True
    tiles = list(
        iter_tiles(
            image,
            mask,
            tile_size=64,
            overlap_fraction=0.0,
            minimum_tissue_fraction=0.8,
        )
    )
    assert [(tile.row, tile.column) for tile in tiles] == [(0, 0)]
