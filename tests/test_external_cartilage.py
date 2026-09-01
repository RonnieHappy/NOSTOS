import numpy as np
import pandas as pd

from nostos.validation.external_cartilage import _bh_adjust, _feature_families


def test_bh_adjust_is_monotone_in_rank():
    p = np.asarray([0.04, 0.001, 0.02, 0.5])
    q = _bh_adjust(p)
    assert np.all((0 <= q) & (q <= 1))
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= 0)


def test_feature_families_separate_response_blocks():
    frame = pd.DataFrame(columns=[
        "anisotropy_median", "angular_entropy_median", "tensor_coherence_median",
        "hessian_blob_scale_2px_median", "variogram_horizontal_sep_2px_median",
        "glcm_contrast_median", "cartilage_fraction", "bone_fraction",
    ])
    families = _feature_families(frame)
    assert "hessian_blob_scale_2px_median" in families["nostos_response_geometry"]
    assert "hessian_blob_scale_2px_median" not in families["nostos_without_hessian"]
    assert "glcm_contrast_median" in families["conventional_texture"]
