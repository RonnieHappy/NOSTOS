"""Controlled image, sampling, and mask perturbations for prospective tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, gaussian_filter, rotate, zoom

from .phantoms import Phantom

Kind = Literal["rotation", "resampling", "crop", "blur", "noise", "contrast", "psf", "partial_volume", "mask_error"]


@dataclass(frozen=True)
class Perturbation:
    kind: Kind
    magnitude: float
    seed: int = 2718


def _center_crop_or_pad(array: np.ndarray, target: tuple[int, ...], fill: float = 0.0) -> np.ndarray:
    result = np.full(target, fill, dtype=array.dtype)
    src_slices = []
    dst_slices = []
    for old, new in zip(array.shape, target, strict=True):
        take = min(old, new)
        src_start = (old - take) // 2
        dst_start = (new - take) // 2
        src_slices.append(slice(src_start, src_start + take))
        dst_slices.append(slice(dst_start, dst_start + take))
    result[tuple(dst_slices)] = array[tuple(src_slices)]
    return result


def apply_perturbation(phantom: Phantom, perturbation: Perturbation) -> Phantom:
    image = phantom.image.astype(float, copy=True)
    mask = None if phantom.mask is None else phantom.mask.copy()
    spacing = phantom.truth.spacing_um
    p = perturbation
    rng = np.random.default_rng(p.seed)

    if p.kind == "rotation":
        if image.ndim != 2:
            raise ValueError("The frozen rotation perturbation currently supports 2-D phantoms.")
        image = rotate(image, p.magnitude, reshape=False, order=1, mode="reflect")
        if mask is not None:
            mask = rotate(mask.astype(float), p.magnitude, reshape=False, order=0) > 0.5
    elif p.kind == "resampling":
        if p.magnitude <= 0:
            raise ValueError("Resampling factor must be positive.")
        image = zoom(image, p.magnitude, order=1, mode="reflect")
        if mask is not None:
            mask = zoom(mask.astype(float), p.magnitude, order=0) > 0.5
        spacing = tuple(v / p.magnitude for v in spacing)
    elif p.kind == "crop":
        fraction = p.magnitude
        if not 0 < fraction <= 1:
            raise ValueError("Crop magnitude must be a retained fraction in (0, 1].")
        target = tuple(max(32, int(round(n * fraction))) for n in image.shape)
        image = _center_crop_or_pad(image, target)
        if mask is not None:
            mask = _center_crop_or_pad(mask, target)
    elif p.kind in ("blur", "psf"):
        if p.magnitude < 0:
            raise ValueError("Blur magnitude must be nonnegative pixels.")
        sigma = [p.magnitude] * image.ndim
        if p.kind == "psf" and image.ndim > 1:
            sigma[-1] *= 2.0
        image = gaussian_filter(image, sigma=sigma, mode="reflect")
    elif p.kind == "noise":
        image += rng.normal(scale=p.magnitude * max(float(image.std()), np.finfo(float).eps), size=image.shape)
    elif p.kind == "contrast":
        center = float(np.mean(image))
        image = center + p.magnitude * (image - center)
    elif p.kind == "partial_volume":
        if not 0 < p.magnitude <= 1:
            raise ValueError("Partial-volume magnitude must be a retained sampling factor in (0, 1].")
        coarse = zoom(image, p.magnitude, order=1, mode="reflect")
        image = _center_crop_or_pad(zoom(coarse, 1.0 / p.magnitude, order=1), image.shape)
    elif p.kind == "mask_error":
        if mask is None:
            raise ValueError("Mask error requires a phantom mask.")
        iterations = max(1, int(abs(p.magnitude)))
        mask = binary_dilation(mask, iterations=iterations) if p.magnitude > 0 else binary_erosion(mask, iterations=iterations)
    else:
        raise ValueError(f"Unsupported perturbation: {p.kind}")

    from dataclasses import replace
    return Phantom(np.asarray(image, dtype=np.float32), mask, replace(phantom.truth, spacing_um=spacing))
