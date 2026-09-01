# NOSTOS-0 synthetic physical-truth v2.3: frozen terminal confirmation

**Frozen:** 2026-09-01 before any v2.3 execution  
**Opened v2.3 development receipt:** SHA-256
`8641770172f31870f69d5b95cd4b68b5eb06c19085549bd0f365c8d4a84d7862`  
**Frozen response implementation:** SHA-256
`13f35bb457374d0c0dcfba90cf039b60d43db3620c08f8db8720955454d47471`

## Final repairs

- Hessian morphology now requires at least 4.75 samples per winning physical
  scale. The numerical Hessian response is unchanged.
- Gradient-moment axes require an estimated anisotropy ratio of at least 1.55.
  The ratio remains reported near isotropy; only the unstable axis abstains.

## Disjoint confirmation

### Hessian

- Blob, tube and sheet radii: 6.5, 8.5 and 10.5 µm.
- Spacing: 0.7³, 1.1³, 1.1 × 1.1 × 2.2 and 1.6³ µm.
- Shape 64³; scale grid 0.5, 0.75, 1, 1.25 and 1.5 times radius.

### Gradient-moment anisotropy

- Correlation lengths: 14, 22 and 30 µm.
- Programmed ratios: 1.0, 1.4, 1.8, 2.2, 2.8 and 3.2.
- Ten new seeds per condition; 180 fields.
- Thirty prespecified anisotropic fields (two seeds per non-isotropic cell)
  undergo 41° rotation and 0.8× resampling.

## Gates

All gates must pass:

1. Hessian coverage ≥0.60, emitted balanced accuracy ≥0.95, every-class recall
   ≥0.90, emitted invalid risk ≤0.05 and every raw misclassification rejected.
2. Emitted Hessian winning-scale median relative error ≤0.35 and p95 ≤0.50.
3. Gradient ratio Spearman ρ ≥0.80, median relative error ≤0.10 and p95 ≤0.25
   across anisotropic fields.
4. Isotropic median ratio ≤1.20, p95 ratio ≤1.50 and axis abstention ≥0.90.
5. Programmed ratio ≥2.0 retains an identifiable axis in at least 0.80 of fields.
6. Rotation median ratio drift ≤0.10, p95 drift ≤0.20 and p95 axial-turn error
   ≤3° among emitted axes.
7. Resampling median ratio drift ≤0.10 and p95 drift ≤0.20.
8. Complementing every invalidity label leaves geometry byte-identical.
9. A full independent repeat is byte-identical.

## Claim boundary

A pass closes the remaining analytic v2.2 failures only. The complete lineage
must report failed v2, failed v2.1, failed v2.2 and this confirmation together.
No biological, segmentation, clinical, mechanical, acquisition-transfer or
intraoperative claim follows from synthetic validation.
