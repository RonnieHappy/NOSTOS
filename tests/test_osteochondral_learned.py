import pytest

torch = pytest.importorskip("torch")

import numpy as np

from nostos.segmentation.osteochondral import (
    OsteochondralUNet, binary_segmentation_loss, boundary_aware_segmentation_loss,
    percentile_normalize, postprocess_probability,
)


def test_learned_adapter_shapes_and_loss() -> None:
    model = OsteochondralUNet(base_channels=4)
    image = torch.rand(2, 1, 64, 64)
    target = (image > 0.5).float()
    logits = model(image)
    assert logits.shape == target.shape
    assert torch.isfinite(binary_segmentation_loss(logits, target))


def test_postprocessing_keeps_largest_component() -> None:
    probability = np.zeros((64, 64), dtype=float)
    probability[40:, 5:60] = 1
    probability[5:10, 5:10] = 1
    result = postprocess_probability(probability)
    assert result[-1].any()
    assert not result[6, 6]


def test_postprocessing_does_not_require_border_contact() -> None:
    probability = np.zeros((64, 64), dtype=float)
    probability[20:40, 10:50] = 1
    result = postprocess_probability(probability)
    assert result[25, 25]
    assert not result[-1].any()


def test_normalization_preserves_model_dtype() -> None:
    result = percentile_normalize(np.arange(64, dtype=np.uint8).reshape(8, 8))
    assert result.dtype == np.float32
    assert result.min() == 0
    assert result.max() == 1


def test_boundary_loss_prefers_the_correct_interface() -> None:
    target = torch.zeros(1, 1, 64, 32)
    target[..., 30:, :] = 1
    correct = torch.where(target > 0, torch.tensor(8.0), torch.tensor(-8.0))
    shifted_target = torch.zeros_like(target)
    shifted_target[..., 40:, :] = 1
    shifted = torch.where(shifted_target > 0, torch.tensor(8.0), torch.tensor(-8.0))
    assert boundary_aware_segmentation_loss(correct, target) < boundary_aware_segmentation_loss(shifted, target)


def test_boundary_loss_backpropagates() -> None:
    logits = torch.randn(2, 1, 32, 24, requires_grad=True)
    target = torch.zeros_like(logits)
    target[..., 14:, :] = 1
    loss = boundary_aware_segmentation_loss(logits, target)
    loss.backward()
    assert torch.isfinite(loss)
    assert logits.grad is not None and torch.isfinite(logits.grad).all()
