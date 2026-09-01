from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt

from nostos.features.zsd import extract_zsd_tiles, summarize_zsd_tiles


def perturb_cartilage_mask(
    labels: np.ndarray,
    *,
    delta_um: float,
    pixel_size_um: float,
    cartilage_label: int = 1,
) -> np.ndarray:
    """Erode (negative) or dilate (positive) cartilage by a physical distance."""
    labels = np.asarray(labels)
    if labels.ndim != 2 or pixel_size_um <= 0:
        raise ValueError("labels must be 2-D and pixel_size_um positive")
    steps = int(round(abs(delta_um) / pixel_size_um))
    if steps == 0:
        return labels.copy()
    cartilage = labels == cartilage_label
    result = labels.copy()
    structure = np.ones((3, 3), dtype=bool)
    if delta_um < 0:
        retained = binary_erosion(cartilage, structure=structure, iterations=steps)
        removed = cartilage & ~retained
        # Assign eroded pixels to their nearest original non-cartilage class.
        _, indices = distance_transform_edt(cartilage, return_indices=True)
        result[removed] = labels[tuple(axis[removed] for axis in indices)]
    else:
        expanded = binary_dilation(cartilage, structure=structure, iterations=steps)
        # Do not consume explicitly unusable artifact; uncertainty concerns tissue interfaces.
        added = expanded & ~cartilage & (labels != 5)
        result[added] = cartilage_label
    return result


def zsd_mask_sensitivity(
    image: np.ndarray,
    labels: np.ndarray,
    *,
    pixel_size_um: float,
    deltas_um: tuple[float, ...] = (-100.0, -50.0, 0.0, 50.0, 100.0),
    **zsd_kwargs,
) -> list[dict[str, float | bool | str]]:
    rows: list[dict[str, float | bool | str]] = []
    for delta in deltas_um:
        perturbed = perturb_cartilage_mask(labels, delta_um=delta, pixel_size_um=pixel_size_um)
        try:
            tiles = extract_zsd_tiles(image, perturbed, pixel_size_um=pixel_size_um, **zsd_kwargs)
            rows.append({"delta_um": delta, "success": bool(tiles), **summarize_zsd_tiles(tiles)})
        except (ValueError, FloatingPointError) as error:
            rows.append({"delta_um": delta, "success": False, "error": str(error)})
    return rows

