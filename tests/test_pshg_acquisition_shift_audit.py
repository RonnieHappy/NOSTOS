from __future__ import annotations

from nostos.validation.pshg_acquisition_shift_audit import _aurc, _predict, independent_split


def test_independent_split_is_order_invariant() -> None:
    names = ["r4", "r1", "r3", "r2"]
    first = independent_split(names, salt="frozen", development=2)
    second = independent_split(list(reversed(names)), salt="frozen", development=2)
    assert first == second
    assert set(first["development"]).isdisjoint(first["confirmation"])


def test_independent_prediction_interpolates_and_clips() -> None:
    risk_map = {"x_thresholds": [1.0, 3.0], "y_thresholds": [0.1, 0.9]}
    assert _predict(0.0, risk_map) == 0.1
    assert _predict(2.0, risk_map) == 0.5
    assert _predict(4.0, risk_map) == 0.9


def test_independent_aurc_groups_tied_scores() -> None:
    rows = [
        {"case_id": "a", "calibrated_risk": 0.1, "invalid": False},
        {"case_id": "b", "calibrated_risk": 0.1, "invalid": True},
        {"case_id": "c", "calibrated_risk": 0.9, "invalid": True},
    ]
    assert abs(_aurc(rows) - (0.5 / 3.0 + (0.5 + 2.0 / 3.0) / 2.0 / 3.0)) < 1e-12
