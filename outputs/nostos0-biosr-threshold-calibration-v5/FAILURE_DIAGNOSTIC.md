# NOSTOS-0 BioSR v5 failure diagnostic

**Status:** Descriptive diagnosis of a prospectively failed gate  
**Confirmation data:** Not accessed  
**Decision use:** Development of a new v6 method only; no v5 threshold is authorized

## What failed

The frozen v5 selector found no single score threshold satisfying the risk and coverage contract across every assessable structure-endpoint combination. This audit asks whether the failure is merely caused by the shared cutoff or whether any endpoint is irreducibly unsupported under the frozen v5 score.

## Endpoint-level bottleneck

- **ER / variogram_range_vertical:** best observed risk 10.76% at 100.00% coverage (threshold `1`).

Each line above gives the lowest descriptive risk obtainable when that combination is allowed its own threshold while retaining at least 70% coverage. Because ER vertical variogram range remains above 10%, removing the global-cutoff constraint alone cannot make v5 pass.

## Score-scale incompatibility

- **ER:** tensor_coherence requires `0.299914` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** tensor_coherence requires `0.299914` while tensor_orientation requires `0.996458` at their independent diagnostic optima.
- **ER:** spectral_anisotropy requires `0.344756` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** spectral_anisotropy requires `0.344756` while tensor_orientation requires `0.996458` at their independent diagnostic optima.
- **ER:** hessian_blob_curve requires `0.403479` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** hessian_tube_curve requires `0.403479` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** spectral_entropy requires `0.403479` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** variogram_horizontal_curve requires `0.403479` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** variogram_range_horizontal requires `0.403479` while variogram_range_vertical requires `1` at their independent diagnostic optima.
- **ER:** variogram_range_vertical requires `1` while variogram_vertical_curve requires `0.403479` at their independent diagnostic optima.

These are post-failure diagnostics, not permissible v5 operating thresholds. They show that endpoint families do not share a commensurate raw risk-score scale.

## Consequence

Version 5 remains failed. The calibration fields are now development data and cannot provide confirmation for a repaired method. A v6 design must use endpoint-family calibration, preserve one structure-independent algorithm, replace or withhold coordinate-dependent variogram range scalars, and be frozen before any confirmation structure is accessed.

The output does not justify biological, clinical, intraoperative or acquisition-family claims.
