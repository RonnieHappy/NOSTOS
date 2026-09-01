from __future__ import annotations

import numpy as np

from nostos.validation.shg_coordinate_bridge import (
    apply_bridge,
    fit_bridge,
    leave_one_mouse_out_models,
    normalized_error,
    stability_invalid,
)


def test_robust_affine_bridge_recovers_scale_and_offset() -> None:
    x = np.arange(1.0, 11.0)
    y = 3.0 + 2.5 * x
    model = fit_bridge("robust_affine", x, y)
    assert abs(model["slope"] - 2.5) < 1e-12
    assert abs(model["intercept"] - 3.0) < 1e-12
    assert np.allclose(apply_bridge(model, [2.0, 4.0]), [8.0, 13.0])


def test_log_affine_bridge_recovers_power_law() -> None:
    x = np.arange(1.0, 11.0)
    y = 4.0 * x**1.5
    model = fit_bridge("robust_log_affine", x, y)
    assert abs(model["exponent"] - 1.5) < 1e-12
    assert np.allclose(apply_bridge(model, [2.0, 4.0]), 4.0 * np.asarray([2.0, 4.0]) ** 1.5)


def test_relative_error_uses_declared_floor_and_tolerance() -> None:
    error = normalized_error([0.16], [0.10], mode="relative", tolerance=0.30, denominator_floor=0.20)
    assert np.allclose(error, [1.0])


def test_leave_one_mouse_out_selection_preserves_grouping() -> None:
    rows = []
    for mouse in range(6):
        for field in range(3):
            x = 1.0 + mouse + field / 10.0
            rows.append({"mouse": f"m{mouse}", "x": x, "y": 2.0 + 3.0 * x})
    result = leave_one_mouse_out_models(
        rows,
        observed_key="x",
        reference_key="y",
        mode="relative",
        tolerance=0.20,
        denominator_floor=1.0,
    )
    assert result["independent_mice"] == 6
    assert result["cases"] == 18
    assert result["selected_kind"] == "robust_affine"
    assert result["candidate_summaries"]["robust_affine"]["within_tolerance_fraction"] == 1.0


def test_collapsed_candidates_return_explicit_no_model() -> None:
    rows = []
    for mouse in range(6):
        for field in range(3):
            rows.append({"mouse": f"m{mouse}", "x": 1.0, "y": 1.0 + mouse + field})
    result = leave_one_mouse_out_models(
        rows,
        observed_key="x",
        reference_key="y",
        mode="relative",
        tolerance=0.20,
        denominator_floor=1.0,
    )
    assert result["selected_kind"] is None
    assert result["selected_model"] is None
    assert result["no_eligible_model_reason"] is not None


def test_stability_invalid_is_relative_to_same_mapped_clean_coordinate() -> None:
    model = {"kind": "robust_affine", "slope": 3.0, "intercept": 2.0}
    invalid, drift = stability_invalid(
        model,
        11.0,
        10.0,
        mode="relative",
        tolerance=0.25,
        denominator_floor=1.0,
    )
    assert invalid is False
    assert abs(drift - (3.0 / 32.0 / 0.25)) < 1e-12
