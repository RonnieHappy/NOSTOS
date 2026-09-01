import numpy as np
import pandas as pd

from nostos.evaluation.agreement import benjamini_hochberg, cross_stain_spearman, medial_lateral_differences


def _frame():
    rows = []
    for participant in range(1, 11):
        for site, offset in (("Medial", 1.0), ("Lateral", 0.0)):
            for stain, scale in (("HE", 1.0), ("SafO", 2.0), ("PLM", 3.0)):
                rows.append({"participant_id": f"P{participant:03}", "site": site, "stain": stain, "value": scale * participant + offset})
    return pd.DataFrame(rows)


def test_cross_stain_agreement_resamples_participants():
    results = cross_stain_spearman(_frame(), "value", iterations=100)
    assert len(results) == 3
    assert all(result["rho"] > 0.99 for result in results)


def test_medial_lateral_is_paired():
    differences = medial_lateral_differences(_frame(), "value")
    assert len(differences) == 30
    assert np.allclose(differences["medial_minus_lateral"], 1.0)


def test_bh_adjustment_is_monotone_in_rank():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.8])
    assert np.allclose(adjusted, [0.04, 0.0533333333, 0.0533333333, 0.8])
