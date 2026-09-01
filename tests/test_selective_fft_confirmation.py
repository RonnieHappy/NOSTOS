from nostos.validation.selective_fft_confirmation import _wilson
def test_wilson_interval_contains_observed_risk():
 low,high=_wilson(5,100)
 assert low<.05<high and high<.12
