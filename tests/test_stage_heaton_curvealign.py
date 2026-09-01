from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.stage_heaton_curvealign import stage


def _tree(root: Path, experiment: str, fields: int) -> None:
    source = root / "Raw SHG Images" / experiment / "mouse"
    source.mkdir(parents=True)
    for index in range(fields):
        (source / f"field_{index}.tif").write_bytes(f"field-{index}".encode())


def _vendor(root: Path) -> None:
    root.mkdir()
    for name in ("CAP_cluster.txt", "CTFP_cluster.txt", "CAroiP_cluster.txt"):
        (root / name).write_text(name, encoding="utf-8")


def test_confirmation_stage_requires_authorizing_lock(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    vendor = tmp_path / "vendor"
    _tree(dataset, "Exp15", 45)
    _vendor(vendor)
    with pytest.raises(PermissionError):
        stage(dataset, vendor, tmp_path / "stage", experiment="Exp15", confirmation_lock=None)


def test_development_stage_is_content_identical(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    vendor = tmp_path / "vendor"
    _tree(dataset, "Exp10", 34)
    _vendor(vendor)
    result = stage(dataset, vendor, tmp_path / "stage", experiment="Exp10", confirmation_lock=None)
    assert result["fields"] == 34
    assert result["mice"] == 1
    assert len(result["rows"]) == 34
    receipt = json.loads((tmp_path / "stage" / "stage_receipt.json").read_text(encoding="utf-8"))
    assert receipt["rows"][0]["sha256"] == result["rows"][0]["sha256"]

