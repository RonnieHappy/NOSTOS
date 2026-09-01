from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "audit_biosr_score_design.py"
SPEC = importlib.util.spec_from_file_location("audit_biosr_score_design", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _row(endpoint: str, measurement: float, *, scale: float = 0.5008) -> dict:
    return {
        "case_id": f"p1|{endpoint}|{scale}",
        "pair_id": "p1",
        "reference_group_id": "g1",
        "structure": "CCPs",
        "development_partition": "score_design",
        "endpoint": endpoint,
        "requested_scale_um": scale,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "invalid": endpoint == "tensor_orientation",
        "hard_abstention": False,
        "input_measurement": measurement,
        "support_components": {
            "acquisition_qc": 0.1,
            "physical_sampling": 0.0,
            "perturbation_stability": 0.2,
            "cross_scale_agreement": 0.3,
        },
        "scores": {"full_contract": 0.3},
    }


def test_orientation_observability_is_input_only_and_scale_matched() -> None:
    config = json.loads(AUDIT.CANDIDATE_CONFIG.read_text(encoding="utf-8"))
    rows = [_row("tensor_orientation", 42.0), _row("tensor_coherence", 0.10)]
    AUDIT.add_locked_candidate_scores(rows, config)
    orientation = rows[0]
    coherence = rows[1]
    assert orientation["support_components"]["orientation_observability"] == pytest.approx(1.5)
    assert orientation["scores"]["v2_full_max_plus_orientation_observability"] == pytest.approx(1.5)
    assert orientation["scores"]["robustness_max_plus_orientation_observability"] == pytest.approx(1.5)
    assert coherence["support_components"]["orientation_observability"] == 0.0
    assert coherence["scores"]["v2_full_max_plus_orientation_observability"] == pytest.approx(0.3)


def test_candidate_lock_verifies() -> None:
    receipt = AUDIT.verify_candidate_lock()
    assert receipt["stage"] == "score_design_candidate_lock_after_calibration_correction"


def test_non_design_partition_is_refused_before_analysis(tmp_path: Path) -> None:
    rows_path = tmp_path / "endpoint_cases.jsonl"
    row = _row("tensor_coherence", 0.2)
    row["development_partition"] = "threshold_calibration"
    rows_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    receipt = {
        "status": "complete_score_design",
        "stage": "score_design",
        "structure": "CCPs",
        "config_sha256": "config",
        "implementation": {"sha256": "implementation"},
        "artifacts": {"endpoint_cases_sha256": AUDIT.sha256_file(rows_path)},
    }
    (tmp_path / "archive_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Forbidden non-score-design rows"):
        AUDIT.load_receipted_design_rows([rows_path])


def test_smoke_receipt_requires_explicit_developmental_pilot_permission(tmp_path: Path) -> None:
    rows_path = tmp_path / "endpoint_cases.jsonl"
    rows_path.write_text(json.dumps(_row("tensor_coherence", 0.2)) + "\n", encoding="utf-8")
    receipt = {
        "status": "smoke_test",
        "stage": "score_design",
        "structure": "CCPs",
        "config_sha256": "config",
        "implementation": {"sha256": "implementation"},
        "artifacts": {"endpoint_cases_sha256": AUDIT.sha256_file(rows_path)},
    }
    (tmp_path / "archive_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Refusing non-design receipt"):
        AUDIT.load_receipted_design_rows([rows_path])
    rows, _ = AUDIT.load_receipted_design_rows(
        [rows_path],
        allow_developmental_pilot=True,
    )
    assert len(rows) == 1


def test_developmental_pilot_manifest_verifies_exact_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AUDIT, "PROJECT_ROOT", tmp_path)
    run_dir = tmp_path / "pilot"
    run_dir.mkdir()
    rows_path = run_dir / "endpoint_cases.jsonl"
    rows_path.write_text(json.dumps(_row("tensor_coherence", 0.2)) + "\n", encoding="utf-8")
    pair_index = run_dir / "pair_index.json"
    pair_index.write_text("{}\n", encoding="utf-8")
    receipt_path = run_dir / "archive_receipt.json"
    receipt = {
        "protocol_version": "nostos-paired-acquisition-support/2.0",
        "status": "smoke_test",
        "stage": "score_design",
        "structure": "CCPs",
        "config_sha256": "config",
        "implementation": {"sha256": "implementation"},
        "checkpoints": [{"cell_id": "Cell_001"}],
        "summary": {"reference_fields": 1, "pairs": 1, "rows": 1},
        "artifacts": {"endpoint_cases_sha256": AUDIT.sha256_file(rows_path)},
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    manifest = {
        "schema_version": "nostos-biosr-developmental-pilot/1.0",
        "status": "post_consolidation_deterministic_receipt",
        "shared": {
            "protocol_version": "nostos-paired-acquisition-support/2.0",
            "stage": "score_design",
            "receipt_status": "smoke_test",
            "config_sha256": "config",
            "implementation_sha256": "implementation",
        },
        "inputs": [
            {
                "structure": "CCPs",
                "endpoint_cases_path": "pilot/endpoint_cases.jsonl",
                "archive_receipt_path": "pilot/archive_receipt.json",
                "archive_receipt_bytes": receipt_path.stat().st_size,
                "archive_receipt_sha256": AUDIT.sha256_file(receipt_path),
                "endpoint_cases_sha256": AUDIT.sha256_file(rows_path),
                "pair_index_sha256": AUDIT.sha256_file(pair_index),
                "selected_cell_ids": ["Cell_001"],
                "reference_fields": 1,
                "paired_acquisitions": 1,
                "endpoint_cases": 1,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    verified = AUDIT.verify_developmental_pilot_manifest(manifest_path, [rows_path])
    assert verified["inputs"][0]["selected_cell_ids"] == ["Cell_001"]

    manifest["inputs"][0]["selected_cell_ids"] = ["Cell_999"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="cell identifiers disagree"):
        AUDIT.verify_developmental_pilot_manifest(manifest_path, [rows_path])


def test_clustered_bootstrap_preserves_paired_candidate_comparison() -> None:
    rows = []
    labels = [False, True, True, False]
    baseline_scores = [0.1, 0.2, 0.3, 0.4]
    candidate_scores = [0.1, 0.9, 0.8, 0.2]
    for index, (invalid, baseline, candidate) in enumerate(
        zip(labels, baseline_scores, candidate_scores), start=1
    ):
        rows.append(
            {
                "case_id": f"p{index}|spectral_entropy|global",
                "pair_id": f"p{index}",
                "reference_group_id": f"g{index}",
                "structure": "CCPs",
                "endpoint": "spectral_entropy",
                "requested_scale_um": None,
                "pair_registration_eligible": True,
                "reference_eligible": True,
                "invalid": invalid,
                "hard_abstention": False,
                "scores": {
                    "v2_full_max": baseline,
                    "candidate": candidate,
                },
            }
        )
    first = AUDIT.clustered_bootstrap_candidate_differences(
        rows,
        ["v2_full_max", "candidate"],
        draws=512,
        seed=17,
    )
    second = AUDIT.clustered_bootstrap_candidate_differences(
        rows,
        ["v2_full_max", "candidate"],
        draws=512,
        seed=17,
    )
    comparison = first["comparisons"]["candidate"]
    assert comparison["finite_draws"] == 512
    assert comparison["median_baseline_minus_candidate"] > 0
    assert first == second
