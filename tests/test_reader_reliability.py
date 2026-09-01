import numpy as np
from nostos.evaluation.reader_reliability import icc_ak

def test_average_measure_icc_is_one_for_identical_raters():
    x=np.array([1.,2.,3.,4.]); matrix=np.column_stack([x,x,x])
    assert np.isclose(icc_ak(matrix),1)
