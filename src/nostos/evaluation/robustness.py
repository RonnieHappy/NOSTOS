from __future__ import annotations

from dataclasses import asdict
from typing import Callable

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import rotate

from nostos.features.spatial_fft import SpatialFFTFeatures, extract_spatial_fft


def apply_smooth_illumination(
    image: np.ndarray,
    *,
    gain: float = 1.0,
    offset_fraction: float = 0.0,
    gradient_fraction: float = 0.0,
) -> np.ndarray:
    array = np.asarray(image, dtype=float)
    scale = float(np.ptp(array)) or 1.0
    horizontal = np.linspace(-0.5, 0.5, array.shape[1])
    field = gain + gradient_fraction * horizontal
    if array.ndim == 3:
        field = field[None, :, None]
    else:
        field = field[None, :]
    return array * field + offset_fraction * scale


def apply_gaussian_blur(image: np.ndarray, radius: float) -> np.ndarray:
    array = np.asarray(image)
    low, high = float(array.min()), float(array.max())
    if high <= low:
        return array.astype(float)
    normalized = np.clip((array - low) / (high - low) * 255.0, 0, 255).astype(np.uint8)
    blurred = np.asarray(Image.fromarray(normalized).filter(ImageFilter.GaussianBlur(radius=radius)))
    return blurred.astype(float) / 255.0 * (high - low) + low


def apply_downsample_restore(image: np.ndarray, factor: int) -> np.ndarray:
    if factor < 1:
        raise ValueError("factor must be at least 1.")
    array = np.asarray(image)
    height, width = array.shape[:2]
    pil = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
    smaller = pil.resize((max(1, width // factor), max(1, height // factor)), Image.Resampling.BOX)
    return np.asarray(smaller.resize((width, height), Image.Resampling.BILINEAR))


def apply_rotation(image: np.ndarray, degrees: float) -> np.ndarray:
    quarter_turns = degrees / 90.0
    if np.isclose(quarter_turns, round(quarter_turns)):
        return np.rot90(np.asarray(image), int(round(quarter_turns)) % 4).copy()
    return rotate(np.asarray(image), degrees, reshape=False, order=1, mode="reflect")


def apply_gaussian_noise(image: np.ndarray, sigma_fraction: float, seed: int = 240826) -> np.ndarray:
    if sigma_fraction < 0:
        raise ValueError("sigma_fraction must be nonnegative")
    array = np.asarray(image, dtype=float)
    scale = float(np.ptp(array)) or 1.0
    return array + np.random.default_rng(seed).normal(0.0, sigma_fraction * scale, size=array.shape)


def axial_angle_difference(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def fft_feature_drift(
    reference: SpatialFFTFeatures,
    perturbed: SpatialFFTFeatures,
) -> dict[str, float]:
    result: dict[str, float] = {
        "orientation_degrees_absolute_drift": axial_angle_difference(
            reference.orientation_degrees, perturbed.orientation_degrees
        )
    }
    reference_values = asdict(reference)
    perturbed_values = asdict(perturbed)
    for name in (
        "anisotropy",
        "angular_entropy",
        "spectral_slope",
        "characteristic_frequency_cycles_per_mm",
    ):
        denominator = max(abs(float(reference_values[name])), np.finfo(float).eps)
        result[f"{name}_relative_drift"] = abs(
            float(perturbed_values[name]) - float(reference_values[name])
        ) / denominator
    return result


def evaluate_fft_perturbation(
    image: np.ndarray,
    perturbation: Callable[[np.ndarray], np.ndarray],
    *,
    pixel_size_um: float,
) -> dict[str, float]:
    reference = extract_spatial_fft(image, pixel_size_um=pixel_size_um)
    perturbed = extract_spatial_fft(perturbation(np.asarray(image)), pixel_size_um=pixel_size_um)
    return fft_feature_drift(reference, perturbed)


def evaluate_robustness_suite(image: np.ndarray, *, pixel_size_um: float) -> list[dict[str, float | str | bool]]:
    perturbations: list[tuple[str, Callable[[np.ndarray], np.ndarray]]] = [
        ("illumination", lambda value: apply_smooth_illumination(value, gain=1.2, offset_fraction=0.1, gradient_fraction=0.2)),
        ("blur_1px", lambda value: apply_gaussian_blur(value, 1.0)),
        ("blur_2px", lambda value: apply_gaussian_blur(value, 2.0)),
        ("downsample_2x", lambda value: apply_downsample_restore(value, 2)),
        ("downsample_4x", lambda value: apply_downsample_restore(value, 4)),
        ("noise_01", lambda value: apply_gaussian_noise(value, 0.01)),
        ("noise_05", lambda value: apply_gaussian_noise(value, 0.05)),
    ]
    rows: list[dict[str, float | str | bool]] = []
    for name, perturbation in perturbations:
        try:
            rows.append({"perturbation": name, "success": True, **evaluate_fft_perturbation(image, perturbation, pixel_size_um=pixel_size_um)})
        except (ValueError, FloatingPointError) as error:
            rows.append({"perturbation": name, "success": False, "error": str(error)})
    return rows
