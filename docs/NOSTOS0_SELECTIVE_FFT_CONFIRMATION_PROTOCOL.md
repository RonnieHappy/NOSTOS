# NOSTOS-0 selective FFT measurement confirmation

**Frozen before confirmation generation:** 26 August 2026  
**Development receipt SHA-256:** `9c1e2e536f5bcefbf68a5f3ab8374dd15f3c83f106b29f7ebff994b77952c6af`  
**Frozen acceptance threshold:** self-perturbation score ≤ `1.0943159403934886`

## Question

Can NOSTOS detect, from the image and controlled internal probes alone, when an FFT
orientation/wavelength measurement is unsupported by acquisition quality?

## Truth and validity

Six hundred new 128 × 128 analytic orientation fields are generated with PCG64 seed
61202, random axial directions and wavelengths of 6–34 physical units. Confirmation
degradations use new random seeds and compound gamma response, illumination gradient,
anisotropic blur, shot noise, impulse noise, band dropout, resampling and cropping.
Resampling updates physical pixel spacing; padding and cropping do not. No confirmation
truth is used by the acceptance rule.

A measurement is valid only when axial angular error is at most 5° and relative
wavelength error is at most 0.15.

## Observable score

NOSTOS repeats the measurement after fixed ±4° rotations, 0.6-pixel blur and a fixed
center crop. Rotation estimates are mapped back to the source coordinate system. The
score is the maximum of prespecified normalized components: axial probe instability,
wavelength probe variability, low anisotropy, high angular entropy, low estimated SNR
and fewer than four pixels per measured wavelength. The formula and component scales
are frozen in `selective_fft_development.py`.

The existing rule based only on estimated SNR <3 or fewer than four pixels per scale is
retained as the legacy baseline.

## Inference and gates

Cases are the independent unit. Wilson intervals quantify selective risk. Stratified
bootstrap comparisons use 10,000 resamples with seed 61203. All gates must pass:

1. Coverage is at least 0.60.
2. The upper 95% Wilson limit for invalid measurements among accepted cases is at most 0.08.
3. Invalid-measurement detection ROC AUC is at least 0.90.
4. The lower 95% bootstrap limit for reduction in invalid risk relative to accepting
   every case is greater than 0.10.
5. Selective risk is lower than the legacy rule, or the legacy rule covers fewer than
   half as many cases.
6. Among accepted cases, median angular error is at most 2° and median relative
   wavelength error is at most 0.08.

All cases, abstentions, reasons, probe measurements and failed gates are retained.
Passing validates selective analytic FFT measurement under the declared perturbations;
it does not establish tissue-specific meaning or clinical use.
