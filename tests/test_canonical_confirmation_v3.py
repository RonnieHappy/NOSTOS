import numpy as np
from nostos.validation.canonical_confirmation_v3 import _gamma, _standardize

def test_v3_intensity_transforms_remain_finite():
    image=np.linspace(-2,3,104*104,dtype=np.float32).reshape(104,104)
    changed=_standardize(_gamma(image,.7))
    assert changed.shape==(104,104) and np.isfinite(changed).all()
    assert abs(float(changed.mean())) < 1e-5
