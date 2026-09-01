from __future__ import annotations

import hashlib

from nostos.validation.computational_release_audit import (
    derive_computational_audit_status,
    registered_file_matches,
    scan_manuscript_claims,
)


def test_computational_audit_fails_closed() -> None:
    assert (
        derive_computational_audit_status({"integrity": True, "science": True})
        == "verified_computational_release_with_external_blockers"
    )
    assert derive_computational_audit_status({"integrity": True, "science": False}) == "failed"
    assert derive_computational_audit_status({}) == "failed"


def test_registered_file_match_verifies_size_and_sha256(tmp_path) -> None:
    payload = b"frozen evidence\n"
    path = tmp_path / "receipt.json"
    path.write_bytes(payload)
    record = {
        "path": "receipt.json",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    assert registered_file_matches(tmp_path.resolve(), record)
    record["bytes"] += 1
    assert not registered_file_matches(tmp_path.resolve(), record)


def test_registered_file_match_rejects_path_traversal(tmp_path) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    record = {
        "path": "../outside.json",
        "bytes": outside.stat().st_size,
        "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
    }
    assert not registered_file_matches(tmp_path.resolve(), record)


def test_manuscript_scope_scan_requires_computational_boundary() -> None:
    safe = (
        "The claim evaluated here is computational. The present work does not "
        "establish biological interpretation, diagnosis, mechanics, clinical "
        "usefulness or intraoperative performance."
    )
    result = scan_manuscript_claims(safe)
    assert not result["missing_claim_boundary_phrases"]
    assert not result["overclaim_hits"]
    unsafe = scan_manuscript_claims(safe + " The software is ready for clinical use.")
    assert unsafe["overclaim_hits"] == ["ready for clinical use"]

