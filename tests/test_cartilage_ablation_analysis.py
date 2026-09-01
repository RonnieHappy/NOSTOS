import numpy as np
import pandas as pd

from nostos.evaluation.cartilage_ablation_analysis import _paired_delta_bootstrap


def test_paired_delta_bootstrap_uses_common_rows_and_is_reproducible():
    x = np.arange(30, dtype=float)
    frame = pd.DataFrame({"first": x, "second": -x, "outcome": x})
    first = _paired_delta_bootstrap(frame, "first", "second", "outcome", seed=12, draws=200)
    second = _paired_delta_bootstrap(frame, "first", "second", "outcome", seed=12, draws=200)
    assert first == second
    assert first[0] > 1.9 and first[1] > 1.9
