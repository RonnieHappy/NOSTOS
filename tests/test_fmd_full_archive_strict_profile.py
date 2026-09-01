from __future__ import annotations

import json
from pathlib import Path

from nostos.validation.fmd_full_archive_strict_profile import compile_strict_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "configs" / "fmd_full_archive_strict_support_v1_6.development.json"


def test_strict_profile_retains_only_error_free_average_of_16_cells() -> None:
    profile, audit, scored, receipt = compile_strict_profile(PROJECT_ROOT, CONFIG)
    assert profile["status"] == "operating_point_selected"
    assert audit["status"] == "operating_point_selected"
    assert receipt["primary_row_count"] == 1140
    assert len(scored) == 1140
    assert [cell["values"] for cell in profile["supported_cells"]] == [
        ["avg16", 16.0],
        ["avg16", 4.0],
        ["avg16", 8.0],
    ]
    assert profile["development_operating_point"]["accepted"] == 228
    assert profile["development_operating_point"]["coverage"] == 0.2
    assert profile["development_operating_point"]["invalid"] == 0
    assert profile["development_operating_point"][
        "fields_with_any_accepted_failure"
    ] == 0


def test_failed_average_of_8_coarse_cell_is_retained_as_unsupported() -> None:
    profile, _, _, _ = compile_strict_profile(PROJECT_ROOT, CONFIG)
    target = next(
        cell
        for cell in profile["unsupported_cells"]
        if cell["values"] == ["avg8", 16.0]
    )
    assert target["development_summary"]["invalid"] == 6
    assert target["field_event_summary"]["fields_with_any_accepted_failure"] == 2
    assert target["supported"] is False
