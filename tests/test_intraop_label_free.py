from pathlib import Path

import numpy as np
import tifffile

from nostos.intraop.label_free import (
    analyze_pshg_directory,
    analyze_unstained_field,
    load_intraop_profile,
    local_orientation_field,
)
from nostos.validation.local_orientation import _tensor_fields


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "configs/intraop_pshg_orientation_profile_v1.locked.json"


def _axial_error(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def _oriented_texture(shape: tuple[int, int] = (128, 128), angle: float = 31.0) -> np.ndarray:
    y, x = np.mgrid[: shape[0], : shape[1]]
    radians = np.radians(angle)
    normal_coordinate = x * np.sin(radians) - y * np.cos(radians)
    return 110.0 + 55.0 * np.sin(2.0 * np.pi * normal_coordinate / 13.0) + 0.01 * x


def test_local_orientation_recovers_axial_texture_direction() -> None:
    image = _oriented_texture()
    orientation, coherence, energy = local_orientation_field(image, sigma_pixels=2.0)
    core = np.s_[16:-16, 16:-16]
    vector = np.mean(np.exp(2j * np.radians(orientation[core])))
    estimate = float((0.5 * np.degrees(np.angle(vector))) % 180.0)
    assert _axial_error(estimate, 31.0) < 2.0
    assert float(np.median(coherence[core])) > 0.75
    assert np.all(energy[core] > 0)


def test_production_estimator_is_exactly_equivalent_to_frozen_validation_path() -> None:
    image = _oriented_texture()
    production, production_coherence, _ = local_orientation_field(image, sigma_pixels=2.0)
    validation, validation_coherence, _ = _tensor_fields(image, scales=(2.0,))
    np.testing.assert_allclose(production, validation[0], rtol=0.0, atol=0.0)
    np.testing.assert_allclose(production_coherence, validation_coherence[0], rtol=0.0, atol=0.0)


def test_confirmed_evidence_requires_exact_stack_and_support_contract() -> None:
    profile = load_intraop_profile(PROFILE)
    image = _oriented_texture()
    support = np.ones(image.shape, dtype=float)
    confirmed = analyze_unstained_field(
        image,
        pixel_size_um=1.0,
        modality=profile["modality"],
        profile=profile,
        verified_stack_frame_count=10,
        r2_map=support,
        snr_map=10.0 * support,
    )
    assert confirmed.payload["status"] == "valid"
    assert confirmed.payload["measurement"]["evidence_status"] == "confirmed"
    assert confirmed.payload["clinical_output"]["status"] == "withheld"

    unverified = analyze_unstained_field(
        image,
        pixel_size_um=1.0,
        modality=profile["modality"],
        profile=profile,
    )
    assert unverified.payload["status"] == "review"
    assert unverified.payload["measurement"]["evidence_status"] == "unvalidated"
    assert "exact_frame_construction_not_verified" in unverified.payload["validity_reasons"]


def test_pshg_directory_writes_maps_and_evaluation_only_reference(tmp_path: Path) -> None:
    case = tmp_path / "case_001"
    case.mkdir()
    image = _oriented_texture((96, 96))
    for angle in range(0, 181, 20):
        tifffile.imwrite(case / f"case_001_FSHG_p{angle}.tif", image.astype(np.float32))
    tifffile.imwrite(case / "R2.tif", np.ones(image.shape, dtype=np.float32))
    tifffile.imwrite(case / "SNR.tif", np.full(image.shape, 10.0, dtype=np.float32))
    tifffile.imwrite(case / "FI.tif", np.full(image.shape, 121.0, dtype=np.float32))

    result = analyze_pshg_directory(
        case,
        tmp_path / "result",
        profile_path=PROFILE,
        include_reference_evaluation=True,
    )
    assert result["status"] == "valid"
    assert result["reference_evaluation"]["role"].startswith("evaluation_only")
    assert result["clinical_output"]["status"] == "withheld"
    assert (tmp_path / "result/orientation_degrees.npy").is_file()
    assert (tmp_path / "result/orientation.png").is_file()
    assert (tmp_path / "result/intraop_result.json").is_file()

