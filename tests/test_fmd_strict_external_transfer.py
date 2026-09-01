from __future__ import annotations

import json
from pathlib import Path

import pytest

from nostos.validation.fmd_strict_external_transfer import (
    derive_transfer_field_order,
    derive_transfer_realizations,
    load_transfer_inputs,
    verify_transfer_selection,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "fmd_strict_external_transfer_v1_6.locked.json"


def test_locked_transfer_configuration_and_profile_identity() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    verify_transfer_selection(config)
    loaded, _development, _base, strict, _measurement, _refs = load_transfer_inputs(
        PROJECT_ROOT, CONFIG_PATH
    )
    assert loaded["protocol_id"] == "fmd-strict-external-transfer-v1-6"
    assert [cell["values"] for cell in strict["supported_cells"]] == [
        ["avg16", 16.0],
        ["avg16", 4.0],
        ["avg16", 8.0],
    ]
    assert sum(len(source["confirmation_fields"]) for source in loaded["sources"]) == 14


@pytest.mark.parametrize(
    ("dataset_key", "expected"),
    [
        ("Confocal_BPAE_R", [7, 19, 17, 2, 3, 6, 16]),
        ("WideField_BPAE_G", [1, 11, 5, 16, 3, 15, 19]),
    ],
)
def test_transfer_field_selection(dataset_key: str, expected: list[int]) -> None:
    assert derive_transfer_field_order(seed=26083161, dataset_key=dataset_key)[:7] == expected


@pytest.mark.parametrize(
    ("dataset_key", "field", "expected"),
    [
        ("Confocal_BPAE_R", 7, [29, 33, 42, 48]),
        ("Confocal_BPAE_R", 19, [2, 3, 8, 39]),
        ("Confocal_BPAE_R", 17, [10, 24, 39, 47]),
        ("Confocal_BPAE_R", 2, [35, 41, 43, 45]),
        ("Confocal_BPAE_R", 3, [5, 8, 13, 18]),
        ("Confocal_BPAE_R", 6, [6, 7, 21, 29]),
        ("Confocal_BPAE_R", 16, [10, 40, 46, 48]),
        ("WideField_BPAE_G", 1, [9, 27, 35, 44]),
        ("WideField_BPAE_G", 11, [3, 9, 19, 46]),
        ("WideField_BPAE_G", 5, [7, 15, 18, 36]),
        ("WideField_BPAE_G", 16, [5, 26, 27, 48]),
        ("WideField_BPAE_G", 3, [13, 18, 25, 45]),
        ("WideField_BPAE_G", 15, [1, 27, 43, 46]),
        ("WideField_BPAE_G", 19, [12, 14, 18, 47]),
    ],
)
def test_transfer_realization_selection(
    dataset_key: str, field: int, expected: list[int]
) -> None:
    assert derive_transfer_realizations(
        seed=26083161, dataset_key=dataset_key, field=field
    ) == expected
