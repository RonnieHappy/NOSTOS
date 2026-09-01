from __future__ import annotations

import json
from pathlib import Path

from nostos.core.measurement_profile import MeasurementProfile
from nostos.validation.paired_acquisition_support import BioSRPairRecord
from nostos.validation.confirmation_v6 import select_confirmation_cells


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _record(cell: str) -> BioSRPairRecord:
    return BioSRPairRecord(
        structure="Microtubules",
        cell_id=cell,
        signal_level=1,
        pair_id=f"Microtubules|{cell}|level_01",
        reference_group_id=f"Microtubules|{cell}",
        input_member="input.mrc",
        reference_member="reference.mrc",
        input_frames=9,
        input_shape_yx=(64, 64),
        reference_shape_yx=(128, 128),
        input_grid_spacing_um=0.0626,
        effective_input_spacing_um=0.0626,
        reference_spacing_um=0.0313,
        input_header_spacing_yx_um=(0.0626, 0.0626),
        reference_header_spacing_yx_um=(0.0313, 0.0313),
        physical_field_of_view_yx_um=(4.0064, 4.0064),
        archive_layout="shared_reference_flat",
    )


def test_confirmation_field_selection_is_order_invariant_and_hash_only() -> None:
    cells = [f"Cell_{index:03d}" for index in range(1, 21)]
    forward = {cell: [_record(cell)] for cell in cells}
    reverse = {cell: [_record(cell)] for cell in reversed(cells)}
    assert select_confirmation_cells(
        forward,
        structure="Microtubules",
        count=8,
    ) == select_confirmation_cells(
        reverse,
        structure="Microtubules",
        count=8,
    )


def test_v6_profile_and_config_exclude_failed_axis_variograms() -> None:
    config = json.loads(
        (
            PROJECT_ROOT / "configs" / "paired_acquisition_support_v6.locked.json"
        ).read_text(encoding="utf-8")
    )
    profile = MeasurementProfile.from_path(
        PROJECT_ROOT / "configs" / "biosr_widefield_measurement_profile_v2.locked.json"
    )
    assert config["protocol_version"] == "nostos-paired-acquisition-support/6.0"
    assert "variogram_range_vertical" not in profile.eligible_endpoints
    assert "variogram_range_vertical" in profile.disabled_endpoints
    assert all(
        "variogram" not in endpoint
        for endpoints in config["endpoint_families"].values()
        for endpoint in endpoints
    )


def test_v6_thresholds_match_the_development_audit_exactly() -> None:
    config = json.loads(
        (
            PROJECT_ROOT / "configs" / "paired_acquisition_support_v6.locked.json"
        ).read_text(encoding="utf-8")
    )
    audit = json.loads(
        (
            PROJECT_ROOT
            / "outputs"
            / "nostos0-biosr-v6-family-threshold-development"
            / "family_threshold_calibration.json"
        ).read_text(encoding="utf-8")
    )
    observed = config["policy_thresholds"]["full_contract"]
    expected = {
        family: result["threshold"]
        for family, result in audit["policies"]["full_contract"]["families"].items()
    }
    assert observed == expected
    assert config["policy_semantics"]["structure_specific_thresholds"] is False
