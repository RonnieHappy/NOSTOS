from __future__ import annotations

import numpy as np

from nostos.validation.pshg_acquisition_shift import (
    apply_condition,
    policy_scores,
    split_rois,
)


def test_hash_split_is_deterministic_and_disjoint() -> None:
    names = [f"roi_{index}" for index in range(48)]
    first = split_rois(
        names,
        salt="frozen",
        development_rois=24,
        confirmation_rois=24,
    )
    second = split_rois(
        list(reversed(names)),
        salt="frozen",
        development_rois=24,
        confirmation_rois=24,
    )
    assert first == second
    assert set(first["development"]).isdisjoint(first["confirmation"])


def test_noise_and_motion_conditions_are_deterministic_and_shape_preserving() -> None:
    yy, xx = np.mgrid[:32, :32]
    frames = np.stack([np.sin(xx / 4.0 + index / 5.0) + yy / 32.0 + 2.0 for index in range(10)])
    condition = {"id": "compound", "blur_sigma": 1.0, "motion_radius": 2.0, "noise_snr_db": 10.0, "resample_factor": 2}
    first = apply_condition(frames, condition, roi_name="roi", seed=7)
    second = apply_condition(frames, condition, roi_name="roi", seed=7)
    assert first.shape == frames.shape
    assert np.array_equal(first, second)
    assert np.all(first >= 0)


def test_component_ablation_does_not_inherit_removed_component() -> None:
    components = {
        "acquisition_qc": 0.2,
        "coherence": 0.3,
        "scale_consistency": 4.0,
        "split_stack": 0.4,
    }
    policies = {
        "without_scale_consistency": ["acquisition_qc", "coherence", "split_stack"],
        "full_contract": ["acquisition_qc", "coherence", "scale_consistency", "split_stack"],
    }
    scores = policy_scores(components, policies)
    assert scores["without_scale_consistency"] == 0.4
    assert scores["full_contract"] == 4.0
