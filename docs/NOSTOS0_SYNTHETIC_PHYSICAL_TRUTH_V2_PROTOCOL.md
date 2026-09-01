# NOSTOS-0 synthetic physical-truth benchmark v2: frozen protocol

**Frozen:** 2026-08-31 before v2 execution  
**Relationship to v1:** additive; the v1 receipt is never overwritten  
**Purpose:** replace single-case module checks with a calibrated 2D/3D truth
grid and explicit failure semantics.

## Measurement grids

### Spectral and tensor organization

- Axial orientations: 7°, 31°, 67°, 113° and 151°.
- Wavelengths: 8, 12, 24 and 40 µm.
- Isotropic spacing: 0.5, 1.0 and 1.5 µm per pixel.
- Image shape: 192 × 192.
- Supported cases require at least four samples per programmed wavelength.
- Spectral orientation and wavelength are evaluated from the calibrated FFT.
- Tensor orientation is evaluated at physical integration scales 1, 2 and 4 µm.

### Hessian morphology

- Analytic 3D Gaussian blob, tube and sheet profiles.
- Radius: 4, 6 and 8 µm.
- Isotropic spacing 1 × 1 × 1 µm and anisotropic spacing 1 × 1 × 2 µm.
- Volume shape: 48 × 48 × 48.
- Scale grid per case: 0.5, 0.75, 1.0, 1.25 and 1.5 times the programmed
  radius.

### Local thickness

- 2D sheets with programmed diameters 8, 16, 24 and 32 µm.
- Spacing 0.5 × 0.5, 1 × 1 and 1 × 2 µm.
- 3D tube and sheet masks with programmed diameters 8, 12 and 16 µm at
  1 × 1 × 1 and 1 × 1 × 2 µm spacing.
- Estimator: frozen 32-bin maximal-sphere local thickness; p95 is the primary
  diameter estimate.

### Network survival

- Six-arm, one-junction analytic 2D network.
- Programmed full arm widths 4.8, 8.0 and 12.0 µm.
- Spacing 0.5 × 0.5, 1 × 1 and 1 × 2 µm.
- Boundary-corrected physical erosion thresholds from zero through 1.5 times
  the programmed half-width in 0.25-half-width increments.
- Primary truth: loss of image-spanning percolation at the first erosion
  threshold above the programmed half-width, subject to sampling tolerance.

### Spatial heterogeneity

- Gaussian random fields with programmed correlation lengths 8, 16 and 24 µm.
- Programmed anisotropy ratios 1, 2 and 3.
- Five independent seeds per condition.
- Spacing 1 × 1 µm, shape 192 × 192.
- Primary endpoint: recovery of anisotropy ordering from the ratio of estimated
  horizontal and vertical variogram ranges. Absolute range is secondary because
  finite-field and discrete-lag estimators are biased.

## Controlled perturbations

The reference orientation phantom (31°, wavelength 24 µm, 1 µm spacing) is
tested under rotation 17°, resampling 0.75×, retained crop 0.8, Gaussian blur
1 pixel, additive noise 0.1 standard deviations, contrast 0.65×, anisotropic PSF
0.75 pixel and partial-volume sampling 0.7×.

Thickness masks are eroded and dilated by two pixels. The expected scientific
behavior is directional sensitivity, not invariance: erosion must reduce and
dilation must increase the p95 thickness.

## Abstention challenges

The frozen validity function must abstain, with the correct reason, when:

1. the requested scale has fewer than four pixels;
2. signal-to-noise ratio is below 3;
3. eligible mask coverage is below 5%.

It must emit when all three support conditions are met exactly at their declared
boundaries.

## Predeclared gates

All gates must pass:

1. Spectral orientation median error ≤1° and p95 ≤3°.
2. Spectral wavelength median relative error ≤0.08 and p95 ≤0.20.
3. Tensor orientation median error ≤1° and p95 ≤2.5°; fifth-percentile
   coherency ≥0.75.
4. Hessian balanced accuracy ≥0.90, each-class recall ≥0.80 and anisotropic-case
   accuracy ≥0.80.
5. Hessian winning-scale median relative error ≤0.35 and p95 ≤0.50.
6. Thickness median relative error ≤0.10, p95 ≤0.20 and anisotropic-case p95
   ≤0.25.
7. Network fragmentation-threshold median relative error ≤0.20 and p95 ≤0.35;
   all survival curves are monotone.
8. Spatial recovered-versus-programmed anisotropy Spearman ρ ≥0.80; median
   relative ratio error ≤0.35; isotropic recovered ratios lie within 0.75–1.33.
9. All eight orientation perturbations either remain within 5° and 20% scale
   error or correctly abstain.
10. Mask erosion decreases and dilation increases thickness in every spacing
    condition.
11. All four abstention/boundary challenges return the predeclared outcome and
    reason set.
12. A complete independent repeat is byte-identical.

## Claim boundary

A pass supports analytic recovery and controlled perturbation behavior for the
tested implementations and physical ranges. It does not validate biological
interpretation, segmentation, unseen acquisition families, clinical use,
mechanics or intraoperative performance. A failed module gate remains visible
and blocks that module's general claim.
