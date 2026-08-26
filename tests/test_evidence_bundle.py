import json

from nostos.validation import evidence_bundle


def test_evidence_bundle_reports_missing_without_false_readiness(tmp_path, monkeypatch):
    spec = evidence_bundle.EvidenceSpec("one", "outputs/one.json", "test", "test receipt")
    monkeypatch.setattr(evidence_bundle, "SPECS", (spec,))
    payload = evidence_bundle.build_evidence_bundle(tmp_path, tmp_path / "bundle")
    assert payload["status"] == "incomplete_index"
    assert payload["nature_readiness"] == "not_ready"

    source = tmp_path / "outputs" / "one.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"protocol_version": "test/1.0", "status": "pass"}))
    payload = evidence_bundle.build_evidence_bundle(tmp_path, tmp_path / "bundle")
    assert payload["status"] == "complete_index"
    assert len(payload["entries"][0]["sha256"]) == 64
    assert (tmp_path / "bundle" / "checksums.sha256").is_file()


def test_evidence_bundle_accepts_string_validity(tmp_path, monkeypatch):
    spec = evidence_bundle.EvidenceSpec("one", "one.json", "test", "test receipt")
    monkeypatch.setattr(evidence_bundle, "SPECS", (spec,))
    (tmp_path / "one.json").write_text(json.dumps({"protocol_version": "test/1.0", "validity": "exploratory"}))
    payload = evidence_bundle.build_evidence_bundle(tmp_path, tmp_path / "bundle")
    assert payload["entries"][0]["reported_status"] == "exploratory"
