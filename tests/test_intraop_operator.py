import json
from pathlib import Path

from nostos.intraop.operator import apply_operator_evidence_boundary, verify_public_acquisition_bundle


def _payload() -> dict:
    return {
        "status": "valid",
        "measurement": {"evidence_status": "confirmed"},
        "profile": {},
        "validity_reasons": [],
        "clinical_output": {"status": "withheld"},
    }


def test_new_acquisition_is_not_promoted_by_format_alone() -> None:
    bounded = apply_operator_evidence_boundary(
        _payload(),
        {"verified": False, "status": "unverified_new_acquisition"},
    )
    assert bounded["status"] == "review"
    assert bounded["measurement"]["evidence_status"] == "unvalidated_new_acquisition"
    assert "acquisition_provenance_not_independently_verified" in bounded["validity_reasons"]
    assert bounded["clinical_output"]["status"] == "withheld"


def test_complete_hash_locked_bundle_is_recognized(tmp_path: Path) -> None:
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "selected_source_files": [
                    {"relative_path": "case_a/frame.tif", "bytes": 4, "sha256": "abc"},
                    {"relative_path": "case_a/R2.tif", "bytes": 5, "sha256": "def"},
                    {"relative_path": "case_a/FI.tif", "bytes": 6, "sha256": "ignored"},
                ]
            }
        ),
        encoding="utf-8",
    )
    result = verify_public_acquisition_bundle(
        [
            {"name": "frame.tif", "bytes": 4, "sha256": "abc"},
            {"name": "R2.tif", "bytes": 5, "sha256": "def"},
        ],
        lock,
    )
    assert result["verified"] is True
    assert result["matched_group"] == "case_a"


def test_partial_or_modified_bundle_is_not_verified(tmp_path: Path) -> None:
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "selected_source_files": [
                    {"relative_path": "case_a/frame.tif", "bytes": 4, "sha256": "abc"},
                    {"relative_path": "case_a/R2.tif", "bytes": 5, "sha256": "def"},
                ]
            }
        ),
        encoding="utf-8",
    )
    result = verify_public_acquisition_bundle(
        [{"name": "frame.tif", "bytes": 4, "sha256": "changed"}],
        lock,
    )
    assert result["verified"] is False
