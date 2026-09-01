import numpy as np

from nostos.segmentation.metrics import class_scores, confusion_matrix, symmetric_boundary_error_um


def test_segmentation_scores_are_exact_for_simple_masks():
    target = np.array([[0, 1], [1, 1]])
    prediction = np.array([[0, 1], [0, 1]])
    scores = class_scores(confusion_matrix(prediction, target, classes=2))
    assert np.isclose(scores["dice"][1], 0.8)
    assert np.isclose(scores["iou"][1], 2 / 3)


def test_boundary_error_is_in_physical_units():
    target = np.zeros((10, 10), dtype=bool)
    prediction = np.zeros_like(target)
    target[2:7, 2:7] = True
    prediction[2:7, 3:8] = True
    assert np.isclose(symmetric_boundary_error_um(prediction, target, 2.0, percentile=100), 2.0)
