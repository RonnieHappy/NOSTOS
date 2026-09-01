from __future__ import annotations

from nostos.validation.profile_domain_guard import (
    apply_profile_domain_guard,
    assess_profile_context,
)


CERTIFIED = {
    "acquisition_modality": "WideField",
    "sample": "BPAE_R",
    "calibration_status": "pixel_relative_only",
}
REQUIRED = tuple(CERTIFIED)


def test_exact_certified_context_is_applicable() -> None:
    result = assess_profile_context(
        CERTIFIED, certified=CERTIFIED, required_fields=REQUIRED
    )
    assert result["applicable"] is True
    assert result["abstention_reasons"] == []


def test_mismatch_and_missing_context_fail_closed() -> None:
    mismatch = assess_profile_context(
        {**CERTIFIED, "sample": "BPAE_G"},
        certified=CERTIFIED,
        required_fields=REQUIRED,
    )
    missing = assess_profile_context(
        {"acquisition_modality": "WideField", "sample": "BPAE_R"},
        certified=CERTIFIED,
        required_fields=REQUIRED,
    )
    assert mismatch["applicable"] is False
    assert mismatch["abstention_reasons"] == [
        "profile_claim_boundary:mismatch:sample"
    ]
    assert missing["applicable"] is False
    assert missing["abstention_reasons"] == [
        "profile_claim_boundary:missing:calibration_status"
    ]


def test_guard_preserves_in_scope_and_abstains_out_of_scope() -> None:
    base = {
        "candidate_hard_abstention": False,
        "calibrated_risk": 0.1,
        "calibration_status": "pixel_relative_only",
        "metadata": {"acquisition_modality": "WideField", "sample": "BPAE_R"},
    }
    outside = {
        **base,
        "metadata": {"acquisition_modality": "WideField", "sample": "BPAE_G"},
    }
    guarded = apply_profile_domain_guard(
        [base, outside], certified=CERTIFIED, required_fields=REQUIRED
    )
    assert guarded[0]["candidate_hard_abstention"] is False
    assert guarded[0]["calibrated_risk"] == 0.1
    assert guarded[1]["candidate_hard_abstention"] is True
    assert guarded[1]["calibrated_risk"] == 1.0
    assert base["candidate_hard_abstention"] is False

