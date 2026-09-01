import numpy as np
from nostos.validation.stability_weighting_development import fit_stability_weights

def test_development_import_exposes_label_free_fit():
    reference=np.arange(20,dtype=float).reshape(5,4); model=fit_stability_weights(reference,reference+.1)
    assert model.effective_coordinates==4
