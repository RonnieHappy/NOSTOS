# NOSTOS-0 synthetic physical-truth v2.2: frozen terminal repair confirmation

**Frozen:** 2026-08-31 before any v2.2 confirmation execution  
**Opened v2.2 development receipt:** SHA-256
`34b625b2300582df254efaeb6771bfc012cd1174afb86e7ede5724b3b0986a85`  
**Frozen response implementation:** SHA-256
`005f0a2d40e7e1a611f16bc0901487bd3cdbd79a5935e530bdacd07347322b62`

## Repairs

1. The Hessian support boundary increases from 3.5 to 4.25 samples per
   winning scale. The numerical Hessian estimator remains unchanged.
2. The unstable single-field intrinsic range ratio is retired as a calibrated
   scalar. Intrinsic variogram curves remain valid response surfaces.
3. A new scalar, `physical_gradient_covariance_eigenratio_v1`, reports the
   square root of the global physical-gradient covariance eigenvalue ratio.
   For differentiable Gaussian random fields this estimates the principal
   correlation-length ratio without training. The major axis abstains when the
   ratio is below 1.50.

## Disjoint confirmation data

### Hessian

- Classes: blob, tube and sheet.
- Radii: 5.5, 7.5 and 9.5 µm.
- Spacing: 0.6³, 0.9³, 0.9 × 0.9 × 1.8 and 1.4³ µm.
- Shape: 64³.
- Scale grid: 0.5, 0.75, 1, 1.25 and 1.5 times radius.

### Spatial anisotropy

- Correlation lengths: 12, 20 and 28 µm.
- Ratios: 1.0, 1.5, 2.0, 2.5 and 3.0.
- Ten new deterministic seeds per condition; 150 independent fields total.
- Shape: 192 × 192; spacing 1 × 1 µm.
- Comparator: the frozen intrinsic-variogram range ratio on the same fields
  when its v2.1 support contract emits.

### Equivariance

Twenty-four prespecified anisotropic fields (two seeds per non-isotropic
correlation/ratio cell) undergo a 37° rotation and 0.75× resampling. Rotation
uses the absolute axial turn, avoiding image-coordinate sign convention.

## Gates

All gates must pass:

1. Hessian coverage ≥0.60, emitted balanced accuracy ≥0.95, every-class recall
   ≥0.90, emitted invalid risk ≤0.05 and every raw misclassification rejected.
2. Emitted Hessian winning-scale median relative error ≤0.35 and p95 ≤0.50.
3. Gradient-moment ratio Spearman ρ ≥0.80 across all anisotropic fields,
   median relative error ≤0.10 and p95 ≤0.25.
4. Isotropic median ratio ≤1.20, isotropic p95 ratio ≤1.50 and isotropic axis
   abstention ≥0.90.
5. Fields with programmed ratio ≥2.0 retain an identifiable axis in at least
   0.80 of cases.
6. Across rotated fields, median ratio drift ≤0.10, p95 ≤0.20 and p95 axial
   turn error ≤3°.
7. Across resampled fields, median ratio drift ≤0.10 and p95 ≤0.20.
8. Gradient-moment Spearman ρ is not more than 0.05 below the frozen intrinsic
   range-ratio comparator; both values are reported even if the gate fails.
9. Complementing every synthetic invalidity label leaves response geometry
   byte-identical.
10. A full independent repeat is byte-identical.

## Claim boundary

A pass closes the specific analytic failures from v2 and v2.1. It supports a
fail-closed Hessian class and an untrained gradient-moment anisotropy measure on
these physical grids. It does not validate biological meaning, segmentation,
clinical utility, mechanics, external acquisition transfer or intraoperative
deployment. Both earlier failed confirmations remain part of the required
lineage.
