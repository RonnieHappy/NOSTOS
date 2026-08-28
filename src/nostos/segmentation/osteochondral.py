"""Single-channel learned ROI adapter for osteochondral micro-CT development."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import Dataset


class Block(nn.Module):
    def __init__(self, input_channels: int, output_channels: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(output_channels), nn.SiLU(inplace=True),
            nn.Conv2d(output_channels, output_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(output_channels), nn.SiLU(inplace=True),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.layers(value)


class OsteochondralUNet(nn.Module):
    def __init__(self, base_channels: int = 16) -> None:
        super().__init__()
        c1, c2, c3, c4 = (base_channels * value for value in (1, 2, 4, 8))
        self.pool = nn.MaxPool2d(2)
        self.e1, self.e2, self.e3 = Block(1, c1), Block(c1, c2), Block(c2, c3)
        self.bridge = Block(c3, c4)
        self.u3, self.u2, self.u1 = (nn.ConvTranspose2d(a, b, 2, 2) for a, b in ((c4, c3), (c3, c2), (c2, c1)))
        self.d3, self.d2, self.d1 = Block(c3 * 2, c3), Block(c2 * 2, c2), Block(c1 * 2, c1)
        self.head = nn.Conv2d(c1, 1, 1)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        a = self.e1(image); b = self.e2(self.pool(a)); c = self.e3(self.pool(b))
        value = self.d3(torch.cat((self.u3(self.bridge(self.pool(c))), c), 1))
        value = self.d2(torch.cat((self.u2(value), b), 1))
        return self.head(self.d1(torch.cat((self.u1(value), a), 1)))


def binary_segmentation_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    target = target.to(logits.dtype)
    bce = F.binary_cross_entropy_with_logits(logits, target)
    probability = torch.sigmoid(logits)
    intersection = (probability * target).sum(dim=(1, 2, 3))
    denominator = probability.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    dice = (2 * intersection + 1.0) / (denominator + 1.0)
    return bce + (1.0 - dice.mean())


def boundary_aware_segmentation_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    *,
    boundary_sigma_px: float = 5.0,
    boundary_weight: float = 4.0,
    interface_weight: float = 2.0,
) -> torch.Tensor:
    """Dice/BCE objective augmented for the first foreground interface in each column."""
    if boundary_sigma_px <= 0 or boundary_weight < 0 or interface_weight < 0:
        raise ValueError("Boundary parameters must be non-negative and sigma must be positive.")
    target = target.to(logits.dtype)
    probability = torch.sigmoid(logits)
    height = target.shape[-2]
    eligible = target.amax(dim=-2) > 0.5
    truth_rows = target.argmax(dim=-2).to(logits.dtype)
    rows = torch.arange(height, device=logits.device, dtype=logits.dtype).view(1, 1, height, 1)
    distance = rows - truth_rows.unsqueeze(-2)
    emphasis = torch.exp(-0.5 * (distance / boundary_sigma_px).square()) * eligible.unsqueeze(-2)
    bce_map = F.binary_cross_entropy_with_logits(logits, target, reduction="none")
    weighted_bce = (bce_map * (1.0 + boundary_weight * emphasis)).mean()

    previous = F.pad(probability[..., :-1, :], (0, 0, 1, 0))
    transition = F.relu(probability - previous)
    transition_mass = transition.sum(dim=-2)
    predicted_rows = (transition * rows).sum(dim=-2) / transition_mass.clamp_min(1e-6)
    valid = eligible & (transition_mass > 1e-6)
    if valid.any():
        interface = F.smooth_l1_loss(
            predicted_rows[valid] / max(height - 1, 1),
            truth_rows[valid] / max(height - 1, 1),
            beta=0.02,
        )
    else:
        interface = logits.new_tensor(1.0)
    intersection = (probability * target).sum(dim=(1, 2, 3))
    denominator = probability.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    dice = (2 * intersection + 1.0) / (denominator + 1.0)
    return weighted_bce + (1.0 - dice.mean()) + interface_weight * interface


@dataclass(frozen=True)
class SliceRecord:
    patient: str
    sample: str
    family: str
    index: int
    image: Path
    mask: Path


def percentile_normalize(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float32)
    low, high = np.percentile(data, (1, 99))
    if high <= low:
        return np.zeros_like(data)
    return np.clip((data - low) / (high - low), 0, 1).astype(np.float32, copy=False)


def load_pair(record: SliceRecord, downsample: int = 2) -> tuple[torch.Tensor, torch.Tensor]:
    with Image.open(record.image) as opened:
        image = percentile_normalize(np.asarray(opened))
    with Image.open(record.mask) as opened:
        mask = (np.asarray(opened) > 0).astype(np.float32)
    image_tensor = torch.from_numpy(image)[None, None]
    mask_tensor = torch.from_numpy(mask)[None, None]
    size = (image.shape[0] // downsample, image.shape[1] // downsample)
    image_tensor = F.interpolate(image_tensor, size=size, mode="bilinear", align_corners=False)[0]
    mask_tensor = F.interpolate(mask_tensor, size=size, mode="nearest")[0]
    return image_tensor, mask_tensor


class OsteochondralSliceDataset(Dataset):
    def __init__(self, records: list[SliceRecord], *, augment: bool, seed: int) -> None:
        self.records, self.augment, self.seed, self.epoch = records, augment, seed, 0

    def set_epoch(self, epoch: int) -> None:
        """Select a deterministic but epoch-varying augmentation stream."""
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        image, mask = load_pair(self.records[index])
        if self.augment:
            generator = torch.Generator().manual_seed(
                self.seed + 1_000_003 * self.epoch + 10_007 * index
            )
            if torch.rand((), generator=generator) < 0.5:
                image, mask = image.flip(-1), mask.flip(-1)
            gamma = float(torch.empty(()).uniform_(0.7, 1.4, generator=generator))
            contrast = float(torch.empty(()).uniform_(0.8, 1.2, generator=generator))
            noise = float(torch.empty(()).uniform_(0.0, 0.03, generator=generator))
            image = torch.clamp(image.pow(gamma) * contrast + torch.randn(image.shape, generator=generator) * noise, 0, 1)
        return image, mask


def postprocess_probability(probability: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    binary = np.asarray(probability) >= threshold
    labels, count = ndimage.label(binary)
    if count == 0:
        return np.zeros_like(binary)
    sizes = [(int((labels == label).sum()), int(label)) for label in range(1, count + 1)]
    selected = labels == max(sizes)[1]
    filled = ndimage.binary_fill_holes(selected)
    holes = filled & ~selected
    hole_labels, hole_count = ndimage.label(holes)
    for label in range(1, hole_count + 1):
        region = hole_labels == label
        if region.sum() <= 64:
            selected[region] = True
    return selected
