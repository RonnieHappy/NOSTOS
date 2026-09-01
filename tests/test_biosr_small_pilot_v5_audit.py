from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "audit_biosr_small_pilot_v5.py"
SPEC = importlib.util.spec_from_file_location("audit_biosr_small_pilot_v5", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _row(
    case: int,
    *,
    invalid: bool,
    score: float,
    endpoint: str = "tensor_coherence",
    field: str | None = None,
) -> dict:
    return {
        "case_id": f"case-{case}",
        "pair_id": f"pair-{case}",
        "reference_group_id": field or f"field-{case}",
        "structure": "ER",
        "endpoint": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": False,
        "invalid": invalid,
        "error": 0.2 if invalid else 0.02,
        "scores": {
            "full_contract": score,
            "always_emit": 0.0,
            "conventional_acquisition_qc": score,
        },
        "metadata": {"signal_level_ordinal": 1},
    }


def test_summary_reports_silent_invalids_at_unit_boundary() -> None:
    rows = [
        _row(1, invalid=False, score=0.2),
        _row(2, invalid=True, score=0.8),
        _row(3, invalid=True, score=1.4),
    ]
    summary = AUDIT.summarize_subset(rows)
    assert summary["invalid_cases"] == 2
    assert summary["unit_boundary"]["accepted_cases"] == 2
    assert summary["unit_boundary"]["silent_invalid_cases"] == 1
    assert summary["unit_boundary"]["selective_risk"] == pytest.approx(0.5)
    assert summary["unit_boundary"]["invalid_rejection_fraction"] == pytest.approx(0.5)


def test_endpoint_profile_status_is_explicit() -> None:
    profile = {
        "eligible_for_threshold_calibration": ["tensor_coherence"],
        "disabled_for_this_acquisition_profile": {"spectral_scale": "failed"},
    }
    rows = [
        _row(1, invalid=False, score=0.2),
        _row(2, invalid=True, score=2.0, endpoint="spectral_scale"),
    ]
    summaries = AUDIT.endpoint_summaries(rows, profile)
    statuses = {row["endpoint"]: row["observed_status"] for row in summaries}
    assert statuses["tensor_coherence"] == "zero_observed_failures_in_eligible_pilot_cases"
    assert statuses["spectral_scale"] == "disabled_by_acquisition_profile"


def test_clustered_bootstrap_is_deterministic_and_field_clustered() -> None:
    rows = [
        _row(1, invalid=False, score=0.2, field="field-a"),
        _row(2, invalid=False, score=0.3, field="field-a"),
        _row(3, invalid=True, score=1.2, field="field-b"),
        _row(4, invalid=True, score=1.3, field="field-b"),
    ]
    first = AUDIT.clustered_unit_boundary_bootstrap(rows, draws=256, seed=9)
    second = AUDIT.clustered_unit_boundary_bootstrap(rows, draws=256, seed=9)
    assert first == second
    assert first["resampling_unit"] == "reference_group_id, stratified by structure"
    assert first["unit_boundary_selective_risk"]["finite_draws"] > 0


def test_coverage_landmarks_respect_tied_score_blocks() -> None:
    rows = [
        _row(1, invalid=False, score=0.1),
        _row(2, invalid=False, score=0.2),
        _row(3, invalid=True, score=0.2),
        _row(4, invalid=True, score=0.9),
    ]
    landmarks = AUDIT.coverage_landmarks(rows, "full_contract", targets=(0.5, 0.75))
    assert landmarks["0.50"]["coverage"] == pytest.approx(0.25)
    assert landmarks["0.75"]["coverage"] == pytest.approx(0.75)
    assert landmarks["0.75"]["risk"] == pytest.approx(1 / 3)
