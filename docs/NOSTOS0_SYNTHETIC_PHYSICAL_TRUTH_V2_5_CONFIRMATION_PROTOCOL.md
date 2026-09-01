# NOSTOS-0 synthetic physical-truth v2.5: frozen terminal confirmation

**Frozen:** 2026-09-01 before any v2.5 confirmation execution  
**Opened v2.5 development receipt:** SHA-256
`b2809d5e404cac7a3b91267a33383cc53e5335468bb1799784d2e6b58b7ab7fe`  
**Frozen response implementation:** SHA-256
`16452de8987f25f123d4badf569250fb8ef753f24e5cec8ab65b0bf5f4b99a13`  
**Frozen confirmation evaluator:** SHA-256
`119638fc1797bcd67d927bd6cc74e55c01687194614e11840b80055c0082d43f`

## Repairs under test

- Hessian morphology requires at least 5.0 samples per winning physical scale.
- A gradient-moment orientation axis is emitted only when the estimated
  anisotropy ratio is at least 1.65.
- The v2.4 quadrant/nested-crop stability score and maximum value of 0.20 are
  unchanged.
- Numerical Hessian and gradient-covariance estimators are unchanged.

Both thresholds were chosen by written rules on the opened failed v2.4 receipt.

## Disjoint confirmation

### Hessian morphology

- Blob, tube and sheet radii: 7.5, 9.5 and 11.5 µm.
- Spacing: 0.80³, 1.20³, 1.20 × 1.20 × 2.40 and 1.80³ µm.
- Shape: 64³; scale grid: 0.50, 0.75, 1.00, 1.25 and 1.50 times radius.

### Gradient-moment anisotropy

- Correlation lengths: 18, 26 and 34 µm.
- Programmed ratios: 1.0, 1.7, 2.2, 2.7 and 3.2.
- Ten new deterministic seeds per condition; 150 fields total.
- Twenty-four prespecified anisotropic fields undergo 43° rotation and 0.70×
  physically calibrated resampling.
- No earlier development or confirmation identity is reused.

## Success gates

All gates must pass:

1. Hessian coverage ≥0.60, emitted balanced accuracy ≥0.95, every-class recall
   ≥0.90, emitted invalid risk ≤0.05 and every raw misclassification rejected.
2. Emitted Hessian winning-scale median relative error ≤0.35 and p95 ≤0.50.
3. Overall spatial coverage ≥0.60, anisotropic coverage ≥0.60 and at least ten
   supported isotropic controls.
4. Supported anisotropic fields: Spearman ρ ≥0.80, median relative error ≤0.10,
   p95 ≤0.25 and invalid risk (error >0.25) ≤0.05.
5. The contract must not increase invalid risk or p95 error relative to always
   emitting the same estimator on the same fields.
6. Supported isotropic fields: median ratio ≤1.20, p95 ≤1.50 and axis
   abstention ≥0.90.
7. Programmed ratio ≥2.0 retains an identifiable axis in ≥0.80 of supported
   fields.
8. At least 0.50 of equivariance cases remain supported across reference,
   rotated and resampled views, and ≥0.60 of those supported cases retain both
   reference and rotated axes.
9. Supported equivariance fields: rotation median ratio drift ≤0.10, p95 ≤0.20
   and p95 axial-turn error ≤3°; resampling median drift ≤0.10 and p95 ≤0.20.
10. Complementing every invalidity label leaves all measurement and support
    bytes unchanged.
11. A full independent recomputation is byte-identical.

## Failure policy

No threshold, identity, metric, denominator or gate may change after the first
execution. A failed gate remains a failed receipt; any later repair requires a
new version and another disjoint confirmation.

## Claim boundary

A pass confirms calibrated analytic recovery and fail-closed support for these
synthetic 2-D/3-D response families only. It does not establish segmentation,
biological meaning, acquisition-family transfer, diagnosis, mechanics,
clinical utility or intraoperative readiness.
