import json

from nostos.validation.comparator_conformance import write_comparator_conformance_receipt


def test_comparator_audit_writes_machine_readable_claim_gate(tmp_path):
    payload = write_comparator_conformance_receipt(tmp_path)
    assert payload["status"] in {"pass", "fail"}
    assert {gate["distribution"] for gate in payload["gates"]} == {"kymatio", "pyradiomics"}
    assert "may not be called IBSI radiomics" in payload["claim_rule"]
    receipt = json.loads((tmp_path / "comparator_conformance.json").read_text())
    assert receipt["protocol_version"].endswith("/1.0")
