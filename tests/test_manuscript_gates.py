import json
from pathlib import Path

from nostos.evaluation.gates import evaluate_manuscript_gates


def _thresholds():
    return json.loads(Path("configs/manuscript_gates.json").read_text())


def _evidence():
    return {
        "cohort": {"audited_participants": 90},
        "leakage": {"violations": 0},
        "segmentation": {"cartilage_dice": 0.93, "cartilage_iou": 0.87, "median_boundary_hd95_um": 60, "success_rate": 0.95, "catastrophic_masks": 0},
        "features": {"valid_rate": 0.91},
        "robustness": {"rotation_scalar_max_relative_drift": 0.03, "rotation_orientation_error_degrees": 2},
        "primary": {"zsd_minus_global_fft_ci_95_upper": -0.02},
        "stain_analysis": {"directionally_stable_stain_count": 2},
        "comparators": {"non_fft_count": 2},
        "reproducibility": {"single_command_verified": True},
    }


def test_all_manuscript_gates_can_pass():
    result = evaluate_manuscript_gates(_evidence(), _thresholds())
    assert result["manuscript_quality_pass"]
    assert result["passed"] == result["total"]


def test_primary_failure_blocks_manuscript_quality():
    evidence = _evidence()
    evidence["primary"]["zsd_minus_global_fft_ci_95_upper"] = 0.2
    result = evaluate_manuscript_gates(evidence, _thresholds())
    assert not result["manuscript_quality_pass"]
