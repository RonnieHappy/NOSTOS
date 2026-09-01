from __future__ import annotations

from nostos.validation.heaton_shg_confirmation import invalid_endpoint


TOLERANCES = {
    "axial_resultant_absolute": 0.15,
    "foreground_occupancy_relative": 0.25,
    "median_segment_straightness_absolute": 0.10,
    "median_segment_length_relative": 0.30,
    "median_local_width_relative": 0.30,
}


def test_absolute_endpoint_invalidity_uses_strict_declared_boundary() -> None:
    invalid, metric = invalid_endpoint(
        "axial_resultant", 0.35, 0.20, denominator_floor=0.01, tolerances=TOLERANCES
    )
    assert invalid is False
    assert abs(metric - 0.15) < 1e-12
    invalid, _ = invalid_endpoint(
        "axial_resultant", 0.351, 0.20, denominator_floor=0.01, tolerances=TOLERANCES
    )
    assert invalid is True


def test_relative_endpoint_invalidity_uses_frozen_denominator_floor() -> None:
    invalid, metric = invalid_endpoint(
        "median_local_width_um", 0.14, 0.10, denominator_floor=0.20, tolerances=TOLERANCES
    )
    assert invalid is False
    assert abs(metric - 0.20) < 1e-12
    invalid, metric = invalid_endpoint(
        "median_local_width_um", 0.17, 0.10, denominator_floor=0.20, tolerances=TOLERANCES
    )
    assert invalid is True
    assert abs(metric - 0.35) < 1e-12


def test_nonfinite_or_missing_measurement_is_invalid() -> None:
    invalid, metric = invalid_endpoint(
        "foreground_occupancy", None, 0.4, denominator_floor=0.1, tolerances=TOLERANCES
    )
    assert invalid is True
    assert metric is None
