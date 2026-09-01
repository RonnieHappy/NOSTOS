from __future__ import annotations

from dataclasses import asdict

import numpy as np

from nostos.data.tiles import iter_tiles

from .baselines import cooccurrence_features, structure_tensor_features
from .depth import cartilage_depth_coordinate
from .spatial_fft import extract_spatial_fft


def axial_difference_degrees(first: float, second: float) -> float:
    """Smallest difference between two unoriented axes, in [0, 90]."""
    return float(abs((first - second + 90.0) % 180.0 - 90.0))


def extract_zsd_tiles(
    image: np.ndarray,
    labels: np.ndarray,
    *,
    pixel_size_um: float,
    tile_size: int = 512,
    overlap_fraction: float = 0.5,
    minimum_cartilage_fraction: float = 0.8,
    boundary_exclusion_um: float = 100.0,
) -> list[dict[str, float | int]]:
    coordinate = cartilage_depth_coordinate(
        labels, pixel_size_um=pixel_size_um, boundary_exclusion_um=boundary_exclusion_um
    )
    gradient_y, gradient_x = np.gradient(coordinate.normalized_depth.astype(np.float64))
    rows: list[dict[str, float | int]] = []
    for tile in iter_tiles(
        image,
        coordinate.eligible_cartilage,
        tile_size=tile_size,
        overlap_fraction=overlap_fraction,
        minimum_tissue_fraction=minimum_cartilage_fraction,
    ):
        region = np.s_[tile.row : tile.row + tile.height, tile.column : tile.column + tile.width]
        eligible = coordinate.eligible_cartilage[region]
        depth = coordinate.normalized_depth[region]
        gx, gy = gradient_x[region][eligible], gradient_y[region][eligible]
        valid_gradient = np.isfinite(gx) & np.isfinite(gy) & (np.hypot(gx, gy) > 0)
        if not valid_gradient.any():
            continue
        # Double-angle averaging respects the axial (180-degree) nature of direction.
        angles = np.arctan2(gy[valid_gradient], gx[valid_gradient])
        depth_axis = float(np.mod(0.5 * np.angle(np.mean(np.exp(2j * angles))), np.pi) * 180 / np.pi)
        fft = extract_spatial_fft(tile.image, pixel_size_um=pixel_size_um)
        tensor = structure_tensor_features(tile.image)
        cooccurrence = cooccurrence_features(tile.image)
        row: dict[str, float | int] = {
            "row": tile.row,
            "column": tile.column,
            "cartilage_fraction": tile.tissue_fraction,
            "normalized_depth": float(np.nanmean(depth[eligible])),
            "depth_axis_degrees": depth_axis,
            "fft_relative_to_depth_degrees": axial_difference_degrees(fft.orientation_degrees, depth_axis),
        }
        row.update({f"fft_{key}": value for key, value in asdict(fft).items()})
        row.update({f"tensor_{key}": value for key, value in asdict(tensor).items()})
        row.update({f"glcm_{key}": value for key, value in asdict(cooccurrence).items()})
        rows.append(row)
    return rows


def summarize_zsd_tiles(
    rows: list[dict[str, float | int]],
    *,
    edges: tuple[float, ...] = (0.0, 0.1, 0.3, 0.7, 1.0),
) -> dict[str, float]:
    if not rows:
        return {"valid_tile_count": 0.0}
    feature_names = [
        "fft_anisotropy",
        "fft_angular_entropy",
        "fft_spectral_slope",
        "fft_characteristic_frequency_cycles_per_mm",
        "fft_relative_to_depth_degrees",
    ]
    summary: dict[str, float] = {"valid_tile_count": float(len(rows))}
    depth = np.asarray([row["normalized_depth"] for row in rows], dtype=float)
    for name in feature_names:
        values = np.asarray([row[name] for row in rows], dtype=float)
        for lower, upper in zip(edges, edges[1:]):
            selected = (depth >= lower) & (depth <= upper if upper == edges[-1] else depth < upper)
            summary[f"{name}__depth_{lower:.2f}_{upper:.2f}"] = (
                float(np.mean(values[selected])) if selected.any() else float("nan")
            )
        summary[f"{name}__depth_slope"] = float(np.polyfit(depth, values, 1)[0]) if len(rows) >= 2 else float("nan")
    return summary

