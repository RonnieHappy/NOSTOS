"""Training-free object linkage for calibrated microscopy time series."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.ndimage import map_coordinates
from scipy.optimize import linear_sum_assignment
from skimage.registration import optical_flow_tvl1
from skimage.transform import resize


@dataclass(frozen=True)
class TrackedObject:
    frame: int
    local_id: int
    centroid_y: float
    centroid_x: float
    area_pixels: int
    equivalent_radius_pixels: float


@dataclass(frozen=True)
class TrackEdge:
    frame: int
    parent_local_id: int
    child_local_id: int
    edge_type: str
    cost: float
    confidence: float
    displacement_y: float
    displacement_x: float
    speed: float


def extract_objects(labels: np.ndarray, frame: int) -> tuple[list[TrackedObject], list[np.ndarray]]:
    """Extract objects while discarding source label identity and ordering spatially."""
    data = np.asarray(labels)
    if data.ndim != 2:
        raise ValueError("Object tracking currently requires 2-D instance masks.")
    objects = []
    coordinates = []
    for source_label in np.unique(data):
        if source_label == 0:
            continue
        coords = np.argwhere(data == source_label)
        if coords.size == 0:
            continue
        centroid = coords.mean(axis=0); area = int(coords.shape[0])
        objects.append((float(centroid[0]), float(centroid[1]), area, coords))
    objects.sort(key=lambda item: (item[0], item[1], item[2]))
    records, ordered_coords = [], []
    for local_id, (cy, cx, area, coords) in enumerate(objects, start=1):
        records.append(TrackedObject(frame, local_id, cy, cx, area, float(np.sqrt(area / np.pi))))
        ordered_coords.append(coords)
    return records, ordered_coords


def centroid_flow(reference: np.ndarray, moving: np.ndarray, centroids: np.ndarray, downsample: int = 4) -> np.ndarray:
    """Estimate dense flow on a declared coarse grid and sample at object centroids."""
    if downsample < 1:
        raise ValueError("downsample must be positive.")
    shape = tuple(max(32, int(np.ceil(size / downsample))) for size in reference.shape)
    first = resize(reference, shape, preserve_range=True, anti_aliasing=True).astype(np.float32)
    second = resize(moving, shape, preserve_range=True, anti_aliasing=True).astype(np.float32)
    first_range = float(np.percentile(first, 99) - np.percentile(first, 1))
    second_range = float(np.percentile(second, 99) - np.percentile(second, 1))
    if min(first_range, second_range) <= np.finfo(np.float32).eps:
        return np.zeros((len(centroids), 2), dtype=float)
    first = np.clip((first - np.percentile(first, 1)) / first_range, 0, 1)
    second = np.clip((second - np.percentile(second, 1)) / second_range, 0, 1)
    flow = np.asarray(optical_flow_tvl1(first, second, prefilter=True), dtype=float)
    scale_y = reference.shape[0] / shape[0]; scale_x = reference.shape[1] / shape[1]
    sample = np.stack((centroids[:, 0] / scale_y, centroids[:, 1] / scale_x))
    return np.column_stack((
        map_coordinates(flow[0], sample, order=1, mode="nearest") * scale_y,
        map_coordinates(flow[1], sample, order=1, mode="nearest") * scale_x,
    ))


def _translated_iou(parent_coords: np.ndarray, child_labels: np.ndarray, child_source_label: int, displacement: np.ndarray) -> float:
    shifted = np.rint(parent_coords + displacement).astype(int)
    inside = ((shifted[:, 0] >= 0) & (shifted[:, 0] < child_labels.shape[0])
              & (shifted[:, 1] >= 0) & (shifted[:, 1] < child_labels.shape[1]))
    shifted = shifted[inside]
    intersection = int(np.sum(child_labels[shifted[:, 0], shifted[:, 1]] == child_source_label)) if len(shifted) else 0
    child_area = int(np.sum(child_labels == child_source_label))
    union = len(parent_coords) + child_area - intersection
    return float(intersection / union) if union else 0.0


def link_frame_pair(
    parent_labels: np.ndarray,
    child_labels: np.ndarray,
    *,
    frame: int,
    spacing: tuple[float, float],
    temporal_spacing: float,
    parent_image: np.ndarray | None = None,
    child_image: np.ndarray | None = None,
    weights: tuple[float, float, float] = (1.0, 0.35, 0.75),
    use_flow: bool = True,
    allow_divisions: bool = True,
    precomputed_flow: np.ndarray | None = None,
    division_combined_area_range: tuple[float, float] = (0.5, 2.0),
    division_child_area_range: tuple[float, float] = (0.0, 4.0),
    division_balance_max: float = float("inf"),
    division_distance_radii: float = 6.0,
    division_separation_radii: float = 6.0,
) -> dict[str, Any]:
    parents, parent_coords = extract_objects(parent_labels, frame)
    children, child_coords = extract_objects(child_labels, frame + 1)
    if not parents or not children:
        return {"parents": parents, "children": children, "edges": [], "abstention": "FRAME_WITHOUT_VALID_OBJECTS"}
    parent_centroids = np.asarray([(p.centroid_y, p.centroid_x) for p in parents])
    if precomputed_flow is not None:
        predicted_flow = np.asarray(precomputed_flow, dtype=float)
        if predicted_flow.shape != parent_centroids.shape:
            raise ValueError("Precomputed centroid flow must match the parent-object count.")
    elif use_flow and parent_image is not None and child_image is not None:
        predicted_flow = centroid_flow(parent_image, child_image, parent_centroids)
    else:
        predicted_flow = np.zeros_like(parent_centroids)
    child_centroids = np.asarray([(c.centroid_y, c.centroid_x) for c in children])
    child_source_labels = [int(child_labels[coords[0, 0], coords[0, 1]]) for coords in child_coords]
    cost = np.full((len(parents), len(children)), 1e6, dtype=float)
    for i, parent in enumerate(parents):
        predicted = parent_centroids[i] + predicted_flow[i]
        radius = max(parent.equivalent_radius_pixels, 1.0)
        for j, child in enumerate(children):
            distance = float(np.linalg.norm(child_centroids[j] - predicted)) / max(radius, child.equivalent_radius_pixels, 1.0)
            ratio = child.area_pixels / parent.area_pixels
            if distance > 6.0 or not 0.25 <= ratio <= 4.0:
                continue
            overlap = 0.0 if weights[2] == 0 else _translated_iou(parent_coords[i], child_labels, child_source_labels[j], predicted_flow[i])
            cost[i, j] = weights[0] * distance + weights[1] * abs(float(np.log(ratio))) + weights[2] * (1.0 - overlap)
    rows, cols = linear_sum_assignment(cost)
    assignments = {int(i): int(j) for i, j in zip(rows, cols, strict=True) if cost[i, j] < 1e5}
    unmatched_children = set(range(len(children))) - set(assignments.values())
    division_pairs: dict[int, tuple[int, int]] = {}
    if allow_divisions and unmatched_children:
        for i, matched_child in list(assignments.items()):
            parent = parents[i]; radius = max(parent.equivalent_radius_pixels, 1.0); predicted = parent_centroids[i] + predicted_flow[i]
            candidates = []
            for other in unmatched_children:
                pair = (matched_child, other); combined = sum(children[j].area_pixels for j in pair) / parent.area_pixels
                distances = [np.linalg.norm(child_centroids[j] - predicted) / radius for j in pair]
                separation = np.linalg.norm(child_centroids[pair[0]] - child_centroids[pair[1]]) / radius
                child_ratios = [children[j].area_pixels / parent.area_pixels for j in pair]
                balance = max(child_ratios) / max(min(child_ratios), np.finfo(float).eps)
                if (division_combined_area_range[0] <= combined <= division_combined_area_range[1]
                        and all(division_child_area_range[0] <= value <= division_child_area_range[1] for value in child_ratios)
                        and balance <= division_balance_max and max(distances) <= division_distance_radii
                        and separation <= division_separation_radii):
                    candidates.append((sum(distances) + abs(np.log(combined)), other))
            if candidates:
                _, other = min(candidates); division_pairs[i] = (matched_child, other); unmatched_children.remove(other)
    edges: list[TrackEdge] = []
    for i, j in assignments.items():
        pair = division_pairs.get(i)
        child_indices = pair if pair is not None else (j,)
        for child_index in child_indices:
            displacement_pixels = child_centroids[child_index] - parent_centroids[i]
            physical = displacement_pixels * np.asarray(spacing)
            edge_cost = float(cost[i, j]) if child_index == j else float(np.linalg.norm(child_centroids[child_index] - (parent_centroids[i] + predicted_flow[i])) / max(parents[i].equivalent_radius_pixels, 1.0))
            edges.append(TrackEdge(
                frame, parents[i].local_id, children[child_index].local_id,
                "division" if pair is not None else "continuation", edge_cost, float(np.exp(-edge_cost)),
                float(physical[0]), float(physical[1]), float(np.linalg.norm(physical) / temporal_spacing),
            ))
    return {"parents": parents, "children": children, "edges": edges, "abstention": None}


def track_instance_series(
    masks: np.ndarray,
    *,
    spacing: tuple[float, float],
    temporal_spacing: float,
    images: np.ndarray | None = None,
    weights: tuple[float, float, float] = (1.0, 0.35, 0.75),
    use_flow: bool = True,
    allow_divisions: bool = True,
    precomputed_flows: list[np.ndarray] | None = None,
    division_parameters: dict[str, Any] | None = None,
    spatial_unit: str = "um",
    temporal_unit: str = "min",
) -> dict[str, Any]:
    data = np.asarray(masks)
    if data.ndim != 3 or data.shape[0] < 2:
        raise ValueError("Tracking requires instance masks with shape (time, y, x).")
    if images is not None and np.asarray(images).shape != data.shape:
        raise ValueError("Images must match the instance-mask series shape.")
    if len(spacing) != 2 or temporal_spacing <= 0 or any(value <= 0 for value in spacing):
        raise ValueError("Positive spatial and temporal calibration is required.")
    frame_results = []
    for frame in range(data.shape[0] - 1):
        division_options = {} if division_parameters is None else division_parameters
        frame_results.append(link_frame_pair(
            data[frame], data[frame + 1], frame=frame, spacing=spacing, temporal_spacing=temporal_spacing,
            parent_image=None if images is None else images[frame], child_image=None if images is None else images[frame + 1],
            weights=weights, use_flow=use_flow, allow_divisions=allow_divisions,
            precomputed_flow=None if precomputed_flows is None else precomputed_flows[frame],
            **division_options,
        ))
    edges = [asdict(edge) for result in frame_results for edge in result["edges"]]
    abstentions = [{"frame": index, "code": result["abstention"]} for index, result in enumerate(frame_results) if result["abstention"]]
    return {
        "schema_version": "nostos-tracking/1.0", "input_dimensions": list(data.shape),
        "calibration": {"spacing": list(spacing), "spatial_unit": spatial_unit, "temporal_spacing": temporal_spacing, "temporal_unit": temporal_unit},
        "method": {"weights": list(weights), "use_flow": use_flow, "allow_divisions": allow_divisions,
                   "division_parameters": division_parameters or {}, "assignment": "Hungarian", "source_labels_discarded": True},
        "edges": edges, "abstentions": abstentions,
        "status": "valid" if edges and not abstentions else ("review" if edges else "abstain"),
    }
