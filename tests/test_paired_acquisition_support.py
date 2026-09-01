from __future__ import annotations

import json
import struct
import zipfile

import numpy as np
import pytest
from scipy import ndimage

from nostos.validation.paired_acquisition_support import (
    aurc,
    audit_pair_registration,
    _streaming_hessian_2d,
    _cross_scale_risk,
    development_partition,
    evaluate_registered_pair,
    index_biosr_archive,
    read_mrc_bytes,
    risk_coverage_curve,
    select_operating_threshold,
    shared_spectral_band_cycles_per_mm,
)
from nostos.validation.phantoms import generate_phantom
from nostos.features.response_modules import hessian_morphology_response


def _config() -> dict:
    return {
        "physical_scales_um": [4.0, 6.0, 8.0, 12.0, 16.0],
        "spectral_analysis": {
            "minimum_fraction_of_effective_input_nyquist": 0.02,
            "maximum_fraction_of_effective_input_nyquist": 0.90,
        },
        "minimum_samples_per_scale": 4.0,
        "reference_eligibility": {
            "minimum_orientation_resultant": 0.15,
            "minimum_spectral_orientation_anisotropy": 0.15,
            "maximum_cross_estimator_orientation_disagreement_degrees": 20.0,
            "maximum_reference_orientation_probe_drift_degrees": 5.0,
            "maximum_reference_scalar_probe_drift": 0.1,
            "minimum_normalized_curve_energy": 1e-6,
        },
        "invalidity_tolerances": {
            "tensor_orientation_degrees": 10.0,
            "tensor_coherence_absolute": 0.15,
            "spectral_anisotropy_absolute": 0.15,
            "spectral_entropy_absolute": 0.1,
            "spectral_scale_relative": 0.25,
            "normalized_response_curve_distance": 0.25,
            "winning_scale_log2_absolute": 0.5,
            "normalized_variogram_curve_distance": 0.25,
            "variogram_range_relative": 0.5,
        },
    }


def test_mrc_reader_handles_extended_header_and_uint16() -> None:
    image = np.arange(20, dtype=np.uint16).reshape(4, 5)
    header = bytearray(1024)
    struct.pack_into("<4i", header, 0, 5, 4, 1, 6)
    struct.pack_into("<i", header, 92, 16)
    payload = bytes(header) + bytes(16) + image.astype("<u2").tobytes()
    observed = read_mrc_bytes(payload)
    np.testing.assert_array_equal(observed, image)


def _mrc_payload(array: np.ndarray, *, spacing_um: float) -> bytes:
    values = np.asarray(array, dtype="<u2")
    if values.ndim == 2:
        values = values[None, ...]
    header = bytearray(1024)
    struct.pack_into("<4i", header, 0, values.shape[2], values.shape[1], values.shape[0], 6)
    struct.pack_into("<3i", header, 28, 1, 1, 1)
    struct.pack_into("<3f", header, 40, spacing_um, spacing_um, 0.16)
    return bytes(header) + values.tobytes()


def test_biosr_index_requires_nine_levels_and_dimension_ratio(tmp_path) -> None:
    archive = tmp_path / "tiny.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr(
            "CCPs/Cell_001/SIM_gt.mrc",
            _mrc_payload(np.zeros((64, 64), np.uint16), spacing_um=0.0313),
        )
        for level in range(1, 10):
            opened.writestr(
                f"CCPs/Cell_001/RawSIMData_level_{level:02d}.mrc",
                _mrc_payload(np.zeros((9, 32, 32), np.uint16), spacing_um=0.0626),
            )
    records = index_biosr_archive(
        archive,
        structure="CCPs",
        expected_raw_spacing_um=0.0626,
        upscaling_factor=2,
        expected_level_count=9,
    )
    assert len(records) == 9
    assert records[0].input_frames == 9
    assert records[0].input_grid_spacing_um == 0.0626
    assert records[0].effective_input_spacing_um == 0.0626
    assert records[0].reference_spacing_um == 0.0313
    assert records[0].physical_field_of_view_yx_um == pytest.approx((2.0032, 2.0032))


def test_biosr_index_supports_er_level_matched_layout(tmp_path) -> None:
    archive = tmp_path / "er.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        for level in range(1, 7):
            opened.writestr(
                f"ER/Cell_001/GTSIM/GTSIM_level_{level:02d}.mrc",
                _mrc_payload(np.zeros((64, 64), np.uint16), spacing_um=0.0313),
            )
            opened.writestr(
                f"ER/Cell_001/RawSIMData/RawSIMData_level_{level:02d}.mrc",
                _mrc_payload(np.zeros((9, 32, 32), np.uint16), spacing_um=0.0626),
            )
    records = index_biosr_archive(
        archive,
        structure="ER",
        expected_raw_spacing_um=0.0626,
        upscaling_factor=2,
        expected_level_count=6,
    )
    assert len(records) == 6
    assert records[3].reference_member.endswith("GTSIM_level_04.mrc")
    assert records[3].archive_layout == "level_matched_nested"


def test_biosr_index_rejects_factor_of_two_reference_calibration_error(tmp_path) -> None:
    archive = tmp_path / "wrong-spacing.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr(
            "CCPs/Cell_001/SIM_gt.mrc",
            _mrc_payload(np.zeros((64, 64), np.uint16), spacing_um=0.0626),
        )
        for level in range(1, 10):
            opened.writestr(
                f"CCPs/Cell_001/RawSIMData_level_{level:02d}.mrc",
                _mrc_payload(np.zeros((9, 32, 32), np.uint16), spacing_um=0.0626),
            )
    with pytest.raises(ValueError, match="Reference MRC spacing disagrees"):
        index_biosr_archive(
            archive,
            structure="CCPs",
            expected_raw_spacing_um=0.0626,
            upscaling_factor=2,
            expected_level_count=9,
        )


def test_partition_is_stable_and_binary() -> None:
    first = development_partition("ER", "field-17")
    assert first in {"score_design", "threshold_calibration"}
    assert development_partition("ER", "field-17") == first


def test_streaming_hessian_matches_frozen_generic_summary() -> None:
    image = generate_phantom("tube", shape=(64, 64), scale_um=10).image
    scales = (1.5, 3.0, 4.5, 6.0)
    expected = hessian_morphology_response(image, spacing_um=(1.0, 1.0), scales_um=scales)
    observed = _streaming_hessian_2d(image, spacing_um=1.0, scales_um=scales)
    np.testing.assert_allclose(observed["blob_energy"] * np.asarray(observed["blob_curve"]), expected.blob)
    np.testing.assert_allclose(observed["tube_energy"] * np.asarray(observed["tube_curve"]), expected.tube)
    assert observed["blob_scale"] == scales[int(np.argmax(expected.blob))]
    assert observed["tube_scale"] == scales[int(np.argmax(expected.tube))]


def test_spectral_entropy_agreement_uses_inverse_entropy_as_order() -> None:
    measurement = {
        "tensor_coherence": [0.8, 0.8],
        "spectral_anisotropy": 0.8,
        "spectral_entropy": 0.8,
    }
    assert _cross_scale_risk("spectral_anisotropy", None, measurement) == pytest.approx(0.0)
    assert _cross_scale_risk("spectral_entropy", None, measurement) == pytest.approx(2.4)


def test_shared_spectral_band_uses_effective_input_physical_nyquist() -> None:
    observed = shared_spectral_band_cycles_per_mm(_config(), 0.0626)
    assert observed == pytest.approx((159.7444089456869, 7188.49840255591))


def test_registration_audit_accepts_small_shift_and_rejects_large_shift() -> None:
    rng = np.random.default_rng(91)
    phantom = ndimage.gaussian_filter(rng.normal(size=(128, 128)), 2.0)
    phantom[37:46, 81:96] += 4.0
    small = ndimage.shift(phantom, (1, -1), order=1, mode="reflect")
    large = ndimage.shift(phantom, (8, 0), order=1, mode="reflect")
    accepted = audit_pair_registration(small, phantom, reference_spacing_um=1.0, effective_input_spacing_um=1.0)
    rejected = audit_pair_registration(large, phantom, reference_spacing_um=1.0, effective_input_spacing_um=1.0)
    assert accepted.eligible
    assert not rejected.eligible


def test_pair_evaluation_keeps_support_separate_from_reference_error() -> None:
    reference = generate_phantom("orientation", shape=(128, 128), angle_degrees=31, scale_um=16).image
    input_image = ndimage.gaussian_filter(reference, 0.6)
    rows = evaluate_registered_pair(
        input_image,
        reference,
        pair_id="pair-1",
        reference_group_id="field-1",
        structure="ER",
        input_grid_spacing_um=1.0,
        effective_input_spacing_um=1.0,
        reference_spacing_um=1.0,
        config=_config(),
    )
    assert len(rows) == 21
    assert all("error" in row and "scores" in row for row in rows)
    assert all("reference_measurement" not in row["support_components"] for row in rows)
    assert {row["development_partition"] for row in rows} <= {"score_design", "threshold_calibration"}
    orientation_rows = [row for row in rows if row["endpoint"] == "tensor_orientation"]
    assert all(row["reference_eligible"] for row in orientation_rows)
    assert all(not row["hard_abstention"] for row in orientation_rows)
    for row in rows:
        components = row["support_components"]
        expected = max(
            components["acquisition_qc"],
            components["physical_sampling"],
            components["perturbation_stability"],
            components["measurement_identifiability"],
        )
        assert row["scores"]["full_contract"] == pytest.approx(expected)
        assert row["scores"]["exploratory_full_contract_with_cross_scale_diagnostic"] == pytest.approx(
            max(expected, components["cross_scale_agreement"])
        )


def test_global_orientation_abstains_when_directions_cancel() -> None:
    y, x = np.mgrid[:128, :128]
    image = np.empty((128, 128), dtype=float)
    image[:64] = np.sin(2 * np.pi * x[:64] / 16.0)
    image[64:] = np.sin(2 * np.pi * y[64:] / 16.0)
    rows = evaluate_registered_pair(
        image,
        image,
        pair_id="pair-mixed",
        reference_group_id="field-mixed",
        structure="ER",
        input_grid_spacing_um=1.0,
        effective_input_spacing_um=1.0,
        reference_spacing_um=1.0,
        config=_config(),
    )
    orientations = [row for row in rows if row["endpoint"] == "tensor_orientation"]
    assert orientations
    assert all(not row["reference_eligible"] for row in orientations)
    assert all(row["hard_abstention"] for row in orientations)
    assert all(
        "input_orientation_resultant_below_minimum" in row["hard_abstention_reasons"]
        for row in orientations
    )


def _row(case: int, score: float, invalid: bool, group: str) -> dict:
    return {
        "case_id": f"case-{case}",
        "reference_group_id": group,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": False,
        "invalid": invalid,
        "scores": {"full_contract": score, "reversed": 1.0 - score},
    }


def test_risk_coverage_and_aurc_reward_valid_first_ordering() -> None:
    rows = [_row(i, i / 10, i >= 7, f"g{i // 2}") for i in range(10)]
    curve = risk_coverage_curve(rows, "full_contract")
    assert curve[-1]["coverage"] == 1.0
    assert curve[-1]["risk"] == 0.3
    assert aurc(rows, "full_contract") < aurc(rows, "reversed")


def test_threshold_selection_is_cluster_bootstrapped_and_deterministic() -> None:
    rows = [_row(i, i / 20, i >= 18, f"g{i // 2}") for i in range(20)]
    first = select_operating_threshold(rows, draws=200, seed=41)
    second = select_operating_threshold(rows, draws=200, seed=41)
    assert first == second
    assert first.status == "operating_point_selected"
    assert first.threshold is not None
    assert json.loads(json.dumps(first.__dict__))["coverage"] > 0
