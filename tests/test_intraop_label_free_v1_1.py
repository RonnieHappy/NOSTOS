from pathlib import Path

import numpy as np

from nostos.intraop.label_free import load_intraop_profile
from nostos.intraop.label_free_v1_1 import analyze_unstained_field, sanitize_support_maps


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "configs/intraop_pshg_orientation_profile_v1.locked.json"


def _texture() -> np.ndarray:
    y, x = np.mgrid[:128, :128]
    return 100.0 + 40.0 * np.sin((x + 2.0 * y) / 7.0) + 0.01 * x


def test_nonfinite_support_pixels_are_excluded_without_imputation() -> None:
    r2 = np.ones((8, 8), dtype=float)
    snr = np.full((8, 8), 10.0)
    r2[:2, :3] = np.nan
    snr[:2, :3] = np.nan
    clean_r2, clean_snr, diagnostic = sanitize_support_maps(r2, snr)
    assert np.isfinite(clean_r2).all() and np.isfinite(clean_snr).all()
    assert np.all(clean_r2[:2, :3] < 0.9)
    assert np.all(clean_snr[:2, :3] < 3.0)
    assert diagnostic["joint_nonfinite_pixels"] == 6


def test_v1_1_profile_remains_confirmed_with_partial_instrument_support() -> None:
    profile = load_intraop_profile(PROFILE)
    image = _texture()
    r2 = np.ones(image.shape, dtype=float)
    snr = np.full(image.shape, 10.0)
    r2[:48] = np.nan
    snr[:48] = np.nan
    result = analyze_unstained_field(
        image,
        pixel_size_um=1.0,
        modality=profile["modality"],
        profile=profile,
        verified_stack_frame_count=10,
        r2_map=r2,
        snr_map=snr,
    )
    assert result.payload["status"] == "valid"
    assert result.payload["measurement"]["evidence_status"] == "confirmed"
    assert result.payload["support_map_handling"]["joint_nonfinite_pixels"] == 48 * 128
    assert result.payload["clinical_output"]["status"] == "withheld"

