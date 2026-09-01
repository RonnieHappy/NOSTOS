from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile
from matplotlib.colors import rgb_to_hsv
from PIL import Image
from sklearn.cluster import MiniBatchKMeans


@dataclass(frozen=True)
class ClusterProposal:
    resized_rgb: np.ndarray
    clusters: np.ndarray
    centers: np.ndarray


def resize_for_annotation(image: np.ndarray, maximum_dimension: int = 1600) -> np.ndarray:
    rgb = np.asarray(image)
    if rgb.ndim == 2:
        rgb = np.repeat(rgb[..., None], 3, axis=-1)
    rgb = rgb[..., :3]
    height, width = rgb.shape[:2]
    scale = min(1.0, maximum_dimension / max(height, width))
    if scale == 1.0:
        return rgb.astype(np.uint8, copy=False)
    resized = Image.fromarray(rgb.astype(np.uint8)).resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.BOX,
    )
    return np.asarray(resized)


def pixel_features(rgb: np.ndarray) -> np.ndarray:
    normalized = np.asarray(rgb, dtype=np.float32) / 255.0
    hsv = rgb_to_hsv(normalized)
    optical_density = -np.log(np.clip(normalized, 1.0 / 255.0, 1.0))
    height, width = normalized.shape[:2]
    y, x = np.mgrid[0:height, 0:width]
    coordinates = np.stack((x / max(width - 1, 1), y / max(height - 1, 1)), axis=-1)
    # Color dominates; weak coordinates encourage spatially coherent proposals.
    return np.concatenate((normalized, hsv, optical_density, 0.15 * coordinates), axis=-1)


def cluster_proposal(
    image: np.ndarray,
    *,
    clusters: int = 10,
    maximum_dimension: int = 1600,
    sample_pixels: int = 200_000,
    seed: int = 240826,
) -> ClusterProposal:
    resized = resize_for_annotation(image, maximum_dimension=maximum_dimension)
    features = pixel_features(resized).reshape(-1, 11)
    rng = np.random.default_rng(seed)
    if len(features) > sample_pixels:
        training = features[rng.choice(len(features), size=sample_pixels, replace=False)]
    else:
        training = features
    model = MiniBatchKMeans(
        n_clusters=clusters,
        random_state=seed,
        batch_size=8192,
        n_init=5,
    ).fit(training)
    labels = model.predict(features).reshape(resized.shape[:2])
    return ClusterProposal(resized, labels.astype(np.uint8), model.cluster_centers_)


def colorize_clusters(clusters: np.ndarray) -> np.ndarray:
    palette = np.asarray(
        [
            [0, 0, 0],
            [230, 25, 75],
            [60, 180, 75],
            [255, 225, 25],
            [0, 130, 200],
            [245, 130, 48],
            [145, 30, 180],
            [70, 240, 240],
            [240, 50, 230],
            [210, 245, 60],
            [250, 190, 212],
            [0, 128, 128],
        ],
        dtype=np.uint8,
    )
    return palette[np.asarray(clusters) % len(palette)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate stain-specific cluster proposals.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clusters", type=int, default=10)
    args = parser.parse_args()
    image = tifffile.imread(args.image)
    proposal = cluster_proposal(image, clusters=args.clusters)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(colorize_clusters(proposal.clusters)).save(args.output)
    np.save(args.output.with_suffix(".labels.npy"), proposal.clusters)
    np.save(args.output.with_suffix(".centers.npy"), proposal.centers)


if __name__ == "__main__":
    main()
