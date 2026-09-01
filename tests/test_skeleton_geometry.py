from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage.draw import line

from nostos.features.skeleton_geometry import skeleton_geometry_response


def _stroke(points: list[tuple[int, int]], shape: tuple[int, int] = (96, 96), radius: int = 1) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    for start, stop in zip(points[:-1], points[1:], strict=True):
        rr, cc = line(start[0], start[1], stop[0], stop[1])
        mask[rr, cc] = True
    if radius:
        mask = ndimage.binary_dilation(mask, iterations=radius)
    return mask


def test_straight_segment_recovers_orientation_straightness_and_width() -> None:
    mask = np.zeros((64, 80), dtype=bool)
    mask[30:35, 10:70] = True
    result = skeleton_geometry_response(mask, spacing_um=(1.0, 1.0))
    assert result.component_count == 1
    assert result.endpoint_count == 2
    assert result.segment_count == 1
    assert result.median_segment_straightness is not None
    assert result.median_segment_straightness > 0.99
    assert result.median_local_width_um is not None
    assert abs(result.median_local_width_um - 5.0) <= 0.25
    orientation = result.segments[0].axial_orientation_degrees
    assert min(abs(orientation), abs(orientation - 180.0)) < 1.0


def test_curved_arc_is_longer_and_less_straight_than_its_chord() -> None:
    angles = np.linspace(np.pi, 1.5 * np.pi, 32)
    points = [(int(round(48 + 28 * np.sin(angle))), int(round(48 + 28 * np.cos(angle)))) for angle in angles]
    mask = _stroke(points, radius=1)
    result = skeleton_geometry_response(mask, spacing_um=(0.5, 0.5))
    longest = max((segment for segment in result.segments if not segment.is_cycle), key=lambda item: item.geodesic_length_um)
    assert longest.geodesic_length_um > longest.chord_length_um
    assert 0.70 < longest.straightness < 0.95


def test_y_network_counts_three_arms_and_one_junction_region() -> None:
    mask = _stroke([(48, 48), (18, 20)], radius=0)
    mask |= _stroke([(48, 48), (18, 76)], radius=0)
    mask |= _stroke([(48, 48), (82, 48)], radius=0)
    result = skeleton_geometry_response(mask, spacing_um=(1.0, 1.0))
    assert result.component_count == 1
    assert result.endpoint_count == 3
    assert result.junction_count == 1
    assert result.segment_count == 3


def test_anisotropic_spacing_changes_physical_length_not_pixel_topology() -> None:
    mask = np.zeros((48, 48), dtype=bool)
    mask[8:40, 24] = True
    isotropic = skeleton_geometry_response(mask, spacing_um=(1.0, 1.0))
    anisotropic = skeleton_geometry_response(mask, spacing_um=(2.0, 1.0))
    assert isotropic.skeleton_pixels == anisotropic.skeleton_pixels
    assert np.isclose(anisotropic.total_segment_length_um, 2.0 * isotropic.total_segment_length_um)


def test_closed_cycle_is_reported_but_not_misrepresented_as_straight_fiber() -> None:
    yy, xx = np.ogrid[:80, :80]
    radius = np.sqrt((yy - 40) ** 2 + (xx - 40) ** 2)
    mask = (radius >= 19) & (radius <= 21)
    result = skeleton_geometry_response(mask, spacing_um=(1.0, 1.0))
    assert result.cycle_count >= 1
    assert result.segment_count == 0
    assert result.median_segment_straightness is None

