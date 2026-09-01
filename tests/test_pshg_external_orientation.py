import numpy as np

from nostos.validation.pshg_external_orientation import _summary


def test_summary_reports_axial_alignment() -> None:
    result = _summary([np.asarray([0.0, 5.0]), np.asarray([10.0, 15.0])])
    assert result["eligible_rois"] == 2
    assert result["eligible_pixels"] == 4
    assert result["median_error"] == 7.5
    assert 0.8 < result["axial_alignment"] <= 1.0
