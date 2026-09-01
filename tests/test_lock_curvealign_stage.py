from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.lock_curvealign_stage import finalize


def _stage(
    root: Path,
    fraction: str = "0.04",
    threshold: str = "50",
    experiment: str | None = None,
) -> Path:
    root.mkdir()
    (root / "CAP_cluster.txt").write_text(f"./images/\nimage.tif\n{fraction}\n{threshold}\n", encoding="utf-8")
    (root / "CTFP_cluster.txt").write_text("defaults\n", encoding="utf-8")
    (root / "CAroiP_cluster.txt").write_text("defaults\n", encoding="utf-8")
    receipt = {"fields": 34}
    if experiment is not None:
        receipt["experiment"] = experiment
    (root / "stage_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return root


def test_finalize_records_parameter_provenance(tmp_path: Path) -> None:
    receipt = finalize(_stage(tmp_path / "stage"))
    assert receipt["status"] == "development_stage_parameters_locked"
    assert receipt["parameter_overrides"]["CAP_cluster.txt"]["line_4_8bit_intensity_threshold"]["locked"] == 50
    assert set(receipt["locked_parameter_sha256"]) == {"CAP_cluster.txt", "CTFP_cluster.txt", "CAroiP_cluster.txt"}


def test_finalize_refuses_unregistered_parameter_values(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        finalize(_stage(tmp_path / "stage", fraction="0.05", threshold="75"))


def test_finalize_applies_and_receipts_vendor_to_preregistered_override(tmp_path: Path) -> None:
    stage = _stage(tmp_path / "stage", fraction="0.06", threshold="100", experiment="Exp10")
    receipt = finalize(stage)
    lines = (stage / "CAP_cluster.txt").read_text(encoding="utf-8").splitlines()
    assert lines[2:4] == ["0.04", "50"]
    assert receipt["parameter_overrides"]["CAP_cluster.txt"]["action"] == "vendor_example_overridden_by_lock"
    assert receipt["status"] == "development_stage_parameters_locked"


def test_finalize_marks_exp15_as_confirmation_stage(tmp_path: Path) -> None:
    receipt = finalize(_stage(tmp_path / "stage", experiment="Exp15"))
    assert receipt["status"] == "confirmation_stage_parameters_locked"
