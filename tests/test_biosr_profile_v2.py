from pathlib import Path

from nostos.core.measurement_profile import MeasurementProfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_biosr_v2_profile_verifies_all_basis_artifacts() -> None:
    profile = MeasurementProfile.from_path(
        PROJECT_ROOT / "configs" / "biosr_widefield_measurement_profile_v2.locked.json"
    )
    assert profile.status == "threshold_calibrated"
    assert profile.evidence_status("tensor_coherence") == "calibrated"
    assert profile.evidence_status("variogram_range_vertical") == "unvalidated"
    assert len(profile.verified_artifacts) == 4
