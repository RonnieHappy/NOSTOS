import json

from nostos.validation import bone_program_summary


def _write(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_condition_by_perturbation_reports_selective_risk():
    rows = [
        {"perturbation": "blur", "invalid": True, "accept": {"full": True}},
        {"perturbation": "blur", "invalid": False, "accept": {"full": False}},
        {"perturbation": "noise", "invalid": False, "accept": {"full": True}},
    ]
    result = bone_program_summary._condition_by_perturbation(rows, "full")
    assert result["blur"]["coverage"] == 0.5
    assert result["blur"]["silent_invalid_risk"] == 1.0
    assert result["noise"]["silent_invalid_risk"] == 0.0


def test_missing_receipt_fails_closed(tmp_path):
    try:
        bone_program_summary.build_bone_program_summary(tmp_path, tmp_path / "out")
    except FileNotFoundError as error:
        assert "Missing required bone-program receipts" in str(error)
    else:
        raise AssertionError("The summary must not build from incomplete evidence.")
