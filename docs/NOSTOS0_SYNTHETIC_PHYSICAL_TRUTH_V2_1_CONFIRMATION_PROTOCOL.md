# NOSTOS-0 synthetic physical-truth v2.1: frozen repair confirmation

**Frozen:** 2026-08-31 before any v2.1 confirmation execution  
**Opened development receipt:** SHA-256
`c40ab9f619508e2319a9b6c65e84034ea5b742ae103bfdc6a5337d8a5620ace5`  
**Frozen validated-response implementation:** SHA-256
`0205f85a9982f1e572ebc1de167f04c6560a984773bb2f6b80aa702214c4b461`

## Repairs frozen from failed v2 development

1. Tensor orientation is emitted only when the FFT-estimated characteristic
   wavelength has at least 6 samples and spectral anisotropy is at least 0.50.
2. Hessian class is emitted only when the winning physical scale has at least
   3.5 samples along the coarsest voxel dimension.
3. Intrinsic variogram range anisotropy is emitted only when both intrinsic
   ranges are identifiable and median angular anisotropy is at least 0.20.
4. Network fragmentation truth is corrected from 1.25 times half-width to the
   continuous analytic half-width. No network estimator changes.
5. Local thickness and the numerical tensor, Hessian, FFT and erosion
   estimators remain unchanged.

## Disjoint confirmation grids

No v2 angle, wavelength, radius, diameter, width, correlation length or random
seed is reused.

### Organization

- Angles: 19°, 47°, 83°, 127°, 163°.
- Wavelengths: 9, 15, 27, 36 µm.
- Isotropic spacing: 0.75, 1.25 and 1.75 µm.
- Shape 192 × 192; new deterministic seeds.
- Five white-noise fields and five crossed-orientation fields are prespecified
  non-identifiable controls.

### Hessian morphology

- Blob, tube and sheet radii: 5, 7 and 9 µm.
- Spacing: 0.75 × 0.75 × 0.75, 0.75 × 0.75 × 1.5 and
  1.25 × 1.25 × 1.25 µm.
- Shape 56 × 56 × 56.
- Per-case scale grid: 0.5, 0.75, 1, 1.25 and 1.5 times radius.

### Thickness

- 2D sheets: diameters 10, 18 and 30 µm at 0.75 × 0.75,
  1.25 × 1.25 and 0.75 × 1.5 µm spacing.
- 3D tubes and sheets: diameters 10, 14 and 18 µm at
  0.75 × 0.75 × 0.75 and 0.75 × 0.75 × 1.5 µm spacing.

### Network

- Full arm widths: 6, 10 and 14 µm.
- Spacing: 0.75 × 0.75, 1.25 × 1.25 and 0.75 × 1.5 µm.
- Analytic fragmentation truth: half the programmed full width.
- Physical erosion thresholds: 0 to 1.5 half-width in 0.25-half-width steps.

### Spatial heterogeneity

- Correlation lengths: 10, 18 and 26 µm.
- Anisotropy ratios: 1.0, 1.8 and 2.6.
- Five new seeds per condition; shape 192 × 192; spacing 1 × 1 µm.
- Frozen separations: 2, 4, 6, 8, 12, 16, 24, 32, 48, 64 and 80 µm.

### Perturbations

The disjoint 47°/27-µm reference is challenged by rotation 23°, resampling
0.8×, crop 0.75, blur 1.2 pixels, noise 0.15 standard deviations, contrast
0.5×, anisotropic PSF 1 pixel and partial-volume sampling 0.65×.

## Predeclared gates

All gates must pass:

1. Organization coverage ≥0.75; among emitted cases, p95 maximum tensor angular
   error ≤2.5°, invalid risk (error >2.5°) ≤0.02 and every >2.5° case is rejected.
2. All ten non-identifiable organization controls are rejected.
3. Hessian coverage ≥0.60; emitted balanced accuracy ≥0.95, every-class recall
   ≥0.90 and invalid risk ≤0.05; every misclassification is rejected.
4. Hessian emitted winning-scale median relative error ≤0.35 and p95 ≤0.50.
5. Thickness median relative error ≤0.10, p95 ≤0.20 and anisotropic p95 ≤0.25.
6. Network median fragmentation relative error ≤0.15, p95 ≤0.35 and every
   survival curve is monotone.
7. Spatial anisotropic coverage ≥0.50, isotropic abstention ≥0.80, emitted
   ratio Spearman ρ ≥0.75, median relative ratio error ≤0.35 and p95 ≤0.55.
8. At least six of eight perturbations remain supported; every supported
   perturbation has maximum tensor error ≤2.5°.
9. Output geometry and scores are unchanged when synthetic validity labels are
   complemented.
10. A complete independent repeat is byte-identical.

## Claim boundary

A pass validates the repaired support contracts only on these disjoint analytic
physical grids. It does not establish biological meaning, segmentation,
external acquisition transfer, clinical utility, mechanics or intraoperative
performance. The failed v2 receipt remains mandatory context.
