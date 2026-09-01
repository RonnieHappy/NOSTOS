from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from .annotations import read_annotation_manifest, validate_annotation_manifest
from .dataset import SegmentationTileDataset
from .model import StainConditionedUNet, segmentation_loss


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _epoch(model, loader, device, optimizer=None) -> float:
    training = optimizer is not None
    model.train(training)
    total = 0.0
    batches = 0
    for images, stains, targets in loader:
        images, stains, targets = images.to(device), stains.to(device), targets.to(device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            logits = model(images, stains)
            loss = segmentation_loss(logits, targets)
            if training:
                loss.backward()
                optimizer.step()
        total += float(loss.detach())
        batches += 1
    return total / max(batches, 1)


def train(args: argparse.Namespace) -> dict:
    seed_everything(args.seed)
    records = read_annotation_manifest(args.manifest)
    errors = validate_annotation_manifest(records, require_review_audit=not args.allow_unreviewed_proposals)
    if errors:
        raise ValueError("Invalid annotation manifest:\n" + "\n".join(errors))
    train_records = [record for record in records if record.split == "train"]
    validation_records = [record for record in records if record.split == "validation"]
    if not train_records or not validation_records:
        raise ValueError("manifest requires both train and validation records")
    train_data = SegmentationTileDataset(
        train_records, args.tile_size, augment=True, samples_per_record=args.samples_per_record
    )
    validation_data = SegmentationTileDataset(
        validation_records, args.tile_size, augment=False, samples_per_record=max(2, args.samples_per_record // 4)
    )
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_data, args.batch_size, shuffle=True, num_workers=args.workers, generator=generator)
    validation_loader = DataLoader(validation_data, args.batch_size, shuffle=False, num_workers=args.workers)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = StainConditionedUNet(base_channels=args.base_channels).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    history = []
    best = float("inf")
    for epoch in range(1, args.epochs + 1):
        train_loss = _epoch(model, train_loader, device, optimizer)
        with torch.no_grad():
            validation_loss = _epoch(model, validation_loader, device)
        row = {"epoch": epoch, "train_loss": train_loss, "validation_loss": validation_loss}
        history.append(row)
        print(json.dumps(row), flush=True)
        if validation_loss < best:
            best = validation_loss
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "model": {"classes": 6, "stains": 3, "base_channels": args.base_channels},
                    "seed": args.seed,
                    "supervision": "unreviewed_weak_proposals" if args.allow_unreviewed_proposals else "reviewed_reference_masks",
                    "epoch": epoch,
                    "validation_loss": validation_loss,
                },
                output,
            )
    history_path = output.with_suffix(".history.json")
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return {"checkpoint": str(output), "history": str(history_path), "device": str(device), "best": best}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train participant-separated NOSTOS semantic segmentation.")
    parser.add_argument("manifest")
    parser.add_argument("--output", default="outputs/segmentation/best.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--samples-per-record", type=int, default=32)
    parser.add_argument("--base-channels", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=240826)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument(
        "--allow-unreviewed-proposals",
        action="store_true",
        help="Initialize from weak proposal masks; checkpoint is not valid for performance claims.",
    )
    return parser


def main() -> None:
    print(json.dumps(train(build_parser().parse_args()), indent=2))


if __name__ == "__main__":
    main()
