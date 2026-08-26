import pytest

from nostos.core.response import Axis, Calibration, ResponseGeometry, ResponseSurface


def test_calibration_maps_physical_relative_and_specimen_direction():
    calibration = Calibration((2.0, 2.0), specimen_reference=100.0, specimen_direction_degrees=15.0)
    assert calibration.relative_scale(20.0) == pytest.approx(0.2)
    assert calibration.specimen_direction(170.0) == pytest.approx(5.0)


def test_response_geometry_serializes_and_rejects_duplicates():
    geometry = ResponseGeometry(Calibration((1.0, 1.0)), (64, 64))
    response = ResponseSurface(
        module="spectral",
        measurement="angular_power",
        axes=(Axis("direction", (0.0, 90.0), "degrees"),),
        values=(0.25, 0.75),
        shape=(2,),
        uncertainty=(0.02, 0.03),
    )
    geometry.add(response)
    assert geometry.to_dict()["status"] == "valid"
    with pytest.raises(ValueError, match="Duplicate"):
        geometry.add(response)


def test_response_geometry_tracks_abstention():
    geometry = ResponseGeometry(Calibration((1.0, 1.0)), (32, 32))
    geometry.abstain("UNDER_RESOLVED", "scale below four pixels", "local_thickness")
    assert geometry.status == "abstain"
