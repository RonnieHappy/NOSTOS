import hashlib
import json
from pathlib import Path

import pytest

from nostos.core.measurement_profile import MeasurementProfile


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_fixture(tmp_path: Path) -> tuple[Path, Path]:
    configs = tmp_path / "configs"
    manifests = tmp_path / "manifests"
    audit_directory = tmp_path / "outputs" / "audit"
    configs.mkdir()
    manifests.mkdir()
    audit_directory.mkdir(parents=True)
    receipt = manifests / "receipt.json"
    audit = audit_directory / "pilot_audit.json"
    protocol = configs / "protocol.json"
    receipt.write_text('{"receipt":1}\n', encoding="utf-8")
    audit.write_text('{"audit":1}\n', encoding="utf-8")
    protocol.write_text('{"protocol":1}\n', encoding="utf-8")
    payload = {
        "schema_version": "nostos-acquisition-measurement-profile/1.0",
        "profile_id": "test-profile",
        "status": "provisional_test",
        "basis": {
            "artifact_receipt_path": "manifests/receipt.json",
            "artifact_receipt_bytes": receipt.stat().st_size,
            "artifact_receipt_sha256": _sha256(receipt),
            "pilot_audit_path": "outputs/audit/pilot_audit.json",
            "pilot_audit_bytes": audit.stat().st_size,
            "pilot_audit_sha256": _sha256(audit),
        },
        "analysis_contract": {
            "protocol_config_path": "configs/protocol.json",
            "protocol_config_sha256": _sha256(protocol),
        },
        "eligible_for_threshold_calibration": [],
        "disabled_for_this_acquisition_profile": {},
    }
    profile = configs / "profile.json"
    profile.write_text(json.dumps(payload), encoding="utf-8")
    return profile, receipt


def test_measurement_profile_verifies_every_linked_artifact(tmp_path: Path):
    profile_path, _ = _profile_fixture(tmp_path)
    profile = MeasurementProfile.from_path(profile_path)
    assert len(profile.verified_artifacts) == 3


def test_measurement_profile_fails_closed_after_artifact_tampering(tmp_path: Path):
    profile_path, receipt = _profile_fixture(tmp_path)
    receipt.write_text('{"receipt":2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        MeasurementProfile.from_path(profile_path)
