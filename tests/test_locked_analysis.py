import numpy as np
import pandas as pd

from nostos.modeling.locked_analysis import run_locked_analysis


def test_locked_analysis_only_returns_test_rows():
    count = 30
    signal = np.linspace(-2, 2, count)
    frame = pd.DataFrame({
        "participant_id": [f"P{index:03}" for index in range(count)],
        "split": ["train"] * 18 + ["validation"] * 6 + ["test"] * 6,
        "outcome": signal * 2,
        "global_fft_mean": signal + 0.3,
        "zsd_depth_slope": signal,
    })
    predictions, receipt = run_locked_analysis(
        frame,
        outcome="outcome",
        feature_sets={"global_fft": ["global_fft_mean"], "zsd": ["zsd_depth_slope"]},
    )
    assert len(predictions) == 6
    assert set(predictions.columns) == {"participant_id", "observed", "global_fft", "zsd"}
    assert receipt["test_participants"] == 6
