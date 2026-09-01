# NOSTOS-0 support-score code-audit corrections

This record lists implementation corrections made during the authorized score-design phase and before threshold calibration or confirmation access.

## Canonical sampling after header validation

BioSR MRC headers encode the documented 0.0626 µm raw spacing as float32 (observed 0.06260000169277191). Direct division made an intended four-sample scale evaluate infinitesimally below four. The implementation now:

1. validates the observed header spacing against the exact workbook value within the frozen tolerance;
2. retains the observed header values in the pair manifest; and
3. uses the exact documented value for physical calculations after validation.

This prevents file-format rounding from changing a boundary decision. A corrected real-field smoke test returned zero unintended hard abstentions.

## Spectral entropy agreement

The v1 cross-estimator component compared mean tensor coherence with Fourier anisotropy for both the anisotropy endpoint and the entropy endpoint. That made the two support components identical and failed to use the entropy estimate when judging entropy support.

Version 2 compares tensor coherence with Fourier anisotropy for `spectral_anisotropy`, and with \(1-H_{\mathrm{angular}}\) for `spectral_entropy`, where normalized entropy lies in [0, 1]. Both are order coordinates in which larger values represent stronger directionality. The normalization denominator remains the predeclared 0.25.

This is an algebraic semantics correction, not an outcome-fitted coefficient. A unit test uses equal anisotropy and tensor coherence but high entropy to prove that the two support paths are no longer accidentally identical.

## Access state

Only authorized CCP/ER score-design evidence had been viewed. Threshold-calibration fields remained sealed and confirmation archives remained neither downloaded nor listed.
