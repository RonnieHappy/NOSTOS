from pathlib import Path

import pandas as pd

from nostos.reporting.cohort import generate_cohort_report


def test_cohort_report_tracks_missingness_and_writes_figures(tmp_path: Path):
    frame = pd.DataFrame({
        "participant_id": ["P1", "P2", "P3"],
        "age": [50, 60, None],
        "sex": ["Female", "Male", "Female"],
        "surgery_side": ["Left", "Right", "Left"],
        "mean_total_hhgs": [2, 4, 6],
        "mean_total_oarsi": [3, 5, 7],
        "mean_total_plm": [1, 2, 3],
    })
    result = generate_cohort_report(frame, tmp_path)
    assert result["participants"] == 3
    assert (tmp_path / "table_cohort.csv").is_file()
    assert (tmp_path / "figure_outcome_distributions.svg").is_file()
