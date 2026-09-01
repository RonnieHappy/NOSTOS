from __future__ import annotations

from nostos.validation.fmd_program_final_audit import _selection_checks


def test_fmd_field_and_realization_selection_is_reproducible() -> None:
    config = {
        "source": {"acquisition_modality": "WideField", "sample": "BPAE_R"},
        "selection": {
            "seed": 26082941,
            "development_fields": [7, 15, 13, 9, 16, 17, 18, 11],
            "confirmation_fields": [20, 14, 5, 1],
            "realization_indices": {
                "7": [7, 15, 20, 32],
                "15": [21, 22, 37, 45],
                "13": [27, 30, 32, 48],
                "9": [4, 17, 36, 42],
                "16": [12, 29, 36, 40],
                "17": [5, 17, 22, 24],
                "18": [23, 34, 38, 42],
                "11": [14, 16, 42, 44],
                "20": [2, 8, 17, 33],
                "14": [3, 5, 22, 44],
                "5": [0, 1, 28, 44],
                "1": [1, 15, 19, 43],
            },
        },
    }
    result = _selection_checks(config)
    assert result["field_order_reproduced"]
    assert result["realization_selection_reproduced"]
    assert result["unused_fields_after_confirmation"] == [3, 12, 6, 8, 4, 2, 10]
