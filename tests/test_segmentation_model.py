import pytest

torch = pytest.importorskip("torch")

from nostos.segmentation.model import StainConditionedUNet, generalized_dice_loss, segmentation_loss


def test_stain_conditioned_unet_shape_and_loss() -> None:
    model = StainConditionedUNet(base_channels=8)
    images = torch.rand(2, 3, 64, 64)
    stains = torch.tensor([0, 2])
    targets = torch.randint(0, 6, (2, 64, 64))
    logits = model(images, stains)
    assert logits.shape == (2, 6, 64, 64)
    loss = segmentation_loss(logits, targets)
    assert torch.isfinite(loss)


def test_dice_loss_is_finite_when_most_classes_are_absent() -> None:
    logits = torch.zeros((1, 6, 16, 16), requires_grad=True)
    targets = torch.ones((1, 16, 16), dtype=torch.long)
    loss = generalized_dice_loss(logits, targets)
    assert torch.isfinite(loss)
    loss.backward()
    assert logits.grad is not None
