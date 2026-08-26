"""Deterministic calibrated phantoms with machine-readable ground truth."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.ndimage import gaussian_filter

Construct = Literal["orientation", "spectral_scale", "blob", "tube", "sheet", "thickness", "roughness", "network", "heterogeneity"]


@dataclass(frozen=True)
class PhantomTruth:
    construct: Construct
    parameters: dict[str, float | int | str | list[float]]
    spacing_um: tuple[float, ...]
    seed: int


@dataclass(frozen=True)
class Phantom:
    image: np.ndarray
    mask: np.ndarray | None
    truth: PhantomTruth


def _grid(shape: tuple[int, ...], spacing_um: tuple[float, ...]) -> tuple[np.ndarray, ...]:
    axes = [(np.arange(n) - (n - 1) / 2) * d for n, d in zip(shape, spacing_um, strict=True)]
    return tuple(np.meshgrid(*axes, indexing="ij"))


def generate_phantom(
    construct: Construct,
    *,
    shape: tuple[int, ...] = (192, 192),
    spacing_um: tuple[float, ...] = (1.0, 1.0),
    seed: int = 1729,
    angle_degrees: float = 30.0,
    dispersion_degrees: float = 0.0,
    scale_um: float = 16.0,
    correlation_length_um: float = 12.0,
    anisotropy_ratio: float = 2.0,
) -> Phantom:
    if len(shape) not in (2, 3) or len(shape) != len(spacing_um):
        raise ValueError("Phantoms require matching 2-D or 3-D shape and spacing.")
    if any(n < 32 for n in shape) or any(v <= 0 for v in spacing_um):
        raise ValueError("Each dimension must be >=32 and spacing must be positive.")
    rng = np.random.default_rng(seed)
    coords = _grid(shape, spacing_um)
    parameters: dict[str, float | int | str | list[float]] = {}
    mask: np.ndarray | None = None

    if construct in ("orientation", "spectral_scale"):
        if len(shape) != 2:
            raise ValueError(f"{construct} currently requires a 2-D shape.")
        theta = np.deg2rad(angle_degrees)
        y, x = coords
        normal_coordinate = -x * np.sin(theta) + y * np.cos(theta)
        image = np.cos(2 * np.pi * normal_coordinate / scale_um)
        if dispersion_degrees > 0:
            second = np.deg2rad(angle_degrees + dispersion_degrees)
            normal2 = -x * np.sin(second) + y * np.cos(second)
            image = 0.5 * image + 0.5 * np.cos(2 * np.pi * normal2 / scale_um)
        parameters = {"orientation_degrees": angle_degrees % 180, "dispersion_degrees": dispersion_degrees, "wavelength_um": scale_um}
    elif construct in ("blob", "tube", "sheet", "thickness"):
        radius = scale_um / 2.0
        if construct == "blob":
            distance = np.sqrt(sum(c**2 for c in coords))
        elif construct == "tube":
            distance = np.sqrt(sum(c**2 for c in coords[:-1])) if len(shape) == 3 else np.abs(coords[0])
        else:
            distance = np.abs(coords[0])
        mask = distance <= radius
        if construct in ("blob", "tube", "sheet"):
            # Smooth analytic profiles isolate Hessian morphology without a
            # binary object's outer boundary becoming the dominant structure.
            image = np.exp(-0.5 * (distance / radius) ** 2)
        else:
            image = gaussian_filter(mask.astype(float), sigma=tuple(max(0.5, 0.5 / d) for d in spacing_um))
        parameters = {"class": construct, "radius_um": radius, "diameter_um": scale_um}
    elif construct == "roughness":
        if len(shape) != 2:
            raise ValueError("roughness currently requires a 2-D shape.")
        y, x = coords
        amplitude = scale_um / 4
        wavelength = scale_um * 2
        surface = amplitude * np.sin(2 * np.pi * x / wavelength)
        mask = y >= surface
        image = gaussian_filter(mask.astype(float), sigma=0.7)
        parameters = {"amplitude_um": amplitude, "wavelength_um": wavelength, "rms_roughness_um": amplitude / np.sqrt(2)}
    elif construct == "network":
        if len(shape) != 2:
            raise ValueError("network currently requires a 2-D shape.")
        y, x = coords
        width = scale_um / 5
        horizontal = np.abs(y) <= width
        vertical = np.abs(x) <= width
        diagonal = np.abs(y - x) / np.sqrt(2) <= width
        mask = horizontal | vertical | diagonal
        image = gaussian_filter(mask.astype(float), sigma=0.8)
        parameters = {"branch_count": 6, "cycle_count": 0, "junction_count": 1, "width_um": 2 * width}
    elif construct == "heterogeneity":
        white = rng.normal(size=shape)
        sigma = tuple(correlation_length_um / (np.sqrt(2) * d) for d in spacing_um)
        if len(shape) >= 2:
            sigma = (sigma[0] / anisotropy_ratio,) + sigma[1:]
        image = gaussian_filter(white, sigma=sigma, mode="reflect")
        image = (image - image.mean()) / max(image.std(), np.finfo(float).eps)
        parameters = {"correlation_length_um": correlation_length_um, "anisotropy_ratio": anisotropy_ratio}
    else:
        raise ValueError(f"Unsupported construct: {construct}")

    image = np.asarray(image, dtype=np.float32)
    truth = PhantomTruth(construct=construct, parameters=parameters, spacing_um=spacing_um, seed=seed)
    return Phantom(image=image, mask=None if mask is None else mask.astype(bool), truth=truth)
