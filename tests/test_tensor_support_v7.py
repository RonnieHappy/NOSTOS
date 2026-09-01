from __future__ import annotations

import numpy as np

from nostos.validation.paired_acquisition_support import PairRegistration
from nostos.validation.tensor_support_v7 import (
    evaluate_tensor_pair,
    measure_resolution_margin_probe,
    measure_tensor_support,
    policy_accepts,
)


def grating(angle: float) -> np.ndarray:
    y, x = np.indices((192, 192), dtype=float)
    normal = np.deg2rad(angle + 90.0)
    coordinate = np.cos(normal) * x + np.sin(normal) * y
    return 0.5 + 0.5 * np.sin(2.0 * np.pi * coordinate / 20.0)


def registration() -> PairRegistration:
    return PairRegistration(True, (0.0, 0.0), (0.0, 0.0), 2.0, 0.0, ())


def test_identical_pair_is_valid_and_supported() -> None:
    image = grating(31.0)
    measured = measure_tensor_support(
        image,
        grid_spacing_um=0.1,
        effective_spacing_um=0.1,
        scales_um=(0.4, 0.8),
        spectral_band_cycles_per_mm=(5.0, 900.0),
    )
    rows = evaluate_tensor_pair(
        pair_id="phantom|level_01",
        reference_group_id="phantom",
        structure="phantom",
        effective_input_spacing_um=0.1,
        registration=registration(),
        input_measurement=measured,
        reference_measurement=measured,
        scales_um=(0.4, 0.8),
    )
    assert len(rows) == 4
    assert all(row["reference_eligible"] for row in rows)
    assert all(not row["invalid"] for row in rows)
    assert all(policy_accepts(row, "full_contract") for row in rows)


def test_crossing_distribution_remains_valid_when_scalar_axis_is_undefined() -> None:
    image = 0.5 * grating(20.0) + 0.5 * grating(110.0)
    measured = measure_tensor_support(
        image,
        grid_spacing_um=0.1,
        effective_spacing_um=0.1,
        scales_um=(0.4,),
        spectral_band_cycles_per_mm=(5.0, 900.0),
    )
    rows = evaluate_tensor_pair(
        pair_id="cross|level_01",
        reference_group_id="cross",
        structure="phantom",
        effective_input_spacing_um=0.1,
        registration=registration(),
        input_measurement=measured,
        reference_measurement=measured,
        scales_um=(0.4,),
    )
    orientation = next(
        row for row in rows if row["endpoint"] == "tensor_orientation_distribution"
    )
    assert orientation["reference_eligible"]
    assert orientation["derived_axis_diagnostic_only"]["reference_resultant"] < 0.15
    assert orientation["derived_axis_diagnostic_only"]["claim_eligible"] is False


def test_qc_comparator_does_not_inherit_identifiability_hard_gate() -> None:
    row = {
        "hard_abstention_reasons": [
            "input_quadrant_jackknife_drift_above_20_degrees"
        ],
        "scores": {
            "full_contract": 1.2,
            "conventional_acquisition_qc": 0.2,
            "always_emit": 0.0,
            "full_without_jackknife": 0.2,
            "full_without_perturbation": 1.2,
            "full_without_identifiability": 0.2,
        },
    }
    assert not policy_accepts(row, "full_contract")
    assert policy_accepts(row, "conventional_acquisition_qc")
    assert policy_accepts(row, "full_without_jackknife")
    assert policy_accepts(row, "full_without_identifiability")


def test_strong_resolution_margin_governs_coherence_only() -> None:
    generator = np.random.default_rng(4)
    image = generator.normal(size=(192, 192))
    measured = measure_tensor_support(
        image,
        grid_spacing_um=0.1,
        effective_spacing_um=0.1,
        scales_um=(0.4,),
        spectral_band_cycles_per_mm=(5.0, 900.0),
    )
    strong = measure_resolution_margin_probe(
        image,
        grid_spacing_um=0.1,
        effective_spacing_um=0.1,
        scales_um=(0.4,),
    )
    rows = evaluate_tensor_pair(
        pair_id="noise|level_01",
        reference_group_id="noise",
        structure="phantom",
        effective_input_spacing_um=0.1,
        registration=registration(),
        input_measurement=measured,
        reference_measurement=measured,
        scales_um=(0.4,),
        input_resolution_margin_response=strong,
        coherence_resolution_margin_threshold_fraction=1e-6,
    )
    coherence = next(row for row in rows if row["endpoint"] == "tensor_coherence")
    orientation = next(
        row for row in rows if row["endpoint"] == "tensor_orientation_distribution"
    )
    assert coherence["resolution_margin"]["governs_acceptance"] is True
    assert coherence["scores"]["full_contract"] > 1.0
    assert orientation["resolution_margin"]["governs_acceptance"] is False
    assert orientation["support_components"]["resolution_margin"] == 0.0
