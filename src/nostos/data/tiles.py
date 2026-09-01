from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class TileRecord:
    row: int
    column: int
    height: int
    width: int
    tissue_fraction: float
    image: np.ndarray


def iter_tiles(
    image: np.ndarray,
    tissue_mask: np.ndarray,
    *,
    tile_size: int = 512,
    overlap_fraction: float = 0.5,
    minimum_tissue_fraction: float = 0.8,
) -> Iterator[TileRecord]:
    """Yield identically selected image tiles for FFT and comparator features."""
    image = np.asarray(image)
    mask = np.asarray(tissue_mask, dtype=bool)
    if image.shape[:2] != mask.shape:
        raise ValueError("Image and tissue mask dimensions do not match.")
    if tile_size < 32:
        raise ValueError("tile_size must be at least 32 pixels.")
    if not 0 <= overlap_fraction < 1:
        raise ValueError("overlap_fraction must be in [0, 1).")
    if not 0 <= minimum_tissue_fraction <= 1:
        raise ValueError("minimum_tissue_fraction must be in [0, 1].")
    step = max(1, round(tile_size * (1.0 - overlap_fraction)))
    if image.shape[0] < tile_size or image.shape[1] < tile_size:
        return
    for row in range(0, image.shape[0] - tile_size + 1, step):
        for column in range(0, image.shape[1] - tile_size + 1, step):
            tile_mask = mask[row : row + tile_size, column : column + tile_size]
            tissue_fraction = float(tile_mask.mean())
            if tissue_fraction < minimum_tissue_fraction:
                continue
            yield TileRecord(
                row=row,
                column=column,
                height=tile_size,
                width=tile_size,
                tissue_fraction=tissue_fraction,
                image=image[row : row + tile_size, column : column + tile_size],
            )


def conservative_brightfield_tissue_mask(image: np.ndarray) -> np.ndarray:
    """Initial white-background exclusion for H&E and Safranin-O images.

    This deliberately conservative mask must be visually validated on the real
    repository before it is accepted for the locked analysis.
    """
    rgb = np.asarray(image)
    if rgb.ndim != 3 or rgb.shape[-1] < 3:
        raise ValueError("Brightfield masking requires an RGB image.")
    rgb = rgb[..., :3].astype(np.float64)
    maximum = 255.0 if rgb.max() > 1.5 else 1.0
    rgb /= maximum
    brightness = rgb.mean(axis=-1)
    chroma = rgb.max(axis=-1) - rgb.min(axis=-1)
    return (brightness < 0.94) | (chroma > 0.06)
