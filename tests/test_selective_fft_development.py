import numpy as np
from nostos.validation.phantoms import generate_phantom
from nostos.validation.selective_fft_development import self_perturbation_score

def test_self_perturbation_score_is_finite_and_auditable():
 p=generate_phantom("orientation",shape=(128,128),angle_degrees=31,scale_um=18)
 score,diagnostics=self_perturbation_score(p.image)
 assert np.isfinite(score) and score>=0
 assert set(diagnostics["components"])=={"angle_instability","scale_instability","low_anisotropy","high_entropy","low_snr","undersampling"}
