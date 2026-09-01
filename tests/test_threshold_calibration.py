from __future__ import annotations

import pytest

from nostos.validation.threshold_calibration import (
    evaluate_threshold_calibration,
    select_operating_threshold_stratified,
    stratified_cluster_bootstrap_risk_upper,
)


def _row(
    index: int,
    *,
    structure: str,
    endpoint: str,
    score: float,
    invalid: bool,
) -> dict:
    return {
        "case_id": f"case-{index}",
        "pair_id": f"pair-{index}",
        "reference_group_id": f"{structure}|field-{index}",
        "structure": structure,
        "development_partition": "threshold_calibration",
        "endpoint": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "hard_abstention": False,
        "invalid": invalid,
        "scores": {
            "full_contract": score,
            "conventional_acquisition_qc": score,
            "always_emit": 0.0,
        },
    }


def _dilution_fixture() -> list[dict]:
    rows = [
        _row(
            index,
            structure="CCPs",
            endpoint="spectral_entropy",
            score=0.1,
            invalid=False,
        )
        for index in range(100)
    ]
    rows.extend(
        _row(
            100 + index,
            structure="ER",
            endpoint="tensor_coherence",
            score=0.2 if index < 6 else 0.9,
            invalid=index >= 6,
        )
        for index in range(10)
    )
    return rows


def _config(*, minimum_combination_coverage: float = 0.5) -> dict:
    return {
        "target_selective_risk": 0.1,
        "maximum_cluster_bootstrap_risk_upper95": 0.15,
        "minimum_overall_confirmation_coverage": 0.8,
        "minimum_per_structure_endpoint_coverage": minimum_combination_coverage,
        "minimum_aurc_reduction_fraction": 0.2,
        "bootstrap_replicates": 200,
        "bootstrap_seed": 19,
    }


def test_selector_prevents_bad_endpoint_from_being_diluted_by_easy_cases() -> None:
    selected = select_operating_threshold_stratified(
        _dilution_fixture(),
        condition="full_contract",
        target_risk=0.1,
        maximum_risk_upper95=0.15,
        minimum_overall_coverage=0.8,
        minimum_combination_coverage=0.5,
        draws=200,
        seed=19,
    )
    assert selected["status"] == "operating_point_selected"
    assert selected["threshold"] == pytest.approx(0.2)
    er = next(
        item
        for item in selected["combinations"]
        if item["structure"] == "ER" and item["endpoint"] == "tensor_coherence"
    )
    assert er["coverage"] == pytest.approx(0.6)
    assert er["risk"] == 0.0


def test_selector_fails_when_endpoint_coverage_and_risk_cannot_both_pass() -> None:
    selected = select_operating_threshold_stratified(
        _dilution_fixture(),
        condition="full_contract",
        target_risk=0.1,
        maximum_risk_upper95=0.15,
        minimum_overall_coverage=0.8,
        minimum_combination_coverage=0.7,
        draws=200,
        seed=19,
    )
    assert selected["status"] == "no_operating_point"


def test_stratified_cluster_bootstrap_is_seed_reproducible() -> None:
    first = stratified_cluster_bootstrap_risk_upper(
        _dilution_fixture(),
        threshold=0.9,
        condition="full_contract",
        draws=200,
        seed=91,
    )
    second = stratified_cluster_bootstrap_risk_upper(
        _dilution_fixture(),
        threshold=0.9,
        condition="full_contract",
        draws=200,
        seed=91,
    )
    assert first == second
    assert first is not None and first > 0


def test_complete_calibration_gate_passes_only_with_selected_operating_point() -> None:
    result = evaluate_threshold_calibration(
        _dilution_fixture(),
        eligible_endpoints={"spectral_entropy", "tensor_coherence"},
        config=_config(),
    )
    assert result["status"] == "pass"
    assert result["operating_point"]["threshold"] == pytest.approx(0.2)
    assert result["gates"] == {
        "operating_point_selected": True,
        "minimum_aurc_reduction_fraction": True,
        "required_aurc_reduction_fraction": 0.2,
    }


def test_calibration_rejects_nonheldout_rows() -> None:
    rows = _dilution_fixture()
    rows[0]["development_partition"] = "score_design"
    with pytest.raises(ValueError, match="threshold_calibration"):
        evaluate_threshold_calibration(
            rows,
            eligible_endpoints={"spectral_entropy", "tensor_coherence"},
            config=_config(),
        )
