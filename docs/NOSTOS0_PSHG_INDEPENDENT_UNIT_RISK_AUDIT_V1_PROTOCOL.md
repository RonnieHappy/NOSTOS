# PSHG independent-unit finite-sample risk audit v1

## Status and purpose

This is a **retrospective audit**, not a prospective confirmation and not a
newly tuned operating policy. It evaluates the already frozen PSHG-TISS v1
full-contract policy at its original maximum predicted row risk of 0.15.

The original confirmation reports perturbation-condition rows nested within
24 independent ROIs. Its row-level risk is useful for condition-level behavior
but cannot by itself establish a finite-sample guarantee at the independent ROI
level. This audit asks whether the fixed policy supports the stronger statement
that no more than 20% of accepted ROIs contain any silently invalid accepted
condition.

## Inputs

- Frozen profile:
  `outputs/nostos0-pshg-acquisition-shift-v1-development/development.json`
- Frozen confirmation rows:
  `outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation_rows.jsonl`
- Frozen confirmation receipt:
  `outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation.json`

## Fixed calculations

1. Recompute the full-contract calibrated risk by linear interpolation through
   the frozen isotonic map.
2. Accept a row when calibrated risk is at most 0.15.
3. Define an accepted ROI as an ROI with at least one accepted row.
4. Define an ROI-level silent failure as any accepted ROI containing at least
   one accepted row whose frozen `invalid` label is true.
5. Report the observed ROI failure fraction and its one-sided 95% exact
   Clopper–Pearson upper confidence bound.

## Audit gate

The stronger independent-unit risk claim passes only when:

- all 24 confirmation ROIs are present;
- the recomputed row-level operating counts exactly match the frozen receipt;
- at least 60% of rows and at least 60% of ROIs are accepted; and
- the one-sided 95% exact upper bound for ROI silent-failure risk is at most
  0.20.

Failure does not invalidate the original row-level comparison with acquisition
or endpoint QC. It blocks a stronger independent-unit finite-sample guarantee
and requires the manuscript to label its bootstrap risk estimates as
descriptive.
