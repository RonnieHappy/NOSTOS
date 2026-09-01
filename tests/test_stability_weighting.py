import numpy as np
import pytest

from nostos.features.stability_weighting import apply_stability_weights, fit_stability_weights


def test_unstable_coordinate_is_downweighted_without_labels():
    reference = np.asarray([[0, 0], [1, 1], [2, 2], [3, 3]], dtype=float)
    perturbed = reference.copy(); perturbed[:, 1] += np.asarray([20, -20, 20, -20])
    model = fit_stability_weights(reference, perturbed)
    assert model.reliability[0] > model.reliability[1]
    changed = apply_stability_weights(perturbed, model)
    assert changed.shape == reference.shape and np.isfinite(changed).all()


def test_stability_weighting_validates_pairing():
    with pytest.raises(ValueError):
        fit_stability_weights(np.ones((2, 3)), np.ones((2, 3)))
