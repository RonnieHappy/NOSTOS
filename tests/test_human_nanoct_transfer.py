import numpy as np
from nostos.validation.human_nanoct_transfer import axial_error_3d, internal_diagnostics, measure_direction


def test_axis_permutation_contract():
    z,y,x=np.indices((32,32,32)); v=np.sin(x/2)+0.2*np.sin(y/4)
    m=measure_direction(v,(1,1,1)); d=internal_diagnostics(v,(1,1,1),m)
    assert d["maximum_axis_drift_degrees"] < 1


def test_axial_error_ignores_sign():
    assert axial_error_3d([1,0,0],[-1,0,0]) == 0
