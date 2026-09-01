from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_v7_1_changes_only_declared_nonlinear_metadata_and_scope() -> None:
    original = json.loads(
        (ROOT / "configs/paired_acquisition_tensor_v7.locked.json").read_text()
    )
    amended = json.loads(
        (
            ROOT
            / "configs/paired_acquisition_tensor_v7_1_nonlinear.locked.json"
        ).read_text()
    )
    assert original["raw_sim_sampling_um"] == 0.0626
    assert amended["raw_sim_sampling_um"] == 0.0604
    assert amended["physical_tensor"]["physical_scales_um"] == original[
        "physical_tensor"
    ]["physical_scales_um"]
    assert amended["endpoints"] == original["endpoints"]
    assert amended["support_contract"][
        "coherence_only_resolution_margin"
    ]["threshold_fraction_of_endpoint_tolerance"] == original[
        "support_contract"
    ]["coherence_only_resolution_margin"][
        "threshold_fraction_of_endpoint_tolerance"
    ]
    assert amended["confirmation"]["primary_safety_rules"] == original[
        "confirmation"
    ]["primary_safety_rules"]
    assert amended["confirmation"][
        "separate_incremental_coherence_utility_rules"
    ] == original["confirmation"][
        "separate_incremental_coherence_utility_rules"
    ]
    assert amended["confirmation"]["selected_cells"] == json.loads(
        (
            ROOT
            / "manifests/paired_acquisition_tensor_v7_confirmation_lock.json"
        ).read_text()
    )["confirmation"]["selected_cells"]["F-actin_nonlinear"]


def test_header_failure_receipt_certifies_zero_nonlinear_pixel_decode() -> None:
    receipt = json.loads(
        (
            ROOT
            / "manifests/paired_acquisition_tensor_v7_nonlinear_header_failure_receipt.json"
        ).read_text()
    )
    assert receipt["access_audit"]["nonlinear_pixel_arrays_decoded"] == 0
    assert receipt["access_audit"]["nonlinear_endpoint_outcomes_computed"] == 0
    assert receipt["observed_header_metadata"][
        "uniform_across_archive"
    ] is True
    assert receipt["observed_header_metadata"][
        "spacing_ratio_raw_to_reference"
    ] == pytest.approx([3.0, 3.0], abs=1e-6)
