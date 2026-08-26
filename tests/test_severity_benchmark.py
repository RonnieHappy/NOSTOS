import numpy as np
from nostos.modeling.severity_benchmark import metrics

def test_severity_metrics_are_perfect_for_separable_predictions():
 result=metrics(np.array([0,0,1,1]),np.array([.1,.2,.8,.9]))
 assert all(np.isclose(value,1) for value in result.values())
