from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def as_grayscale_float(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 3:
        if array.shape[-1] < 3:
            array = array[..., 0]
        else:
            rgb = array[..., :3].astype(np.float64)
            array = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    if array.ndim != 2:
        raise ValueError(f"Expected a 2-D or RGB image; received {array.shape}.")
    result = array.astype(np.float64, copy=False)
    if not np.isfinite(result).all():
        raise ValueError("Image contains NaN or infinite values.")
    return result


@dataclass(frozen=True)
class StructureTensorFeatures:
    orientation_degrees: float
    coherence: float
    gradient_energy: float


@dataclass(frozen=True)
class CooccurrenceFeatures:
    contrast: float
    homogeneity: float
    energy: float
    entropy: float


def structure_tensor_features(image: np.ndarray) -> StructureTensorFeatures:
    """Compute a globalized local-gradient orientation baseline for one tile."""
    tile = as_grayscale_float(image)
    if min(tile.shape) < 16:
        raise ValueError("Structure-tensor tiles must be at least 16 x 16 pixels.")
    gradient_y, gradient_x = np.gradient(tile)
    jxx = float(np.mean(gradient_x * gradient_x))
    jyy = float(np.mean(gradient_y * gradient_y))
    jxy = float(np.mean(gradient_x * gradient_y))
    trace = jxx + jyy
    discriminant = float(np.hypot(jxx - jyy, 2.0 * jxy))
    coherence = discriminant / trace if trace > np.finfo(float).eps else 0.0
    # Gradient direction is normal to elongated structures; rotate by 90 degrees.
    angle = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + np.pi / 2.0
    orientation = float(np.mod(angle, np.pi) * 180.0 / np.pi)
    return StructureTensorFeatures(
        orientation_degrees=orientation,
        coherence=float(coherence),
        gradient_energy=trace,
    )


def cooccurrence_features(
    image: np.ndarray,
    *,
    levels: int = 32,
    offset: tuple[int, int] = (0, 1),
) -> CooccurrenceFeatures:
    """Compute a symmetric normalized gray-level co-occurrence baseline."""
    if levels < 4 or levels > 256:
        raise ValueError("levels must be between 4 and 256.")
    tile = as_grayscale_float(image)
    low, high = np.percentile(tile, [1.0, 99.0])
    if high <= low:
        raise ValueError("Tile has insufficient intensity range.")
    quantized = np.clip(((tile - low) / (high - low) * levels).astype(int), 0, levels - 1)
    dy, dx = offset
    y0 = max(0, -dy)
    y1 = min(tile.shape[0], tile.shape[0] - dy)
    x0 = max(0, -dx)
    x1 = min(tile.shape[1], tile.shape[1] - dx)
    first = quantized[y0:y1, x0:x1].ravel()
    second = quantized[y0 + dy : y1 + dy, x0 + dx : x1 + dx].ravel()
    matrix = np.zeros((levels, levels), dtype=np.float64)
    np.add.at(matrix, (first, second), 1.0)
    np.add.at(matrix, (second, first), 1.0)
    matrix /= matrix.sum()
    i, j = np.indices(matrix.shape)
    contrast = float(np.sum(matrix * (i - j) ** 2))
    homogeneity = float(np.sum(matrix / (1.0 + (i - j) ** 2)))
    energy = float(np.sum(matrix**2))
    nonzero = matrix[matrix > 0]
    entropy = float(-np.sum(nonzero * np.log(nonzero)))
    return CooccurrenceFeatures(contrast, homogeneity, energy, entropy)
