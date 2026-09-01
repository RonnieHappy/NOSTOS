# NOSTOS-0 score-design amendment, corrected calibration

This document replaces the v1 score-design amendment for all future BioSR execution. The physical-calibration correction is defined and locked separately in `NOSTOS0_BIOSR_CALIBRATION_CORRECTION.md`.

Only three input-only score formulas may be compared on the restarted, correctly calibrated `score_design` partition:

1. The v2 maximum of acquisition QC, physical sampling, perturbation stability and cross-scale agreement.
2. The same maximum plus tensor-orientation observability.
3. Perturbation stability and cross-scale agreement plus orientation observability, with acquisition QC and physical-sampling hard preconditions retained at the operating point.

Orientation observability applies only to tensor orientation and is 0.15 divided by input tensor coherence at the same physical scale. It is dimensionless and does not depend on the incorrect v1 physical labels. No continuous weights, endpoint-specific transformations or tissue-specific coefficients may be fitted.

The primary design metric is unweighted macro AURC across informative structure × endpoint × requested-scale strata. A candidate fails if its structure-specific macro AURC is more than 0.01 worse than `v2_full_max` in either CCPs or ER. The lowest pooled macro AURC then wins; differences no larger than 0.01 are ties resolved in favor of fewer components.

Every miscalibrated v1/v2 endpoint output is quarantined. The candidate comparison may consume only fresh protocol-2.0 receipts whose MRC header spacing, physical field of view, configuration hash and implementation hash all verify.

No threshold-calibration or confirmation archive had been accessed when this corrected candidate set was locked.
