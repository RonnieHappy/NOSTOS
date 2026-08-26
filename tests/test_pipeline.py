import json
from pathlib import Path

import pandas as pd

from nostos.pipeline import pipeline_commands, write_feature_contract


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
