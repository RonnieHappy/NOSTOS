import numpy as np
import pandas as pd

from nostos.modeling.ablations import derive_feature_contract, run_prespecified_ablations


def test_contract_and_ablation_matrix_are_prespecified_by_prefix():
    count = 30
    signal = np.linspace(-2, 2, count)
    frame = pd.DataFrame({
        "participant_id": [f"P{i:03}" for i in range(count)],
        "split": ["train"] * 18 + ["validation"] * 6 + ["test"] * 6,
        "outcome": signal,
        "zsd_fft_anisotropy__stain_HE__site_Medial": signal,
        "zsd_fft_anisotropy__stain_SafO__site_Lateral": signal + 0.1,
        "zsd_fft_anisotropy__stain_PLM__site_Medial": signal + 0.2,
        "global_fft_anisotropy": signal + 0.2,
        "texture_glcm_contrast": signal + 0.1,
        "intensity_cartilage_mean": signal + 0.3,
        "morphology_cartilage_area_mm2": signal + 0.4,
    })
    contract = derive_feature_contract(frame.columns.tolist())
    assert len(contract["zsd"]) == 3
    assert "texture_glcm_contrast" in contract["zsd_plus_conventional"]
    results = run_prespecified_ablations(frame, outcome="outcome", feature_sets=contract)
    assert set(results["stratum_type"]) == {"overall", "stain", "site"}
    assert set(results.loc[results["stratum_type"] == "overall", "model"]) >= {"zsd", "global_fft", "texture"}
