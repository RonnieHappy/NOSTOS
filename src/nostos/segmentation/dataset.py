from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from .annotations import AnnotationRecord

STAIN_IDS = {"HE": 0, "SafO": 1, "PLM": 2}


@lru_cache(maxsize=128)
def _load_section(image_path: str, mask_path: str) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(image_path) as source_image, Image.open(mask_path) as source_mask:
        image = np.asarray(source_image.convert("RGB"), dtype=np.uint8)
        mask = np.asarray(source_mask.convert("L"), dtype=np.uint8)
    return image, mask


class SegmentationTileDataset(Dataset):
    """Random tiles from reviewed whole-section masks; one item per manifest row per epoch."""

    def __init__(
        self,
        records: list[AnnotationRecord],
        tile_size: int = 512,
        augment: bool = False,
        samples_per_record: int = 16,
        foreground_probability: float = 0.8,
    ):
        if not records or tile_size <= 0 or samples_per_record <= 0:
            raise ValueError("records must be non-empty and tile_size positive")
        self.records = records
        self.tile_size = tile_size
        self.augment = augment
        self.samples_per_record = samples_per_record
        self.foreground_probability = foreground_probability

    def __len__(self) -> int:
        return len(self.records) * self.samples_per_record

    def _origin(self, width: int, height: int) -> tuple[int, int]:
        if width < self.tile_size or height < self.tile_size:
            raise ValueError(f"image smaller than requested {self.tile_size}-pixel tile")
        return random.randint(0, width - self.tile_size), random.randint(0, height - self.tile_size)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        record = self.records[index % len(self.records)]
        image, mask = _load_section(str(record.image_path), str(record.mask_path))
        height, width = mask.shape
        if width < self.tile_size or height < self.tile_size:
            raise ValueError(f"image smaller than requested {self.tile_size}-pixel tile")
        preview = Image.fromarray(mask)
        preview.thumbnail((512, 512), resample=Image.Resampling.NEAREST)
        mask_preview = np.asarray(preview)
        candidates = np.argwhere((mask_preview > 0) & (mask_preview < 5))
        if candidates.size and random.random() < self.foreground_probability:
            preview_y, preview_x = candidates[random.randrange(len(candidates))]
            center_x = (preview_x + 0.5) * width / preview.width
            center_y = (preview_y + 0.5) * height / preview.height
            left = min(max(int(center_x) - self.tile_size // 2, 0), width - self.tile_size)
            top = min(max(int(center_y) - self.tile_size // 2, 0), height - self.tile_size)
        else:
            left, top = self._origin(width, height)
        image_array = image[top : top + self.tile_size, left : left + self.tile_size].astype(np.float32) / 255.0
        mask_array = mask[top : top + self.tile_size, left : left + self.tile_size].astype(np.int64)
        if self.augment:
            if random.random() < 0.5:
                image_array, mask_array = image_array[:, ::-1], mask_array[:, ::-1]
            rotations = random.randrange(4)
            image_array, mask_array = np.rot90(image_array, rotations), np.rot90(mask_array, rotations)
        image_tensor = torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1)))
        mask_tensor = torch.from_numpy(np.ascontiguousarray(mask_array))
        return image_tensor, torch.tensor(STAIN_IDS[record.stain]), mask_tensor
