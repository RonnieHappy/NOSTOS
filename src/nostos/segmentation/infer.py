from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from .dataset import STAIN_IDS
from .metrics import class_scores, confusion_matrix, symmetric_boundary_error_um
from .model import StainConditionedUNet
from .weak_labels import proposal_overlay


def load_model(checkpoint_path: str | Path, device: torch.device) -> StainConditionedUNet:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model = StainConditionedUNet(**checkpoint["model"])
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()
    return model


@torch.inference_mode()
def predict_section(
    model: StainConditionedUNet,
    image_path: str | Path,
    stain: str,
    *,
    tile_size: int = 512,
    context: int = 64,
    input_pixel_size_um: float | None = None,
    model_pixel_size_um: float = 5.16,
    device: torch.device | None = None,
) -> np.ndarray:
    if stain not in STAIN_IDS or context < 0 or 2 * context >= tile_size:
        raise ValueError("unsupported stain or invalid context")
    device = device or next(model.parameters()).device
    core = tile_size - 2 * context
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    original_width, original_height = image.size
    if input_pixel_size_um is not None:
        if input_pixel_size_um <= 0 or model_pixel_size_um <= 0:
            raise ValueError("pixel sizes must be positive")
        scale = input_pixel_size_um / model_pixel_size_um
        if not np.isclose(scale, 1.0):
            image = image.resize(
                (max(1, round(original_width * scale)), max(1, round(original_height * scale))),
                Image.Resampling.BOX if scale < 1 else Image.Resampling.BICUBIC,
            )
    width, height = image.size
    cols, rows = math.ceil(width / core), math.ceil(height / core)
    padded_width, padded_height = cols * core + 2 * context, rows * core + 2 * context
    bordered = ImageOps.expand(image, border=context, fill=(255, 255, 255))
    padded = Image.new("RGB", (padded_width, padded_height), (255, 255, 255))
    padded.paste(bordered, (0, 0))
    prediction = np.zeros((height, width), dtype=np.uint8)
    stain_tensor = torch.tensor([STAIN_IDS[stain]], device=device)
    for row in range(rows):
        for col in range(cols):
            left, top = col * core, row * core
            tile = np.asarray(padded.crop((left, top, left + tile_size, top + tile_size)), dtype=np.float32) / 255.0
            tensor = torch.from_numpy(tile.transpose(2, 0, 1).copy())[None].to(device)
            labels = model(tensor, stain_tensor).argmax(1)[0, context : context + core, context : context + core]
            block = labels.cpu().numpy().astype(np.uint8)
            stop_y, stop_x = min((row + 1) * core, height), min((col + 1) * core, width)
            prediction[row * core : stop_y, col * core : stop_x] = block[: stop_y - row * core, : stop_x - col * core]
    if (width, height) != (original_width, original_height):
        prediction = np.asarray(
            Image.fromarray(prediction, mode="L").resize(
                (original_width, original_height), Image.Resampling.NEAREST
            )
        )
    return prediction


def evaluate_prediction(prediction: np.ndarray, target: np.ndarray, pixel_size_um: float) -> dict:
    matrix = confusion_matrix(prediction, target, classes=6)
    scores = class_scores(matrix)
    result = {name: values.tolist() for name, values in scores.items()}
    result["confusion_matrix"] = matrix.tolist()
    result["cartilage_boundary_hd95_um"] = symmetric_boundary_error_um(
        prediction == 1, target == 1, pixel_size_um, percentile=95
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Whole-section, context-cropped segmentation inference.")
    parser.add_argument("checkpoint")
    parser.add_argument("image")
    parser.add_argument("stain", choices=sorted(STAIN_IDS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--preview", help="Optional color-overlay PNG for visual quality control")
    parser.add_argument("--target")
    parser.add_argument("--pixel-size-um", type=float)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--context", type=int, default=64)
    parser.add_argument("--input-pixel-size-um", type=float)
    parser.add_argument("--model-pixel-size-um", type=float, default=5.16)
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = load_model(args.checkpoint, device)
    prediction = predict_section(
        model,
        args.image,
        args.stain,
        tile_size=args.tile_size,
        context=args.context,
        input_pixel_size_um=args.input_pixel_size_um,
        model_pixel_size_um=args.model_pixel_size_um,
        device=device,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(prediction, mode="L").save(output)
    if args.preview:
        with Image.open(args.image) as source:
            rgb = np.asarray(source.convert("RGB"))
        preview = Path(args.preview)
        preview.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(proposal_overlay(rgb, prediction)).save(preview, optimize=True)
    if args.target:
        if not args.pixel_size_um:
            parser.error("--pixel-size-um is required with --target")
        with Image.open(args.target) as target_image:
            target = np.asarray(target_image.convert("L"))
        metrics = evaluate_prediction(prediction, target, args.pixel_size_um)
        output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
