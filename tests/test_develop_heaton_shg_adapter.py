from __future__ import annotations

from scripts.develop_heaton_shg_adapter import _fisher_mean, select_per_mouse


def test_adapter_selection_uses_two_fields_per_mouse_deterministically() -> None:
    rows = [
        {"mouse": mouse, "source": f"{mouse}/field_{index}.tif", "field_stem": f"{mouse}_{index}"}
        for mouse in ("a", "b", "c")
        for index in range(5)
    ]
    first = select_per_mouse(rows, fields_per_mouse=2, salt="frozen")
    second = select_per_mouse(list(reversed(rows)), fields_per_mouse=2, salt="frozen")
    assert first == second
    assert len(first) == 6
    assert {mouse: sum(row["mouse"] == mouse for row in first) for mouse in ("a", "b", "c")} == {"a": 2, "b": 2, "c": 2}


def test_fisher_mean_is_monotone_with_agreement() -> None:
    low = _fisher_mean({"a": 0.1, "b": 0.2})
    high = _fisher_mean({"a": 0.7, "b": 0.8})
    assert high > low

