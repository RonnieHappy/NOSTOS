from __future__ import annotations

from nostos.validation.failure_diagnostics import (
    best_combination_point,
    diagnose_combinations,
    threshold_scale_conflicts,
)


def _row(
    score: float,
    invalid: bool,
    *,
    endpoint: str = "a",
    structure: str = "ER",
    hard: bool = False,
    group: str = "field_1",
) -> dict:
    return {
        "structure": structure,
        "endpoint": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": hard,
        "invalid": invalid,
        "reference_group_id": group,
        "scores": {"full_contract": score},
    }


def test_best_point_uses_risk_then_coverage_tie_break() -> None:
    rows = [
        _row(0.1, False),
        _row(0.2, False),
        _row(0.3, False),
        _row(0.4, True),
    ]
    result = best_combination_point(
        rows,
        condition="full_contract",
        minimum_coverage=0.5,
    )
    assert result["best"]["threshold"] == 0.3
    assert result["best"]["coverage"] == 0.75
    assert result["best"]["risk"] == 0.0


def test_hard_abstention_counts_against_coverage() -> None:
    rows = [_row(0.1, False), _row(0.2, False, hard=True)]
    result = best_combination_point(
        rows,
        condition="full_contract",
        minimum_coverage=0.75,
    )
    assert result["status"] == "coverage_floor_unattainable"


def test_diagnosis_flags_irreducible_endpoint_failure() -> None:
    rows = [
        _row(0.1, True, endpoint="bad"),
        _row(0.2, False, endpoint="bad"),
        _row(0.3, False, endpoint="bad"),
        _row(0.4, False, endpoint="bad"),
    ]
    diagnostics = diagnose_combinations(
        rows,
        endpoints={"bad"},
        condition="full_contract",
        minimum_coverage=0.75,
        target_risk=0.1,
    )
    assert diagnostics[0]["best"]["risk"] == 0.25
    assert diagnostics[0]["passes_independent_diagnostic"] is False


def test_threshold_conflict_reports_large_scale_separation() -> None:
    diagnostics = [
        {
            "structure": "ER",
            "endpoint": "coherence",
            "best": {"threshold": 0.3},
        },
        {
            "structure": "ER",
            "endpoint": "orientation",
            "best": {"threshold": 0.99},
        },
    ]
    conflicts = threshold_scale_conflicts(diagnostics)
    assert len(conflicts) == 1
    assert conflicts[0]["absolute_separation"] == 0.69
