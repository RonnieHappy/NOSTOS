from __future__ import annotations

from nostos.validation.fmd_strict_external_transfer_audit_v1_6_1 import (
    field_event_summary_zero_safe,
)


def test_zero_coverage_is_a_defined_failed_reporting_state() -> None:
    rows = [
        {
            "reference_group_id": "Confocal_BPAE_R|fov1",
            "candidate_hard_abstention": True,
            "calibrated_risk": 1.0,
            "invalid": False,
        }
    ]
    result = field_event_summary_zero_safe(
        rows,
        threshold=0.63,
        expected_groups=["Confocal_BPAE_R|fov1"],
        confidence=0.95,
    )
    assert result["accepted_emissions"] == 0
    assert result["invalid_accepted_emissions"] == 0
    assert result["accepted_emission_risk"] is None
    assert result["accepted_emission_exact_ci_descriptive"] is None
    assert result["zero_coverage"] is True
    assert result["fields_with_any_accepted_failure"] == 0


def test_nonzero_coverage_retains_exact_risk_reporting() -> None:
    rows = [
        {
            "reference_group_id": "WideField_BPAE_G|fov1",
            "candidate_hard_abstention": False,
            "calibrated_risk": 0.1,
            "invalid": True,
        },
        {
            "reference_group_id": "WideField_BPAE_G|fov1",
            "candidate_hard_abstention": False,
            "calibrated_risk": 0.2,
            "invalid": False,
        },
    ]
    result = field_event_summary_zero_safe(
        rows,
        threshold=0.63,
        expected_groups=["WideField_BPAE_G|fov1"],
        confidence=0.95,
    )
    assert result["accepted_emissions"] == 2
    assert result["invalid_accepted_emissions"] == 1
    assert result["accepted_emission_risk"] == 0.5
    assert result["accepted_emission_exact_ci_descriptive"] is not None
    assert result["zero_coverage"] is False
    assert result["fields_with_any_accepted_failure"] == 1

