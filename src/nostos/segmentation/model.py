from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as functional


class ConvBlock(nn.Module):
    def __init__(self, input_channels: int, output_channels: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(output_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(output_channels, output_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(output_channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


class StainConditionedUNet(nn.Module):
    """Compact shared U-Net conditioned on H&E, Safranin-O, or PLM identity."""

    def __init__(
        self,
        *,
        classes: int = 6,
        stains: int = 3,
        base_channels: int = 32,
    ) -> None:
        super().__init__()
        self.classes = classes
        self.stains = stains
        channels = [base_channels, base_channels * 2, base_channels * 4, base_channels * 8]
        self.encoder_1 = ConvBlock(3 + stains, channels[0])
        self.encoder_2 = ConvBlock(channels[0], channels[1])
        self.encoder_3 = ConvBlock(channels[1], channels[2])
        self.bottleneck = ConvBlock(channels[2], channels[3])
        self.pool = nn.MaxPool2d(2)
        self.up_3 = nn.ConvTranspose2d(channels[3], channels[2], kernel_size=2, stride=2)
        self.decoder_3 = ConvBlock(channels[2] * 2, channels[2])
        self.up_2 = nn.ConvTranspose2d(channels[2], channels[1], kernel_size=2, stride=2)
        self.decoder_2 = ConvBlock(channels[1] * 2, channels[1])
        self.up_1 = nn.ConvTranspose2d(channels[1], channels[0], kernel_size=2, stride=2)
        self.decoder_1 = ConvBlock(channels[0] * 2, channels[0])
        self.classifier = nn.Conv2d(channels[0], classes, kernel_size=1)

    def _condition(self, images: torch.Tensor, stain_ids: torch.Tensor) -> torch.Tensor:
        if images.ndim != 4 or images.shape[1] != 3:
            raise ValueError("images must have shape [batch, 3, height, width].")
        if stain_ids.shape != (images.shape[0],):
            raise ValueError("stain_ids must contain one integer per image.")
        if torch.any(stain_ids < 0) or torch.any(stain_ids >= self.stains):
            raise ValueError("stain_ids contain an unsupported stain index.")
        one_hot = functional.one_hot(stain_ids.long(), num_classes=self.stains).to(images.dtype)
        condition = one_hot[:, :, None, None].expand(-1, -1, images.shape[2], images.shape[3])
        return torch.cat((images, condition), dim=1)

    def forward(self, images: torch.Tensor, stain_ids: torch.Tensor) -> torch.Tensor:
        encoded_1 = self.encoder_1(self._condition(images, stain_ids))
        encoded_2 = self.encoder_2(self.pool(encoded_1))
        encoded_3 = self.encoder_3(self.pool(encoded_2))
        bottleneck = self.bottleneck(self.pool(encoded_3))
        decoded_3 = self.decoder_3(torch.cat((self.up_3(bottleneck), encoded_3), dim=1))
        decoded_2 = self.decoder_2(torch.cat((self.up_2(decoded_3), encoded_2), dim=1))
        decoded_1 = self.decoder_1(torch.cat((self.up_1(decoded_2), encoded_1), dim=1))
        return self.classifier(decoded_1)


def generalized_dice_loss(logits: torch.Tensor, targets: torch.Tensor, epsilon: float = 1e-6) -> torch.Tensor:
    if logits.ndim != 4 or targets.shape != (logits.shape[0], logits.shape[2], logits.shape[3]):
        raise ValueError("Targets must have shape [batch, height, width].")
    probabilities = torch.softmax(logits, dim=1)
    one_hot = functional.one_hot(targets.long(), num_classes=logits.shape[1]).permute(0, 3, 1, 2)
    one_hot = one_hot.to(probabilities.dtype)
    class_volume = one_hot.sum(dim=(0, 2, 3))
    # Ignore classes absent from this minibatch; inverse-volume weighting them
    # would otherwise overwhelm the classes that have actual reference pixels.
    weights = torch.where(class_volume > 0, 1.0 / torch.clamp(class_volume**2, min=epsilon), 0.0)
    intersection = (probabilities * one_hot).sum(dim=(0, 2, 3))
    denominator = (probabilities + one_hot).sum(dim=(0, 2, 3))
    score = 2.0 * (weights * intersection).sum() / torch.clamp(
        (weights * denominator).sum(), min=epsilon
    )
    return 1.0 - score


def segmentation_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    return functional.cross_entropy(logits, targets.long()) + generalized_dice_loss(logits, targets)
