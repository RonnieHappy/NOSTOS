# NOSTOS-0 paired-acquisition score-design amendment

## Purpose

The frozen paired-acquisition protocol reserved the `score_design` half of the CCP and ER reference fields for choosing the input-only support-score formula. This amendment freezes the candidate set and deterministic selection rule before the remaining development fields have been evaluated.

## Design-only observation motivating the amendment

The first authorized score-design field, `CCPs|Cell_001`, showed that a tensor-orientation estimate can remain stable under mild transformations while disagreeing with the registered high-resolution reference. This is physically plausible for approximately isotropic puncta: repeatability alone does not establish that an orientation is observable.

No threshold-calibration field or confirmation archive had been decoded, listed, summarized or visualized when this amendment was written. The observation above is development evidence and will never be reported as confirmation.

## Frozen candidate set

Only three formulas may be compared:

1. The original maximum of acquisition QC, physical sampling, perturbation stability and cross-scale agreement.
2. The original maximum plus an orientation-observability component.
3. Perturbation stability and cross-scale agreement plus orientation observability, omitting generic acquisition QC and sampling from the ranking while retaining their hard abstention rules.

The orientation-observability component applies only to tensor orientation. It is the ratio of the predeclared minimum interpretable coherence (0.15) to the input tensor coherence at the same physical scale. A value of 1 therefore has a direct physical interpretation: the input reaches the minimum directional strength needed to support an angle.

No continuous weights, endpoint-specific score transformations or tissue-specific coefficients may be fitted.

## Frozen selection rule

The primary metric is unweighted macro area under the risk-coverage curve (AURC) across structure × endpoint × requested-scale strata that contain at least one valid and one invalid reference-eligible case.

A candidate is excluded if its structure-specific macro AURC is more than 0.01 worse than the original formula in either CCPs or ER. Among the remaining candidates, the lowest pooled macro AURC wins. Differences of 0.01 or less are ties, resolved in favor of the formula with fewer components.

Micro AURC, every stratum, constant-outcome strata and clustered-bootstrap paired differences remain mandatory secondary reports. Threshold selection remains prohibited until the selected implementation and score receipt are SHA-256 locked.

## Explicitly rejected shortcut

A single-image Fourier mid-band-to-noise-floor ratio is not a candidate. Although it tracked the nominal signal levels in the first CCP field, high-frequency power also depends on specimen morphology. Incorporating it could make a sample-agnostic support decision tissue-dependent. It may be studied later as an acquisition-specific optional diagnostic, but it cannot enter this frozen benchmark.
