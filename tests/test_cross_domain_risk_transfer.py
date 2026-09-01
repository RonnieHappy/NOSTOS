from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from nostos.validation.cross_domain_risk_transfer import (
    CHANNELS,
    _balanced_weights,
    shared_risk_geometry,
)
from nostos.validation.selective_risk_baseline import DOMAIN_SPECS


def _spec(name: str):
    return next(item for item in DOMAIN_SPECS if item.name == name)


def test_pshg_geometry_has_frozen_channel_order_and_transform() -> None:
    row = {
        "diagnostics": {
            "components": {
                "acquisition_qc": 0.0,
                "coherence": 1.0,
                "scale_consistency": 3.0,
                "split_stack": 7.0,
            }
        }
    }
    observed = shared_risk_geometry(row, _spec("pshg_tiss_breast"))
    assert CHANNELS == ("acquisition", "identifiability", "scale", "consistency")
    assert observed == pytest.approx(np.log1p([0.0, 1.0, 3.0, 7.0]))


def test_fmd_geometry_uses_frozen_maxima_and_clip() -> None:
    row = {
        "support_components": {
            "acquisition_qc": 0.2,
            "declared_capture_noise_deficit": 0.7,
            "measurement_identifiability": 0.3,
            "orientation_resultant_risk": 1.4,
            "orientation_estimator_disagreement_risk": 0.8,
            "spectral_orientation_anisotropy_risk": 0.5,
            "scale_sampling": 40.0,
            "perturbation_stability": 0.6,
            "cross_scale_agreement": 2.0,
        }
    }
    observed = shared_risk_geometry(row, _spec("fmd_widefield"))
    assert observed == pytest.approx(np.log1p([0.7, 1.4, 20.0, 2.0]))


def test_geometry_is_label_blind() -> None:
    row = {
        "invalid": False,
        "risk_components": {
            "acquisition_qc": 0.1,
            "endpoint_support": 0.2,
            "scale_consistency": 0.3,
            "threshold_consistency": 0.4,
            "nested_support_consistency": 0.5,
        },
    }
    complemented = dict(row, invalid=True)
    assert np.array_equal(
        shared_risk_geometry(row, _spec("heaton_in_vivo_shg")),
        shared_risk_geometry(complemented, _spec("heaton_in_vivo_shg")),
    )


def test_balanced_weights_equalize_domain_and_class_mass() -> None:
    base = _spec("biosr_f_actin")
    second = replace(base, name="second")
    first_rows = [
        {"invalid": False, "reference_group_id": "a"},
        {"invalid": False, "reference_group_id": "a"},
        {"invalid": True, "reference_group_id": "b"},
    ]
    second_rows = [
        {"invalid": False, "reference_group_id": "c"},
        {"invalid": True, "reference_group_id": "d"},
        {"invalid": True, "reference_group_id": "e"},
    ]
    weights = _balanced_weights(((base, first_rows), (second, second_rows)))
    assert np.mean(weights) == pytest.approx(1.0)
    slices = (weights[:3], weights[3:])
    for rows, block in zip((first_rows, second_rows), slices, strict=True):
        labels = np.asarray([int(row["invalid"]) for row in rows])
        assert np.sum(block[labels == 0]) == pytest.approx(np.sum(block[labels == 1]))
    assert np.sum(slices[0]) == pytest.approx(np.sum(slices[1]))
