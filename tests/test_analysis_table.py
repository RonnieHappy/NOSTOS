import pandas as pd

from nostos.data.analysis_table import build_participant_analysis_table


def test_sections_are_collapsed_to_one_wide_row_per_participant():
    features = pd.DataFrame([
        {"participant_id": "001", "stain": "HE", "site": "Medial", "feature_success": True, "zsd_a": 1.0},
        {"participant_id": "001", "stain": "HE", "site": "Medial", "feature_success": True, "zsd_a": 3.0},
        {"participant_id": "002", "stain": "PLM", "site": "Medial", "feature_success": False, "zsd_a": None},
    ])
    metadata = pd.DataFrame({"participant_id": ["001", "002"], "mean_total_plm": [2.0, 4.0]})
    splits = {"splits": {"train": ["001"], "validation": [], "test": ["002"]}}
    table, report = build_participant_analysis_table(features, metadata, splits)
    assert len(table) == 2
    assert table.loc[table["participant_id"] == "001", "zsd_a__stain_HE__site_Medial"].item() == 2.0
    assert report["valid_feature_rate"] == 2 / 3
