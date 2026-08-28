from pathlib import Path

from nostos.validation import replication


def test_replication_receipt_is_machine_verifiable(tmp_path: Path, monkeypatch) -> None:
    def write(path: Path, name: str, payload: dict) -> dict:
        path.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(__import__("json").dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(replication, "run_frozen_validation", lambda p: write(p, "validation.json", {
        "status": "pass", "summary": {"constructs_registered": 9, "module_gates_passed": 5, "module_gates_total": 5}}))
    monkeypatch.setattr(replication, "write_benchmark_receipt", lambda p: write(p, "representation_benchmark.json", {
        "results": [{"representation": "nostos_response_curves", "balanced_accuracy": 1.0},
                    {"representation": "conventional_scalar", "balanced_accuracy": .9375},
                    {"representation": "naive_response_summaries", "balanced_accuracy": .9375}]}))
    monkeypatch.setattr(replication, "run_module_perturbation_matrix", lambda p: write(p, "module_perturbation_matrix.json", {
        "summary": {"passed": 24, "required_tests": 24, "mask_sensitivity_tests": 2}}))
    monkeypatch.setattr(replication, "_revision", lambda _: "abc123")
    payload = replication.run_replication_challenge(
        tmp_path / "challenge", tmp_path, "test-lab",
        affiliation="Independent Institute", unaided=True,
        author_environment=False, assistance="none", source_kind="release_archive",
    )
    assert payload["status"] == "pass"
    assert payload["operator"] == "test-lab"
    assert payload["environment"]["git_revision"] == "abc123"
    assert len(payload["artifacts"]) == 3
    assert all(len(item["sha256"]) == 64 for item in payload["artifacts"])
    verified = replication.verify_replication_package(tmp_path / "challenge/replication_receipt.json")
    assert verified["status"] == "eligible_independent_pass"
    assert verified["independent_execution_eligible"] is True

    artifact = tmp_path / "challenge" / payload["artifacts"][0]["path"]
    artifact.write_text("tampered", encoding="utf-8")
    rejected = replication.verify_replication_package(tmp_path / "challenge/replication_receipt.json")
    assert rejected["status"] == "fail"
    assert rejected["checks"]["all_artifact_hashes_match"] is False
