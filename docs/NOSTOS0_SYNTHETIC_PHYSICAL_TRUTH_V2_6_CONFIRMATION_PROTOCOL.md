# NOSTOS-0 synthetic physical-truth v2.6: frozen confirmation

**Frozen:** 2026-09-01 before any v2.6 confirmation execution  
**Opened v2.6 development receipt:** SHA-256
`9f425626e7f86a9e86ef1bbcbaab5b4ef814d31a9aa729b218d4b9dac26e7893`  
**Frozen response implementation:** SHA-256
`25b4237d0e896d770242fbfb088deaaa2d4089db8e75b56f2671ffe726f63b10`  
**Frozen confirmation evaluator:** SHA-256
`01f391f32b6568e741f85787f2e3f6adea17a46ec0d13e1127f4d011f87806e8`  
**Frozen metric helper:** SHA-256
`59902f09d201eba53db48bb3737331818684d341032269b24d8a3503f11d4f7c`

## Repairs under test

- The anisotropy magnitude remains the full-field physical-gradient
  covariance eigenratio.
- The reported axis comes from a Hann-tapered physical-gradient covariance to
  suppress crop-boundary rotation artifacts.
- Axis identification requires both full and tapered ratios to be at least
  1.65.
- Ratio support still requires quadrant/nested-crop log drift no greater than
  0.20.
- The field must contain at least 2.25 measured characteristic wavelengths.
  Characteristic scale is derived from a physically calibrated, detrended and
  Hann-windowed FFT. Anisotropic sampling is conservatively downsampled to the
  coarsest pixel spacing for this support check.
- Hessian morphology retains the five-samples-per-winning-scale rule.

The boundary and field-support choices were made on the opened failed v2.4 and
v2.5 receipts. Numerical response magnitudes were not trained against the new
confirmation cases.

## Disjoint confirmation

### Hessian morphology

- Blob, tube and sheet radii: 8, 10 and 12 µm.
- Spacing: 0.85³, 1.25³, 1.25 × 1.25 × 2.50 and 1.90³ µm.
- Shape: 64³; scale grid: 0.50, 0.75, 1.00, 1.25 and 1.50 times radius.

### Spatial anisotropy and field support

- Square fields: 192, 288 and 384 pixels at 1 µm spacing.
- Correlation lengths: 20, 28 and 36 µm.
- Programmed ratios: 1.0, 1.8, 2.3, 2.8 and 3.3.
- Six new seeds per condition; 270 fields total.
- Twenty-four 384-pixel anisotropic fields undergo 39° rotation and 0.82×
  physically calibrated resampling.
- No earlier development or confirmation identity is reused.

## Success gates

All gates must pass:

1. Hessian coverage ≥0.60, emitted balanced accuracy ≥0.95, every-class recall
   ≥0.90, emitted invalid risk ≤0.05 and every raw misclassification rejected.
2. Emitted Hessian scale median relative error ≤0.35 and p95 ≤0.50.
3. Overall and anisotropic spatial coverage ≥0.50, at least 15 supported
   isotropic controls, 384-pixel coverage ≥0.70, and 384-pixel coverage no lower
   than 192-pixel coverage.
4. Supported anisotropic fields: Spearman ρ ≥0.80, median relative error ≤0.10,
   p95 ≤0.25 and invalid risk (error >0.25) ≤0.05.
5. The contract must not increase invalid risk or p95 error relative to always
   emitting the same magnitude estimator.
6. Supported isotropic fields: median ratio ≤1.20, p95 ≤1.50 and axis
   abstention ≥0.90.
7. Programmed ratio ≥2.0 retains an identifiable axis in ≥0.80 of supported
   fields.
8. Every sub-threshold field is rejected and every emitted field meets the
   measured 2.25-span floor.
9. At least 0.60 of equivariance fields remain supported across reference,
   rotated and resampled views; ≥0.70 of supported cases retain both axes.
10. Supported equivariance fields: rotation median ratio drift ≤0.10, p95
    ≤0.20 and p95 axial-turn error ≤3°; resampling median drift ≤0.10 and p95
    ≤0.20.
11. Complementing invalidity labels leaves measurements and support unchanged.
12. A full independent recomputation is byte-identical.

## Failure policy

No identity, threshold, estimator, denominator, metric or gate may change after
the first execution. A failed gate remains a failed receipt and any repair
requires a new version with new cases.

## Claim boundary

A pass confirms calibrated analytic recovery, boundary-robust orientation and
finite-field abstention for these synthetic 2-D/3-D response families. It does
not establish segmentation, biological meaning, acquisition-family transfer,
diagnosis, mechanics, clinical utility or intraoperative readiness.
