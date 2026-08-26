from pathlib import Path

import numpy as np
import pandas as pd

from nostos.reporting.primary import generate_primary_report


def test_primary_report_writes_versionable_outputs(tmp_path: Path):
    truth = np.linspace(0, 8, 20)
    frame = pd.DataFrame({
        "participant_id": [f"P{index:03}" for index in range(20)],
        "observed": truth,
        "global_fft": truth + 1.0,
        "zsd": truth + 0.2,
    })
    result = generate_primary_report(frame, tmp_path)
    assert result["participant_count"] == 20
    assert result["comparison"]["difference"] < 0
    for name in result["outputs"]:
        assert (tmp_path / name).is_file()
