import json
from pathlib import Path

import pandas as pd

from nostos.pipeline import pipeline_commands, resolve_config, write_feature_contract


def test_pipeline_does_not_touch_locked_test_without_explicit_flag():
    config = json.loads(Path("configs/pipeline.json").read_text())
    ordinary = pipeline_commands(config, python="python", unlock_test=False)
    locked = pipeline_commands(config, python="python", unlock_test=True)
    assert not any("nostos.modeling.locked_analysis" in command for command in ordinary)
    assert any("nostos.modeling.locked_analysis" in command for command in locked)


def test_feature_contract_is_frozen_from_wide_table(tmp_path: Path):
    table = tmp_path / "table.csv"
    output = tmp_path / "contract.json"
    pd.DataFrame({
        "zsd_a__stain_HE__site_Medial": [1],
        "global_fft_a__stain_HE__site_Medial": [1],
        "texture_a__stain_HE__site_Medial": [1],
        "intensity_a__stain_HE__site_Medial": [1],
    }).to_csv(table, index=False)
    contract = write_feature_contract(table, output)
    assert contract["zsd"]
    assert output.is_file()


def test_pipeline_config_resolves_environment_and_project_paths(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    config_path = project / "configs" / "pipeline.json"
    config_path.parent.mkdir(parents=True)
    monkeypatch.setenv("NOSTOS_DATA_ROOT", str(tmp_path / "public-data"))
    monkeypatch.setenv("NOSTOS_ANNOTATION_ROOT", str(tmp_path / "annotations"))
    resolved = resolve_config({
        "raw_root": "${NOSTOS_DATA_ROOT}/cohort/raw",
        "annotation_manifest": "${NOSTOS_ANNOTATION_ROOT}/annotation_manifest.csv",
        "output": "outputs/result.json",
    }, config_path=config_path)
    assert Path(resolved["raw_root"]) == tmp_path / "public-data" / "cohort" / "raw"
    assert Path(resolved["annotation_manifest"]) == tmp_path / "annotations" / "annotation_manifest.csv"
    assert Path(resolved["output"]) == project / "outputs" / "result.json"
