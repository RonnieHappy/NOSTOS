from pathlib import Path

import numpy as np
import pytest

from nostos.intraop.label_free import load_intraop_profile
from nostos.intraop.label_free_v1_2 import analyze_unstained_field, sanitize_reference_map


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "configs/intraop_pshg_orientation_profile_v1.locked.json"


def _texture() -> np.ndarray:
    y, x = np.mgrid[:128, :128]
    return 100.0 + 40.0 * np.sin((x + 2.0 * y) / 7.0) + 0.01 * x


def test_missing_fi_is_permitted_only_outside_locked_support() -> None:
    profile = load_intraop_profile(PROFILE_PATH)
    image = _texture()
    r2 = np.ones(image.shape, dtype=float)
    snr = np.full(image.shape, 10.0)
    fi = np.full(image.shape, 45.0)
    r2[:48] = np.nan
    snr[:48] = np.nan
    fi[:48] = np.nan
    clean, diagnostic = sanitize_reference_map(fi, r2, snr, profile)
    assert np.isfinite(clean).all()
    assert diagnostic["fi_nonfinite_inside_r2_snr_support"] == 0
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
    assert result.payload["status"] == "valid"
    assert result.payload["measurement"]["evidence_status"] == "confirmed"
    assert result.payload["reference_map_handling"]["fi_nonfinite_pixels"] == 48 * 128
    assert result.payload["clinical_output"]["status"] == "withheld"


def test_missing_fi_inside_locked_support_aborts() -> None:
    profile = load_intraop_profile(PROFILE_PATH)
    image = _texture()
    r2 = np.ones(image.shape, dtype=float)
    snr = np.full(image.shape, 10.0)
    fi = np.full(image.shape, 45.0)
    fi[64, 64] = np.nan
    with pytest.raises(ValueError, match="inside locked R2/SNR acquisition support"):
        analyze_unstained_field(
            image,
            pixel_size_um=1.0,
            modality=profile["modality"],
            profile=profile,
            verified_stack_frame_count=10,
            r2_map=r2,
            snr_map=snr,
            reference_fi_map=fi,
        )
