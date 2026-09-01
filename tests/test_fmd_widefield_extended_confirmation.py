from __future__ import annotations

import json
from pathlib import Path

import pytest

from nostos.validation.fmd_widefield_extended_confirmation import (
    clopper_pearson_interval,
    derive_field_order,
    derive_realization_indices,
    verify_extension_selection,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_ROOT / "configs" / "fmd_widefield_extended_confirmation_v1_5.locked.json"
)


def test_frozen_extension_is_every_remaining_hash_ranked_field() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    verify_extension_selection(config)
    order = derive_field_order(seed=26082941, excluded_field=19)
    assert order[:12] == [7, 15, 13, 9, 16, 17, 18, 11, 20, 14, 5, 1]
    assert order[12:] == [3, 12, 6, 8, 4, 2, 10]


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (3, [8, 23, 29, 34]),
        (12, [11, 12, 27, 41]),
        (6, [11, 23, 27, 44]),
        (8, [2, 15, 29, 48]),
        (4, [4, 19, 35, 49]),
        (2, [9, 24, 31, 40]),
        (10, [7, 32, 36, 37]),
    ],
)
def test_realization_hash_rule(field: int, expected: list[int]) -> None:
    assert derive_realization_indices(seed=26082941, field=field) == expected


def test_exact_field_bound_matches_preregistered_target() -> None:
    lower_four, upper_four = clopper_pearson_interval(0, 4)
    lower_eleven, upper_eleven = clopper_pearson_interval(0, 11)
    assert lower_four == 0.0
    assert upper_four == pytest.approx(0.6023646356)
    assert lower_eleven == 0.0
    assert upper_eleven == pytest.approx(0.2849141529)
    assert upper_eleven <= 0.30


def test_exact_interval_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError):
        clopper_pearson_interval(2, 1)
