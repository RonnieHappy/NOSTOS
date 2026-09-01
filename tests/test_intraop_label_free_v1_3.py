from pathlib import Path

import numpy as np

from nostos.intraop.label_free import load_intraop_profile
from nostos.intraop.label_free_v1_3 import analyze_unstained_field


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "configs/intraop_pshg_orientation_profile_v1.locked.json"


def test_profile_qc_ignores_unsupported_rectangular_background() -> None:
    profile = load_intraop_profile(PROFILE_PATH)
    y, x = np.mgrid[:128, :128]
    image = np.zeros((128, 128), dtype=float)
    image[24:104, 24:104] = 100.0 + 40.0 * np.sin((x[24:104, 24:104] + 2.0 * y[24:104, 24:104]) / 7.0)
    r2 = np.full(image.shape, np.nan)
    snr = np.full(image.shape, np.nan)
    r2[24:104, 24:104] = 1.0
    snr[24:104, 24:104] = 10.0
    fi = np.full(image.shape, np.nan)
    fi[24:104, 24:104] = 45.0
    result = analyze_unstained_field(
        image,
        pixel_size_um=1.0,
        modality=profile["modality"],
        profile=profile,
        verified_stack_frame_count=10,
        r2_map=r2,
        snr_map=snr,
        reference_fi_map=fi,
    )
    assert result.payload["acquisition_qc_full_field_diagnostic"]["status"] == "review"
    assert result.payload["acquisition_qc"]["status"] == "pass"
    assert result.payload["status"] == "valid"
    assert result.payload["measurement"]["evidence_status"] == "confirmed"
    assert result.payload["clinical_output"]["status"] == "withheld"
