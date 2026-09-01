import numpy as np
from nostos.evaluation.adjacent_replication import concordance_ccc, icc_a1

def test_agreement_is_one_for_identical_values():
    values=np.array([.1,.2,.3,.4,.5])
    assert np.isclose(icc_a1(values,values),1)
    assert np.isclose(concordance_ccc(values,values),1)

def test_concordance_penalizes_constant_offset():
    values=np.array([1.,2.,3.,4.,5.])
    assert concordance_ccc(values,values+2)<1
