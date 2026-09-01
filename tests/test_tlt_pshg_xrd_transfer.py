from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from nostos.validation.tlt_pshg_xrd_transfer import (
    CONFIRMATION_SAMPLES,
    DEVELOPMENT_SAMPLES,
    frozen_split,
    iter_fields,
    load_region_file,
    _select_tied_nearest,
)


def _record() -> dict[str, object]:
    yy, xx = np.mgrid[:512, :512]
    image = 1000.0 + 100.0 * np.sin(xx / 10.0)
    reference = np.full((512, 512), 90.0)
    organization = np.full((512, 512), 0.4)
    return {
        "SHG": image.astype(np.int32),
        "Phi2_thresholded": reference,
        "I2_thresholded": organization,
        "Threshold": np.asarray(8000),
        "name": "A1",
    }


def test_frozen_split_is_specimen_level_and_reproducible() -> None:
    split = frozen_split(["Sample4", "Sample2", "Sample1", "Sample3"])
    assert split["development"] == list(DEVELOPMENT_SAMPLES)
    assert split["confirmation"] == list(CONFIRMATION_SAMPLES)


def test_load_region_file_requires_aligned_deposited_arrays(tmp_path: Path) -> None:
    path = tmp_path / "Sample1NM.mat"
    savemat(path, {"Gdata4": np.asarray([_record()], dtype=object)})
    rows = load_region_file(path)
    assert len(rows) == 1
    assert rows[0]["shg"].shape == (512, 512)
    assert rows[0]["record_name"] == "A1"


def test_development_iterator_refuses_confirmation_samples(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="Confirmation arrays are sealed"):
        list(iter_fields(tmp_path, ["Sample2"]))


def test_tied_selection_never_splits_equal_scores() -> None:
    rows = [
        {"case_id": "a", "score": 0.1, "invalid": False},
        {"case_id": "b", "score": 0.2, "invalid": False},
        {"case_id": "c", "score": 0.2, "invalid": True},
        {"case_id": "d", "score": 0.3, "invalid": True},
    ]
    selected = _select_tied_nearest(rows, 2, score_key="score")
    assert {row["case_id"] for row in selected} == {"a", "b", "c"}
