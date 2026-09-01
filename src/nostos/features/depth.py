from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt


@dataclass(frozen=True)
class DepthCoordinate:
    normalized_depth: np.ndarray
    eligible_cartilage: np.ndarray
    surface_boundary: np.ndarray
    deep_boundary: np.ndarray


def cartilage_depth_coordinate(
    labels: np.ndarray,
    *,
    pixel_size_um: float,
    boundary_exclusion_um: float = 100.0,
    cartilage_label: int = 1,
    calcified_label: int = 2,
    background_label: int = 0,
) -> DepthCoordinate:
    """Create a curvature-aware 0-to-1 coordinate between surface and deep boundaries.

    Depth is the relative Euclidean distance to the two independently identified
    interfaces: d(surface)/(d(surface)+d(deep)). It is undefined outside cartilage.
    """
    labels = np.asarray(labels)
    if labels.ndim != 2 or pixel_size_um <= 0 or boundary_exclusion_um < 0:
        raise ValueError("labels must be 2-D and physical scales must be valid")
    cartilage = labels == cartilage_label
    if not cartilage.any():
        raise ValueError("no articular cartilage pixels found")
    neighborhood = np.ones((3, 3), dtype=bool)
    surface = cartilage & binary_dilation(labels == background_label, structure=neighborhood)
    deep = cartilage & binary_dilation(labels == calcified_label, structure=neighborhood)
    if not surface.any() or not deep.any():
        raise ValueError("both surface/background and deep/calcified interfaces are required")
    distance_surface = distance_transform_edt(~surface) * pixel_size_um
    distance_deep = distance_transform_edt(~deep) * pixel_size_um
    denominator = distance_surface + distance_deep
    valid_cartilage = cartilage & (denominator > 0)
    normalized = np.full(labels.shape, np.nan, dtype=np.float32)
    normalized[valid_cartilage] = (
        distance_surface[valid_cartilage] / denominator[valid_cartilage]
    ).astype(np.float32)
    eligible = valid_cartilage & (distance_surface >= boundary_exclusion_um) & (
        distance_deep >= boundary_exclusion_um
    )
    return DepthCoordinate(normalized, eligible, surface, deep)


def summarize_depth_bands(
    depth: np.ndarray,
    values: np.ndarray,
    *,
    edges: tuple[float, ...] = (0.0, 0.1, 0.3, 0.7, 1.0),
) -> dict[str, float]:
    depth, values = np.asarray(depth), np.asarray(values, dtype=float)
    if depth.shape != values.shape or len(edges) < 2 or any(b <= a for a, b in zip(edges, edges[1:])):
        raise ValueError("depth/values must match and edges must increase")
    result: dict[str, float] = {}
    for lower, upper in zip(edges, edges[1:]):
        selected = np.isfinite(depth) & np.isfinite(values) & (depth >= lower) & (
            depth <= upper if upper == edges[-1] else depth < upper
        )
        result[f"depth_{lower:.2f}_{upper:.2f}"] = float(np.mean(values[selected])) if selected.any() else float("nan")
    return result
