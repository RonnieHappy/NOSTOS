import numpy as np
from nostos.validation.human_nanoct_scale_response import measure_at_scale
from nostos.validation.human_nanoct_transfer import axial_error_3d


def test_physical_scale_axis_permutation():
 z,y,x=np.indices((32,32,32));v=np.sin(x/3)+0.1*np.sin(z/6)
 a=measure_at_scale(v,(0.1,0.1,0.1),0.4);p=(2,1,0);b=measure_at_scale(np.transpose(v,p),(0.1,0.1,0.1),0.4)
 assert axial_error_3d(np.asarray(a["principal_structural_axis_zyx"])[list(p)],b["principal_structural_axis_zyx"])<1e-5
