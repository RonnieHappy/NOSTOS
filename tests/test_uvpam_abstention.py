import numpy as np
from nostos.validation.uvpam_abstention import _sample,measure_pixel_domain


def test_sampling_is_deterministic():
    assert _sample([str(x) for x in range(100)],5)==_sample([str(x) for x in reversed(range(100))],5)


def test_pixel_measurement_never_claims_physical_units():
    image=np.tile(np.sin(np.linspace(0,8*np.pi,64)),(64,1))
    assert measure_pixel_domain(image)["units"]=="pixels"
