from nostos.validation.final_audit import derive_audit_status


def test_terminal_audit_fails_closed():
    assert derive_audit_status({"a": True, "b": True}) == "complete_with_external_blockers"
    assert derive_audit_status({"a": True, "b": False}) == "failed"
    assert derive_audit_status({}) == "failed"

