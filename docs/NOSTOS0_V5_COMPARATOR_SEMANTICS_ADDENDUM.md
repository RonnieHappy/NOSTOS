# NOSTOS-0 v5 comparator-semantics addendum

**Date identified:** 29 August 2026  
**Affected result:** v5 threshold-calibration comparator operating points  
**Unaffected result:** the v5 full-contract gate failure and absence of a threshold lock

## Defect

The v5 threshold selector used one shared acceptance helper for every score condition. That helper always rejected a row carrying any NOSTOS hard-abstention reason before applying the selected condition's score. Consequently, the threshold-level policy labelled `conventional_acquisition_qc` inherited physical-sampling and measurement-identifiability hard abstentions from the complete NOSTOS contract.

It was therefore a hybrid policy, not a pure conventional-QC-only comparator. The same issue affected leave-one-component-out threshold policies: removing a continuous score component did not necessarily remove the hard precondition governed by that component.

The AURC calculations in v5 did not use this hard-abstention helper and remain score-ranking summaries. The defect concerns the interpretation of threshold operating points and comparator policies.

## Effect on the v5 decision

The primary v5 result is unchanged. The complete full-contract policy found no global threshold satisfying the prospectively frozen per-combination risk and coverage constraints. No threshold lock was written, and confirmation access was not authorized.

The statement that conventional acquisition QC also found no operating point must be read as applying to the historical hybrid comparator. It cannot be used as evidence that a clean QC-only policy failed.

No v5 file, threshold or outcome has been rewritten. This addendum is appended to the immutable failure receipt.

## Prospective correction

Version 6 defines hard-precondition ownership explicitly:

| Policy component | Governed hard preconditions |
| --- | --- |
| Acquisition QC | Acquisition-QC abstention only |
| Physical sampling | Fewer than four effective samples per requested scale |
| Identifiability | Low orientation resultant, low spectral anisotropy, estimator disagreement and scale-boundary censoring |
| Perturbation stability | Continuous probe-instability score; no independent hard reason in the current estimator |

`always_emit` ignores all NOSTOS hard abstentions when the estimator has produced a value. `conventional_acquisition_qc` applies only its own score and acquisition-QC hard failure. A leave-one-component-out policy removes both the continuous score and the hard preconditions owned by that component. Unknown hard reasons fail validation rather than being silently assigned.

These rules are implemented in `src/nostos/validation/selective_policy_v6.py` and tested in `tests/test_selective_policy_v6.py`. They are frozen before confirmation and cannot be adjusted using confirmation outcomes.

## Claim boundary

This correction strengthens comparator validity. It does not convert the v5 failure into a pass, validate the v6 method, establish superiority over conventional QC, or support biological or clinical claims.
