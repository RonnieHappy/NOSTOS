from pathlib import Path

import numpy as np
import pandas as pd

from nostos.reporting.ablations import generate_ablation_report


def test_ablation_report_writes_table_and_vector_figure(tmp_path: Path):
    truth = np.linspace(0, 5, 12)
    rows = []
    for model, error in (("global_fft", 1.0), ("zsd", 0.2)):
        for index, observed in enumerate(truth):
            rows.append({"stratum_type": "overall", "stratum_value": "all", "model": model, "participant_id": f"P{index:03}", "observed": observed, "predicted": observed + error})
    result = generate_ablation_report(pd.DataFrame(rows), tmp_path, iterations=100)
    assert result["comparisons"] == 2
    assert (tmp_path / "figure_ablations.svg").is_file()
    assert (tmp_path / "table_ablations.csv").is_file()
