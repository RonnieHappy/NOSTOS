from __future__ import annotations

from nostos.validation.tlt_pshg_xrd_audit import _risk_coverage_auc, _select_nearest_ties


def test_audit_tied_selection_uses_complete_larger_group_on_equal_distance() -> None:
    rows = [
        {"case_id": "a", "score": 0.1, "invalid": False},
        {"case_id": "b", "score": 0.2, "invalid": False},
        {"case_id": "c", "score": 0.2, "invalid": True},
        {"case_id": "d", "score": 0.3, "invalid": True},
    ]
    assert len(_select_nearest_ties(rows, 2, "score")) == 3
    assert 0.0 <= _risk_coverage_auc(rows, "score") <= 1.0

