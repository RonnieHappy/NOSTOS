from __future__ import annotations

import pytest

from nostos.validation.finite_sample_risk import (
    audit_nested_measurement_uncertainty,
    clopper_pearson_interval,
)


def test_zero_event_exact_interval_is_not_zero_width() -> None:
    lower, upper = clopper_pearson_interval(0, 64)
    assert lower == 0.0
    assert 0.05 < upper < 0.06


def test_four_clean_groups_still_have_wide_population_bound() -> None:
    _, upper = clopper_pearson_interval(0, 4)
    assert 0.60 < upper < 0.61


def test_invalid_counts_fail_closed() -> None:
    with pytest.raises(ValueError):
        clopper_pearson_interval(5, 4)


def test_nested_audit_separates_rows_from_independent_groups() -> None:
    rows = []
    for group in ("fov1", "fov2"):
        for index in range(3):
            rows.append(
                {
                    "candidate_hard_abstention": False,
                    "calibrated_risk": 0.1,
                    "invalid": group == "fov2" and index == 0,
                    "reference_group_id": group,
                    "conditional_cell": {"key": "cell", "values": ["avg16", 8.0]},
                }
            )
    audit = audit_nested_measurement_uncertainty(
        rows,
        predicted_risk_threshold=0.2,
        source_audit_file_sha256="a" * 64,
        source_audit_content_sha256="b" * 64,
        scored_rows_file_sha256="c" * 64,
    )
    assert audit["nested_measurement_interval"]["events"] == 1
    assert audit["nested_measurement_interval"]["trials"] == 6
    assert audit["independent_group_any_failure_interval"]["events"] == 1
    assert audit["independent_group_any_failure_interval"]["trials"] == 2
