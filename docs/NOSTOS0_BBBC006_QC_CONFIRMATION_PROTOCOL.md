# Frozen BBBC006 QC confirmation protocol

**Protocol:** `nostos-bbbc006-qc-confirmation/1.0`  
**Frozen:** 27 August 2026, before extraction or pixel inspection of confirmation identities

The initial normalized-Laplacian focus endpoint failed on the 64-case development subset and remains in the evidence record. Five replacements were compared only on those opened identities. The frozen selection rule chose mean Tenengrad energy, defined as the mean squared magnitude of reflect-mode Sobel derivatives.

Confirmation uses ranks 65–192 of the same outcome-independent SHA-256 ordering of BBBC006 well–site–channel identifiers, giving 128 identities disjoint from development. Planes z=15 and z=16 are expert-classified in focus; z=0 is out of focus. No threshold is fitted.

## Gates

1. All 128 matched triplets execute with finite scores.
2. z=16 exceeds z=0 in at least 90% of cases.
3. z=15 exceeds z=0 in at least 90% of cases.
4. Median z=15/z=16 score ratio lies between 0.5 and 2.0.
5. Both paired bootstrap 95% intervals for median in-focus-minus-z=0 score exclude zero, using 20,000 resamples and seed 6008.
6. Constant-field and high-endpoint-fraction controls retain their declared abstain and review flags.

The confirmation supports relative focus ordering in one acquisition, not a universal acceptable-focus cutoff.
