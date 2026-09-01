"""Calibrated two-dimensional skeleton-segment geometry.

The module measures geometry from a supplied binary support.  It deliberately
does not claim that the support is a biologically correct segmentation; image
adapters must provide their own validity record.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize


_OFFSETS_2D = tuple(
    (dy, dx)
    for dy in (-1, 0, 1)
    for dx in (-1, 0, 1)
    if (dy, dx) != (0, 0)
)


@dataclass(frozen=True)
class SkeletonSegment:
    segment_id: int
    geodesic_length_um: float
    chord_length_um: float
    straightness: float
    axial_orientation_degrees: float
    median_width_um: float
    mean_width_um: float
    points: int
    is_cycle: bool


@dataclass(frozen=True)
class SkeletonGeometryResponse:
    spacing_um: tuple[float, float]
    foreground_pixels: int
    skeleton_pixels: int
    component_count: int
    endpoint_count: int
    junction_count: int
    cycle_count: int
    segment_count: int
    total_segment_length_um: float
    median_segment_length_um: float | None
    median_segment_straightness: float | None
    median_local_width_um: float | None
    segments: tuple[SkeletonSegment, ...]
    method: str = "skeleton_graph_8_connected_boundary_corrected_edt_v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate(mask: np.ndarray, spacing_um: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    binary = np.asarray(mask, dtype=bool)
    spacing = np.asarray(spacing_um, dtype=float)
    if binary.ndim != 2 or not binary.any():
        raise ValueError("A nonempty two-dimensional mask is required.")
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or np.any(spacing <= 0):
        raise ValueError("spacing_um must contain two finite positive values in row-column order.")
    return binary, spacing


def _adjacency(skeleton: np.ndarray) -> dict[tuple[int, int], tuple[tuple[int, int], ...]]:
    points = {tuple(int(v) for v in point) for point in np.argwhere(skeleton)}
    return {
        point: tuple(
            sorted(
                (point[0] + dy, point[1] + dx)
                for dy, dx in _OFFSETS_2D
                if (point[0] + dy, point[1] + dx) in points
            )
        )
        for point in points
    }


def _edge(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    return (a, b) if a < b else (b, a)


def _path_length(path: list[tuple[int, int]], spacing: np.ndarray) -> float:
    if len(path) < 2:
        return 0.0
    points = np.asarray(path, dtype=float)
    steps = np.diff(points, axis=0) * spacing
    return float(np.linalg.norm(steps, axis=1).sum())


def _segment(
    segment_id: int,
    path: list[tuple[int, int]],
    spacing: np.ndarray,
    width_map: np.ndarray,
    *,
    is_cycle: bool,
) -> SkeletonSegment:
    geodesic = _path_length(path, spacing)
    physical_points = np.asarray(path, dtype=float) * spacing
    vector = physical_points[-1] - physical_points[0]
    chord = 0.0 if is_cycle else float(np.linalg.norm(vector))
    straightness = 0.0 if is_cycle or geodesic <= 0 else float(np.clip(chord / geodesic, 0.0, 1.0))
    if chord > 0 and len(path) >= 2:
        covariance = np.cov(physical_points - physical_points.mean(axis=0), rowvar=False)
        principal = np.linalg.eigh(covariance)[1][:, -1]
        orientation = float(np.mod(np.degrees(np.arctan2(principal[0], principal[1])), 180.0))
    else:
        orientation = 0.0
    widths = np.asarray([width_map[point] for point in path], dtype=float)
    return SkeletonSegment(
        segment_id=segment_id,
        geodesic_length_um=geodesic,
        chord_length_um=chord,
        straightness=straightness,
        axial_orientation_degrees=orientation,
        median_width_um=float(np.median(widths)),
        mean_width_um=float(np.mean(widths)),
        points=len(path),
        is_cycle=is_cycle,
    )


def _trace_noncycle_segments(
    adjacency: dict[tuple[int, int], tuple[tuple[int, int], ...]],
    node_pixels: set[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    paths: list[list[tuple[int, int]]] = []
    for start in sorted(node_pixels):
        for neighbour in adjacency[start]:
            first_edge = _edge(start, neighbour)
            if first_edge in visited_edges:
                continue
            visited_edges.add(first_edge)
            path = [start, neighbour]
            previous, current = start, neighbour
            while current not in node_pixels:
                candidates = [point for point in adjacency[current] if point != previous]
                if not candidates:
                    break
                # Interior skeleton samples should have degree two.  In the
                # event of malformed support, deterministic ordering prevents
                # an outcome-dependent branch choice.
                following = candidates[0]
                next_edge = _edge(current, following)
                if next_edge in visited_edges:
                    break
                visited_edges.add(next_edge)
                path.append(following)
                previous, current = current, following
            if len(path) >= 2:
                paths.append(path)
    return paths


def _trace_cycles(
    adjacency: dict[tuple[int, int], tuple[tuple[int, int], ...]],
    node_pixels: set[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    remaining = {point for point in adjacency if point not in node_pixels}
    cycles: list[list[tuple[int, int]]] = []
    while remaining:
        start = min(remaining)
        component = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for neighbour in adjacency[current]:
                if neighbour in remaining and neighbour not in component:
                    component.add(neighbour)
                    stack.append(neighbour)
        remaining -= component
        if any(neighbour in node_pixels for point in component for neighbour in adjacency[point]):
            continue
        if any(len(adjacency[point]) != 2 for point in component):
            continue
        path = [start]
        previous: tuple[int, int] | None = None
        current = start
        while True:
            candidates = [point for point in adjacency[current] if point != previous]
            following = min(candidates)
            if following == start:
                path.append(start)
                break
            if following in path:
                break
            path.append(following)
            previous, current = current, following
        if len(path) > 3 and path[-1] == start:
            cycles.append(path)
    return cycles


def skeleton_geometry_response(
    mask: np.ndarray,
    *,
    spacing_um: tuple[float, float],
    minimum_segment_length_um: float = 0.0,
) -> SkeletonGeometryResponse:
    """Return segment length, straightness, orientation and local width.

    Junction and endpoint counts are counts of connected node regions rather
    than raw high-degree pixels.  This suppresses double counting where a
    digital junction occupies more than one sample.
    """

    binary, spacing = _validate(mask, spacing_um)
    if not np.isfinite(minimum_segment_length_um) or minimum_segment_length_um < 0:
        raise ValueError("minimum_segment_length_um must be finite and nonnegative.")
    skeleton = skeletonize(binary)
    adjacency = _adjacency(skeleton)
    if not adjacency:
        raise ValueError("The supplied mask does not contain a measurable skeleton.")

    degree = np.zeros(binary.shape, dtype=np.uint8)
    for point, neighbours in adjacency.items():
        degree[point] = len(neighbours)
    node_mask = skeleton & (degree != 2)
    node_labels, node_regions = ndimage.label(node_mask, structure=np.ones((3, 3), dtype=np.uint8))
    endpoint_count = 0
    junction_count = 0
    for label_id in range(1, node_regions + 1):
        values = degree[node_labels == label_id]
        endpoint_count += int(np.any(values <= 1))
        junction_count += int(np.any(values >= 3))

    # EDT measures sample-centre distance.  Subtracting half the smallest
    # spacing converts a five-sample-wide bar to a five-unit physical width.
    centre_distance = ndimage.distance_transform_edt(binary, sampling=tuple(spacing))
    width_map = 2.0 * np.maximum(centre_distance - 0.5 * float(np.min(spacing)), 0.5 * float(np.min(spacing)))

    node_pixels = {point for point, neighbours in adjacency.items() if len(neighbours) != 2}
    open_paths = _trace_noncycle_segments(adjacency, node_pixels)
    cycle_paths = _trace_cycles(adjacency, node_pixels)
    measured: list[SkeletonSegment] = []
    for path, is_cycle in [(path, False) for path in open_paths] + [(path, True) for path in cycle_paths]:
        candidate = _segment(len(measured), path, spacing, width_map, is_cycle=is_cycle)
        if candidate.geodesic_length_um >= minimum_segment_length_um:
            measured.append(candidate)

    labels, component_count = ndimage.label(skeleton, structure=np.ones((3, 3), dtype=np.uint8))
    del labels
    open_segments = [segment for segment in measured if not segment.is_cycle]
    lengths = np.asarray([segment.geodesic_length_um for segment in open_segments], dtype=float)
    straightness = np.asarray([segment.straightness for segment in open_segments], dtype=float)
    widths = np.asarray([segment.median_width_um for segment in open_segments], dtype=float)
    return SkeletonGeometryResponse(
        spacing_um=(float(spacing[0]), float(spacing[1])),
        foreground_pixels=int(binary.sum()),
        skeleton_pixels=int(skeleton.sum()),
        component_count=int(component_count),
        endpoint_count=int(endpoint_count),
        junction_count=int(junction_count),
        cycle_count=len(cycle_paths),
        segment_count=len(open_segments),
        total_segment_length_um=float(sum(segment.geodesic_length_um for segment in measured)),
        median_segment_length_um=float(np.median(lengths)) if lengths.size else None,
        median_segment_straightness=float(np.median(straightness)) if straightness.size else None,
        median_local_width_um=float(np.median(widths)) if widths.size else None,
        segments=tuple(measured),
    )


__all__ = ["SkeletonGeometryResponse", "SkeletonSegment", "skeleton_geometry_response"]
