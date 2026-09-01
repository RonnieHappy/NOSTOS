# NOSTOS-0 BioSR tensor v7 confirmation protocol

## Why v7 exists

The locked v6 confirmation failed on Microtubules. Its scalar tensor-axis endpoint was not physically scale matched across acquisition grids, and its acceptance rule lost too much coverage. That failure remains sealed and is not overwritten.

V7 changes the estimand rather than tuning the failed result away. It uses a physical two-scale structure tensor and preserves the complete axial orientation distribution. The single derived axis remains diagnostic-only because a global axis is not identifiable in crossing, multimodal or near-isotropic fields.

## Development evidence and claim separation

Development used disclosed CCP and ER fields plus the already consumed Microtubules confirmation fields. Across 71 fields and 5,010 eligible tensor cases, the family-specific contract retained 5,008 cases and 44 were invalid relative to the registered high-resolution reference. Observed risk was 0.88%, with a field-cluster bootstrap upper 95% bound of 1.54%.

A two-effective-pixel Gaussian resolution-margin probe ranked coherence failures better than conventional acquisition QC in development. Its cutoff, however, was selected using those same outcomes. The paired cluster bootstrap is therefore descriptive and cannot establish incremental utility. The untouched F-actin confirmation is the first eligible test of that claim.

The orientation-distribution endpoint does not use this strong probe for acceptance. Development showed essentially no orientation-distribution risk-ranking gain, so including it would add unsupported rejection.

## Untouched confirmation samples

Two BioSR acquisition families are used:

- F-actin linear SIM: 2x reference sampling, 12 signal levels, 9 raw frames per level.
- F-actin nonlinear SIM: 3x reference sampling, 9 signal levels, 25 raw frames per level.

Eight fields per family are selected by a deterministic SHA-256 ranking of central-directory cell identifiers. All signal levels in selected fields are analyzed. Selection does not use pixels, image dimensions, intensities, registration, endpoint errors or support scores.

For nonlinear SIM, `SIM_gt_a.mrc` is the only primary reference. The BioSR repository owner states that `SIM_gt_a.mrc` was used for network training and that `SIM_gt_b.mrc` is a gamma-0.6 overview image. The overview image is excluded from every endpoint and gate.

## Frozen endpoints

At five physical response scales (0.2504, 0.3756, 0.5008, 0.7512 and 1.0016 micrometres), NOSTOS emits:

1. Tensor coherence, with invalidity defined as absolute disagreement above 0.15.
2. A 36-bin axial orientation distribution, compared by circular Wasserstein-1 distance with invalidity above 10 degrees.

Each input is the float64 arithmetic mean of its raw SIM frames. Input and reference are registered before comparison. All endpoint values retain acquisition, sampling, perturbation, registration and provenance data.

## Frozen decision logic

Measurement safety is primary and separate from novelty:

- Overall coverage must be at least 80%.
- Coverage in every structure-endpoint family must be at least 70%.
- Observed risk must be at most 10%.
- The field-cluster bootstrap upper 95% risk bound must be at most 15% overall and in every structure-endpoint family.

Incremental coherence utility is a second claim:

- Full-contract risk cannot exceed conventional-QC risk.
- Coverage loss cannot exceed 10 percentage points.
- Cases rejected only by the full contract must have at least twofold invalid-case enrichment.
- Full-contract AURC must be smaller than conventional-QC AURC.
- A paired field-cluster bootstrap must give at least 95% probability of benefit and a positive lower 95% confidence bound.

If conventional QC emits no invalid coherence case, utility is formally not assessable. That does not turn a safety pass into a superiority claim.

## Reproducibility boundary

The archives were downloaded and MD5 verified before v7. Their ZIP central directories were inspected to resolve the v6 layout error. No F-actin pixel array or tensor endpoint outcome was decoded before the v7 implementation, exact selected fields, thresholds, gates and lock were written.

Primary sources:

- BioSR Figshare record: https://figshare.com/articles/dataset/BioSR/13264793
- BioSR Nature Methods paper: https://doi.org/10.1038/s41592-020-01048-5
- Official BioSR code: https://github.com/qc17-THU/DL-SR
- Maintainer clarification of nonlinear references: https://github.com/qc17-THU/DL-SR/issues/8#issuecomment-1037742991

