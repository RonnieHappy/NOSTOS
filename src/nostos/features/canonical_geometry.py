"""Canonicalize response geometry for comparison without discarding raw measurements."""
from __future__ import annotations

import numpy as np

from nostos.core.response import ResponseGeometry


def canonical_response_blocks(geometry: ResponseGeometry, *, quotient_global_rotation: bool = True) -> dict[str, np.ndarray]:
    """Return comparison blocks while retaining the original geometry unchanged.

    Global image rotation is treated as a nuisance transformation only in this
    comparison view. Absolute directions remain available in ``geometry``.
    """
    surfaces = {(surface.module, surface.measurement): np.asarray(surface.values, dtype=float) for surface in geometry.responses}
    blocks: dict[str, list[np.ndarray]] = {}

    spectral = surfaces.get(("spectral", "summary"))
    if spectral is not None:
        values = spectral.copy()
        if quotient_global_rotation and len(values) >= 4:
            values = values[1:]  # anisotropy, entropy and characteristic frequency
        blocks.setdefault("spectral", []).append(values)

    orientation = surfaces.get(("tensor", "orientation"))
    coherency = surfaces.get(("tensor", "coherency"))
    if orientation is not None:
        if quotient_global_rotation:
            radians = np.deg2rad(2 * orientation)
            weights = np.ones_like(radians) if coherency is None else np.maximum(coherency, np.finfo(float).eps)
            reference = .5 * np.arctan2(np.sum(weights * np.sin(radians)), np.sum(weights * np.cos(radians)))
            relative = radians - 2 * reference
            tensor_direction = np.concatenate([np.cos(relative), np.sin(relative)])
        else:
            tensor_direction = orientation
        blocks.setdefault("tensor", []).append(tensor_direction)
    if coherency is not None:
        blocks.setdefault("tensor", []).append(coherency)

    for (module, measurement), values in sorted(surfaces.items()):
        if module in {"spectral", "tensor", "spatial"}:
            continue
        blocks.setdefault(module, []).append(values)

    horizontal = surfaces.get(("spatial", "variogram_horizontal"))
    vertical = surfaces.get(("spatial", "variogram_vertical"))
    if horizontal is not None and vertical is not None and quotient_global_rotation:
        blocks.setdefault("spatial", []).extend(((horizontal + vertical) / 2, np.abs(horizontal - vertical)))
    else:
        if horizontal is not None:
            blocks.setdefault("spatial", []).append(horizontal)
        if vertical is not None:
            blocks.setdefault("spatial", []).append(vertical)

    return {module: np.concatenate(values) for module, values in sorted(blocks.items())}


def canonical_response_vector(geometry: ResponseGeometry, *, quotient_global_rotation: bool = True) -> np.ndarray:
    blocks = canonical_response_blocks(geometry, quotient_global_rotation=quotient_global_rotation)
    return np.concatenate([blocks[module] for module in sorted(blocks)])
