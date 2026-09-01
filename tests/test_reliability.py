import numpy as np
import pandas as pd

from nostos.evaluation.reliability import icc_2_1, reliability_summary


def test_icc_is_high_for_consistent_raters():
    signal = np.linspace(0, 8, 20)
    matrix = np.column_stack((signal, signal + 0.1, signal - 0.1))
    assert icc_2_1(matrix) > 0.99


def test_reliability_bootstraps_complete_targets_and_reports_reader_noise():
    rows = []
    for target in range(15):
        for rater, offset in (("R1", 0.0), ("R2", 0.2), ("R3", -0.2)):
            rows.append({"specimen": f"S{target:02}", "rater": rater, "score": target / 2 + offset})
    result = reliability_summary(pd.DataFrame(rows), target="specimen", rater="rater", score="score", iterations=100)
    assert result["complete_target_count"] == 15
    assert result["icc_2_1"] > 0.99
    assert result["leave_one_rater_out_mae"] > 0
