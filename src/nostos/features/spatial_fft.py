from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class SpatialFFTFeatures:
    """Axial-orientation and scale descriptors from a local 2-D image tile."""

    orientation_degrees: float
    anisotropy: float
    angular_entropy: float
    spectral_slope: float
    characteristic_frequency_cycles_per_mm: float
    analyzed_power: float


def _as_grayscale_float(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 3:
        if array.shape[2] < 3:
            array = array[..., 0]
        else:
            rgb = array[..., :3].astype(np.float64)
            array = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    if array.ndim != 2:
        raise ValueError(f"Expected a 2-D or RGB image; received shape {array.shape}.")
    array = array.astype(np.float64, copy=False)
    if not np.isfinite(array).all():
        raise ValueError("Image contains NaN or infinite values.")
    return array


def _remove_plane(image: np.ndarray) -> np.ndarray:
    rows, columns = image.shape
    y, x = np.mgrid[-1.0:1.0:complex(rows), -1.0:1.0:complex(columns)]
    design = np.column_stack((x.ravel(), y.ravel(), np.ones(image.size)))
    coefficients, *_ = np.linalg.lstsq(design, image.ravel(), rcond=None)
    plane = coefficients[0] * x + coefficients[1] * y + coefficients[2]
    return image - plane


def _normalized_entropy(weights: np.ndarray) -> float:
    probabilities = weights / weights.sum()
    nonzero = probabilities[probabilities > 0]
    return float(-(nonzero * np.log(nonzero)).sum() / np.log(len(weights)))


def extract_spatial_fft(
    image: np.ndarray,
    *,
    pixel_size_um: float,
    angular_bins: int = 36,
    low_frequency_fraction: float = 0.02,
    high_frequency_fraction: float = 0.90,
) -> SpatialFFTFeatures:
    """Extract local spatial-FFT descriptors after planar detrending and Hann windowing.

    Orientation is axial (0-180 degrees). Frequency is reported in cycles/mm so
    results from differently sampled images are not silently pooled.
    """
    if pixel_size_um <= 0:
        raise ValueError("pixel_size_um must be positive.")
    if angular_bins < 8:
        raise ValueError("angular_bins must be at least 8.")
    if not 0 <= low_frequency_fraction < high_frequency_fraction <= 1:
        raise ValueError("Frequency fractions must satisfy 0 <= low < high <= 1.")

    tile = _remove_plane(_as_grayscale_float(image))
    if min(tile.shape) < 32:
        raise ValueError("FFT tiles must be at least 32 x 32 pixels.")
    if float(np.std(tile)) <= np.finfo(np.float64).eps:
        raise ValueError("FFT tile has no measurable intensity variation.")

    window = np.outer(np.hanning(tile.shape[0]), np.hanning(tile.shape[1]))
    spectrum = np.fft.fftshift(np.fft.fft2(tile * window))
    power = np.abs(spectrum) ** 2

    spacing_mm = pixel_size_um / 1000.0
    fy = np.fft.fftshift(np.fft.fftfreq(tile.shape[0], d=spacing_mm))
    fx = np.fft.fftshift(np.fft.fftfreq(tile.shape[1], d=spacing_mm))
    grid_x, grid_y = np.meshgrid(fx, fy)
    radius = np.hypot(grid_x, grid_y)
    nyquist = 0.5 / spacing_mm
    mask = (radius >= low_frequency_fraction * nyquist) & (
        radius <= high_frequency_fraction * nyquist
    )
    weights = power[mask]
    if weights.size == 0 or weights.sum() <= 0:
        raise ValueError("No spectral power remains inside the selected frequency band.")

    # Fourier energy is normal to spatial structures, so rotate by 90 degrees.
    angles = np.mod(np.arctan2(grid_y[mask], grid_x[mask]) + np.pi / 2, np.pi)
    moment = np.sum(weights * np.exp(2j * angles)) / np.sum(weights)
    orientation = float(np.mod(0.5 * np.angle(moment), np.pi) * 180.0 / np.pi)
    anisotropy = float(np.abs(moment))

    bin_edges = np.linspace(0.0, np.pi, angular_bins + 1)
    angular_power, _ = np.histogram(angles, bins=bin_edges, weights=weights)
    angular_entropy = _normalized_entropy(angular_power + np.finfo(float).eps)

    selected_radius = radius[mask]
    radial_edges = np.geomspace(
        max(selected_radius.min(), np.finfo(float).eps), selected_radius.max(), 33
    )
    radial_index = np.digitize(selected_radius, radial_edges) - 1
    centers: list[float] = []
    means: list[float] = []
    for index in range(len(radial_edges) - 1):
        selected = radial_index == index
        if selected.any():
            centers.append(float(np.sqrt(radial_edges[index] * radial_edges[index + 1])))
            means.append(float(weights[selected].mean()))
    slope = float(np.polyfit(np.log(centers), np.log(np.maximum(means, np.finfo(float).tiny)), 1)[0])

    order = np.argsort(selected_radius)
    cumulative = np.cumsum(weights[order])
    median_index = int(np.searchsorted(cumulative, cumulative[-1] / 2.0))
    # Power-weighted median frequency is less peak/noise-sensitive than an
    # argmax and is therefore named characteristic, not "dominant", frequency.
    characteristic_frequency = float(selected_radius[order][median_index])

    return SpatialFFTFeatures(
        orientation_degrees=orientation,
        anisotropy=anisotropy,
        angular_entropy=angular_entropy,
        spectral_slope=slope,
        characteristic_frequency_cycles_per_mm=characteristic_frequency,
        analyzed_power=float(weights.sum()),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract spatial FFT features from one image tile.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--pixel-size-um", type=float, required=True)
    args = parser.parse_args()
    with Image.open(args.image) as opened:
        features = extract_spatial_fft(np.asarray(opened), pixel_size_um=args.pixel_size_um)
    print(json.dumps(asdict(features), indent=2))


if __name__ == "__main__":
    main()
