from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from nostos.validation.heaton_shg_transfer import (
    adapter_grid,
    apply_condition,
    measure_shg_field,
    select_perturbation_fields,
)


def _config() -> dict:
    path = Path(__file__).parents[1] / "configs" / "heaton_in_vivo_shg_v1.prelock.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _image() -> np.ndarray:
    yy, xx = np.mgrid[:128, :128]
    image = 0.05 + 0.001 * yy
    for centre, slope in ((30.0, 0.1), (60.0, -0.2), (90.0, 0.25)):
        distance = np.abs(yy - (centre + slope * xx)) / np.sqrt(1.0 + slope**2)
        image += np.exp(-(distance**2) / (2.0 * 2.0**2))
    return ndimage.gaussian_filter(image, 0.5)


def test_grid_contains_declared_54_candidates() -> None:
    assert len(adapter_grid(_config())) == 54


def test_one_field_per_mouse_selection_is_order_invariant() -> None:
    rows = [
        {"mouse": mouse, "source": f"{mouse}/field_{index}.tif"}
        for mouse in ("a", "b", "c")
        for index in range(4)
    ]
    assert select_perturbation_fields(rows) == select_perturbation_fields(list(reversed(rows)))
    assert len(select_perturbation_fields(rows)) == 3


def test_conditions_are_deterministic_and_crop_preserves_spacing_domain() -> None:
    image = _image()
    condition = {"id": "compound", "blur_sigma_px": 2, "resample_factor": 2, "noise_snr_db": 10, "crop_fraction": 0.75}
    first = apply_condition(image, condition, field_id="field", seed=8)
    second = apply_condition(image, condition, field_id="field", seed=8)
    assert np.array_equal(first, second)
    assert first.shape == (96, 96)
    assert np.all(first >= 0)


def test_measurement_emits_all_five_endpoints_and_ordered_policy_scores() -> None:
    config = _config()
    params = {
        "background_opening_radius_um": 11.72,
        "ridge_scales_um": (1.172, 2.344, 4.688),
        "foreground_quantile": 0.75,
        "minimum_component_length_um": 5.0,
    }
    result = measure_shg_field(
        _image(),
        spacing_um=(0.586, 0.586),
        params=params,
        config=config,
        internal_checks=True,
    )
    assert result["complete"]
    assert set(result["endpoints"]) == {
        "axial_resultant",
        "foreground_occupancy",
        "median_segment_straightness",
        "median_segment_length_um",
        "median_local_width_um",
    }
    assert result["scores"]["full_contract"] >= result["scores"]["endpoint_qc"]

