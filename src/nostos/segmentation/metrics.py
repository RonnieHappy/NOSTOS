from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt


def confusion_matrix(prediction: np.ndarray, target: np.ndarray, classes: int) -> np.ndarray:
    prediction = np.asarray(prediction)
    target = np.asarray(target)
    if prediction.shape != target.shape:
        raise ValueError("prediction and target must have identical shapes")
    valid = (target >= 0) & (target < classes) & (prediction >= 0) & (prediction < classes)
    encoded = classes * target[valid].astype(np.int64) + prediction[valid].astype(np.int64)
    return np.bincount(encoded, minlength=classes * classes).reshape(classes, classes)


def class_scores(matrix: np.ndarray) -> dict[str, np.ndarray]:
    matrix = np.asarray(matrix, dtype=np.float64)
    true_positive = np.diag(matrix)
    target_total = matrix.sum(axis=1)
    predicted_total = matrix.sum(axis=0)
    union = target_total + predicted_total - true_positive
    denominator = target_total + predicted_total
    return {
        "dice": np.divide(2 * true_positive, denominator, out=np.full_like(true_positive, np.nan), where=denominator > 0),
        "iou": np.divide(true_positive, union, out=np.full_like(true_positive, np.nan), where=union > 0),
        "recall": np.divide(true_positive, target_total, out=np.full_like(true_positive, np.nan), where=target_total > 0),
        "precision": np.divide(true_positive, predicted_total, out=np.full_like(true_positive, np.nan), where=predicted_total > 0),
    }


def symmetric_boundary_error_um(
    prediction: np.ndarray, target: np.ndarray, pixel_size_um: float, percentile: float = 95.0
) -> float:
    prediction = np.asarray(prediction, dtype=bool)
    target = np.asarray(target, dtype=bool)
    if prediction.shape != target.shape or pixel_size_um <= 0:
        raise ValueError("masks must match and pixel_size_um must be positive")
    pred_edge = prediction ^ binary_erosion(prediction)
    target_edge = target ^ binary_erosion(target)
    if not pred_edge.any() or not target_edge.any():
        return float("inf")
    pred_to_target = distance_transform_edt(~target_edge)[pred_edge]
    target_to_pred = distance_transform_edt(~pred_edge)[target_edge]
    distances = np.concatenate((pred_to_target, target_to_pred)) * pixel_size_um
    return float(np.percentile(distances, percentile))


def section_segmentation_metrics(
    prediction: np.ndarray,
    target: np.ndarray,
    *,
    pixel_size_um: float,
    classes: int = 6,
    cartilage_class: int = 1,
) -> dict[str, float | bool | list[list[int]]]:
    matrix = confusion_matrix(prediction, target, classes)
    scores = class_scores(matrix)
    boundary = symmetric_boundary_error_um(
        np.asarray(prediction) == cartilage_class,
        np.asarray(target) == cartilage_class,
        pixel_size_um,
    )
    predicted_cartilage = bool(np.any(np.asarray(prediction) == cartilage_class))
    reference_cartilage = bool(np.any(np.asarray(target) == cartilage_class))
    dice = float(scores["dice"][cartilage_class])
    return {
        "cartilage_dice": dice,
        "cartilage_iou": float(scores["iou"][cartilage_class]),
        "cartilage_precision": float(scores["precision"][cartilage_class]),
        "cartilage_recall": float(scores["recall"][cartilage_class]),
        "cartilage_boundary_hd95_um": boundary,
        "predicted_cartilage": predicted_cartilage,
        "reference_cartilage": reference_cartilage,
        "catastrophic": (not predicted_cartilage) or (not np.isfinite(dice)) or dice < 0.5,
        "confusion_matrix": matrix.tolist(),
    }
