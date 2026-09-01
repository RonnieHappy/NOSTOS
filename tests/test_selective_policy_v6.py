from __future__ import annotations

from nostos.validation.selective_policy_v6 import (
    policy_accepts,
    select_family_policy,
)


def _row(
    case: int,
    *,
    structure: str = "ER",
    endpoint: str = "coherence",
    score: float = 0.1,
    invalid: bool = False,
    hard_reasons: list[str] | None = None,
) -> dict:
    reasons = hard_reasons or []
    return {
        "case_id": f"{structure}|field_{case // 4}|{case}",
        "reference_group_id": f"{structure}|field_{case // 4}",
        "structure": structure,
        "endpoint": endpoint,
        "pair_registration_eligible": True,
        "reference_eligible": True,
        "invalid": invalid,
        "hard_abstention": bool(reasons),
        "hard_abstention_reasons": reasons,
        "scores": {
            "full_contract": score,
            "always_emit": 0.0,
            "conventional_acquisition_qc": score,
        },
    }


def test_qc_only_does_not_inherit_orientation_identifiability_abstention() -> None:
    row = _row(
        0,
        hard_reasons=["input_orientation_estimators_disagree"],
    )
    assert policy_accepts(row, condition="full_contract", threshold=1.0) is False
    assert (
        policy_accepts(
            row,
            condition="conventional_acquisition_qc",
            threshold=1.0,
        )
        is True
    )
    assert policy_accepts(row, condition="always_emit", threshold=0.0) is True


def test_qc_only_keeps_its_own_acquisition_abstention() -> None:
    row = _row(0, hard_reasons=["acquisition_qc_abstain"])
    assert (
        policy_accepts(
            row,
            condition="conventional_acquisition_qc",
            threshold=1.0,
        )
        is False
    )
    assert policy_accepts(row, condition="always_emit", threshold=0.0) is True


def test_family_policy_selects_structure_independent_thresholds() -> None:
    rows = []
    for structure in ("CCPs", "ER"):
        for case in range(40):
            score = case / 40
            rows.append(
                _row(
                    case,
                    structure=structure,
                    endpoint="coherence",
                    score=score,
                    invalid=case >= 36,
                )
            )
    result = select_family_policy(
        rows,
        family_map={"tensor_coherence": ["coherence"]},
        condition="full_contract",
        target_risk=0.1,
        maximum_risk_upper95=0.2,
        minimum_overall_coverage=0.7,
        minimum_family_coverage=0.7,
        minimum_structure_coverage=0.7,
        draws=200,
        seed=4,
    )
    assert result["status"] == "pass"
    family = result["families"]["tensor_coherence"]
    assert family["risk"] <= 0.1
    assert {item["structure"] for item in family["structures"]} == {"CCPs", "ER"}
