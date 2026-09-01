# NOSTOS-0 synthetic physical-truth v2.4: frozen terminal confirmation

**Frozen:** 2026-09-01 before any v2.4 confirmation execution  
**Opened v2.4 development receipt:** SHA-256
`b1cfca531dae6e6ca43717f8d2b1277c08139355c82baacb8092405aba4e9fdf`  
**Frozen response implementation:** SHA-256
`e06fe4ce46dff015172bce9e2ca748bd1857feba457d1b066b254e378499ba08`  
**Frozen confirmation evaluator:** SHA-256
`59902f09d201eba53db48bb3737331818684d341032269b24d8a3503f11d4f7c`

## Repair under test

The numerical gradient-covariance estimator is unchanged. A measurement is
supported only when its anisotropy ratio is stable across four non-overlapping
quadrants and a centered 75% nested crop. The input-only score is

`max(median absolute quadrant log-ratio drift, nested-crop log-ratio drift)`.

The score must not exceed 0.20. The threshold and score definition were chosen
on the opened failed v2.3 fields and are frozen here before new-case execution.
Hessian morphology retains the independently developed requirement of at least
4.75 samples per winning physical scale.

## Disjoint confirmation

### Hessian morphology

- Blob, tube and sheet radii: 7, 9 and 11 µm.
- Spacing: 0.75³, 1.15³, 1.15 × 1.15 × 2.30 and 1.70³ µm.
- Shape: 64³; scale grid: 0.50, 0.75, 1.00, 1.25 and 1.50 times radius.

### Gradient-moment anisotropy

- Correlation lengths: 16, 24 and 32 µm.
- Programmed ratios: 1.0, 1.6, 2.1, 2.6 and 3.1.
- Ten new deterministic seeds per condition; 150 fields total.
- Twenty-four prespecified anisotropic fields undergo 37° rotation and 0.75×
  physically calibrated resampling.
- No v2, v2.1, v2.2 or v2.3 confirmation identity is reused.

## Success gates

All gates must pass:

1. Hessian coverage ≥0.60, emitted balanced accuracy ≥0.95, every-class recall
   ≥0.90, emitted invalid risk ≤0.05 and every raw misclassification rejected.
2. Emitted Hessian winning-scale median relative error ≤0.35 and p95 ≤0.50.
3. Overall spatial coverage ≥0.60, anisotropic coverage ≥0.60 and at least ten
   supported isotropic controls.
4. Among supported anisotropic fields: Spearman ρ ≥0.80, median relative error
   ≤0.10, p95 ≤0.25 and invalid risk (error >0.25) ≤0.05.
5. The contract must not increase either invalid risk or p95 error relative to
   always emitting the same estimator on the same confirmation fields.
6. Supported isotropic fields: median ratio ≤1.20, p95 ≤1.50 and axis
   abstention ≥0.90.
7. Programmed ratio ≥2.0 retains an identifiable axis in ≥0.80 of supported
   fields.
8. At least 0.50 of the prespecified equivariance fields remain supported under
   the reference, rotated and resampled views.
9. Supported equivariance fields: rotation median ratio drift ≤0.10, p95 ≤0.20
   and p95 axial-turn error ≤3°; resampling median drift ≤0.10 and p95 ≤0.20.
10. Complementing every invalidity label leaves all measurement and support
    bytes unchanged.
11. A full independent recomputation is byte-identical.

## Failure policy

No threshold, case identity, metric, denominator or gate may change after the
first confirmation execution. A failed gate remains a failed public receipt;
any repair requires a new version and new disjoint cases.

## Claim boundary

A pass confirms calibrated analytic recovery and fail-closed support for these
synthetic 2-D/3-D response families. It does not establish segmentation,
biological meaning, acquisition-family transfer, diagnosis, mechanics,
clinical utility or intraoperative readiness.
