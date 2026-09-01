# NOSTOS-0 threshold-calibration v5 failure audit

**Audit date:** 29 August 2026  
**Gate decision:** FAIL — no operating threshold; do not access confirmation data  
**Software status:** Research and development only  
**Clinical status:** No diagnosis, treatment, intraoperative decision or patient-specific interpretation is supported

## Executive finding

Version 5 did not pass its first genuinely held-out validation gate. The unchanged estimator substantially ranked paired-acquisition errors: its retained-endpoint area under the risk–coverage curve (AURC) was 0.013173, compared with 0.054949 for always emitting a measurement, a 76.03% reduction. That ranking result is promising but insufficient. The prospectively frozen protocol required one global score threshold to retain at least 80% of all reference-eligible measurements, retain at least 70% of every assessable structure–endpoint combination, keep observed risk at or below 10% both globally and within every combination, and keep the reference-field-clustered upper 95% risk at or below 15%. No candidate threshold satisfied the deterministic risk and coverage constraints, so no bootstrap-eligible candidate existed and no threshold was locked.

The failure is scientifically informative. A read-only diagnostic showed two distinct problems:

1. ER vertical variogram range is unsupported under v5. Even when allowed its own threshold, its lowest observed risk at or above 70% coverage was 17 errors among 158 accepted cases, or 10.76%, above the frozen 10% ceiling.
2. The raw validity scores are not commensurate across endpoint families. ER tensor coherence reached its best qualifying point at a score threshold of 0.299914, whereas ER tensor orientation required 0.996458. A single raw cutoff cannot express comparable risk for these endpoints.

Therefore v5 remains failed. Removing a difficult endpoint after seeing this result, weakening the 10% ceiling, or selecting separate v5 thresholds post hoc would be outcome-dependent tuning and is not permitted. The 63 calibration fields are now development data for a separately frozen v6 method. Confirmation archives remain sealed.

## Audit question

The gate asked a narrow tool-use question:

> Can a predeclared NOSTOS validity score select paired-acquisition structural measurements that agree with registered high-resolution references at an acceptable risk and coverage, using one unchanged threshold across two development structures?

It did not ask whether the high-resolution acquisition is biological truth, whether NOSTOS detects disease, whether measurements generalize to other microscopes or tissues, or whether the software is clinically usable. Those claims require different evidence.

## Prospective safeguards

All decision rules were fixed before threshold-calibration pixel access in `manifests/paired_acquisition_support_score_formula_lock_v2.json`.

| Rule | Frozen value |
| --- | ---: |
| Development structures | Clathrin-coated pits (CCPs) and endoplasmic reticulum (ER) |
| Partition | SHA-256 field partition, remainders 2 and 3 of modulo 4 |
| Score | Maximum of acquisition QC, physical sampling, perturbation stability and measurement identifiability |
| Cross-scale term | Diagnostic only; excluded from validity score |
| Overall observed-risk ceiling | 10% |
| Per structure–endpoint observed-risk ceiling | 10% |
| Overall coverage floor | 80% |
| Per structure–endpoint coverage floor | 70% |
| Cluster-bootstrap upper 95% risk ceiling | 15% |
| Bootstrap | 10,000 draws, seed 26,082,801, reference-field clusters stratified by structure |
| Required AURC reduction versus always emit | 20% |
| Selection | Highest-coverage tied cutoff satisfying every rule |

The per-combination constraint was deliberately included to prevent many easy endpoints from diluting failure in one difficult endpoint. A structure–endpoint combination with no reference-eligible cases was reported as not assessable rather than passed. Conventional acquisition QC was subjected to the same selector.

The first attempted commands stopped before archive hashing, indexing or pixel decoding because an immutable historical lock referenced the earlier profile hash. The lineage discrepancy was documented prospectively in `manifests/paired_acquisition_support_profile_lineage_amendment_lock.json`; the estimator, endpoint values, tolerances and score formula were not changed. The version-2 score lock was then written and verified before any threshold field was accessed.

## Held-out sample and execution

The calibration used every field assigned to the frozen threshold partition and none from the 12-field score-design pilot.

| Structure | Independent reference fields | Paired acquisitions | Registration-eligible pairs | All generated rows | Hard-abstention rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| CCPs | 30 | 270 | 237 | 5,670 | 4 |
| ER | 33 | 198 | 192 | 4,158 | 49 |
| **Total** | **63** | **468** | — | **9,828** | **53** |

After applying the pre-existing profile, 8,424 rows belonged to the ten retained claim endpoints. Of these, 5,678 cases were registration- and reference-eligible. Counts are endpoint cases, not independent specimens; uncertainty is clustered by the 63 reference fields.

The three developmentally disabled scalar endpoints—Hessian blob scale, Hessian tube scale and Fourier characteristic scale—were not reintroduced into the gate. CCP global orientation had zero eligible cases because the punctate images did not support one coherent axial direction; this was correctly treated as not assessable.

## Prospective gate result

| Validity policy | AURC | Interpretation |
| --- | ---: | --- |
| Full NOSTOS v5 contract | 0.013173 | Strong ranking relative to always emit |
| Always emit | 0.054949 | Non-selective baseline |
| Conventional acquisition QC | 0.014076 | Nearly as strong as the full contract in the combined retained set |

The full contract reduced AURC by 76.03% relative to always emit and by only 6.41% relative to conventional acquisition QC. The latter advantage is modest and must not be presented as decisive superiority.

The AURC requirement passed, but the operating-point requirement failed:

- 1,258 tied full-contract candidate thresholds were examined.
- No candidate satisfied the deterministic aggregate and per-combination risk/coverage rules.
- Consequently, zero candidates reached the cluster-bootstrap step.
- Conventional acquisition QC also produced no valid operating point among 388 candidates.
- `manifests/paired_acquisition_support_threshold_lock.json` was not created.
- Confirmation access was not authorized.

AURC measures ranking over all possible coverages. A tool still needs a defensible operating point to decide when an individual result is supported. Good AURC cannot substitute for that decision rule.

## Reproducible post-failure diagnosis

After the prospective failure was recorded, `scripts/audit_biosr_threshold_failure_v5.py` independently evaluated each observed structure–endpoint combination. For diagnosis only, each combination was allowed its own cutoff. The reported point minimizes observed risk among cutoffs retaining at least 70% of eligible cases, breaking risk ties in favor of greater coverage. This procedure cannot authorize v5 confirmation.

| Structure | Endpoint | Eligible | Best threshold | Coverage | Errors | Risk | Independent diagnostic |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| CCPs | Hessian blob curve | 237 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Hessian tube curve | 237 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Spectral anisotropy | 237 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Spectral entropy | 237 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Tensor coherence | 1,185 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Tensor orientation | 0 | — | — | — | — | Not assessable |
| CCPs | Horizontal variogram curve | 237 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Horizontal variogram range | 237 | 1.000000 | 100.00% | 0 | 0.00% | Pass |
| CCPs | Vertical variogram range | 237 | 1.000000 | 100.00% | 7 | 2.95% | Pass |
| CCPs | Vertical variogram curve | 237 | 0.456628 | 100.00% | 0 | 0.00% | Pass |
| ER | Hessian blob curve | 192 | 0.403479 | 100.00% | 0 | 0.00% | Pass |
| ER | Hessian tube curve | 192 | 0.403479 | 100.00% | 0 | 0.00% | Pass |
| ER | Spectral anisotropy | 192 | 0.344756 | 92.71% | 0 | 0.00% | Pass |
| ER | Spectral entropy | 192 | 0.403479 | 100.00% | 0 | 0.00% | Pass |
| ER | Tensor coherence | 960 | 0.299914 | 70.31% | 56 | 8.30% | Pass |
| ER | Tensor orientation | 158 | 0.996458 | 77.85% | 10 | 8.13% | Pass |
| ER | Horizontal variogram curve | 192 | 0.403479 | 100.00% | 0 | 0.00% | Pass |
| ER | Horizontal variogram range | 169 | 0.403479 | 78.11% | 6 | 4.55% | Pass |
| ER | Vertical variogram range | 158 | 1.000000 | 100.00% | 17 | 10.76% | **Fail** |
| ER | Vertical variogram curve | 192 | 0.403479 | 100.00% | 0 | 0.00% | Pass |

The raw score distributions still separate many errors: among 5,643 eligible non-hard-abstention claim cases, the median full-contract score was 0.1071 for valid cases and 0.3553 for invalid cases. However, their distributions overlap, and endpoint-specific score semantics differ. This is why the ranking curve looks good while the universal cutoff fails.

## Root-cause assessment

### 1. Coordinate-dependent range scalar

The horizontal and vertical variogram range scalars are tied to image axes. For a rotated or locally curving network, “vertical range” is not an intrinsic specimen property. The normalized directional response curves can remain reproducible while a threshold-crossing range scalar becomes unstable or non-identifiable. The particularly poor ER vertical-range behavior is consistent with this design weakness.

This does not prove that every observed error is caused by rotation. It establishes that the current scalar lacks a defensible generic invariance contract and empirically fails the gate. Version 6 should not simply retune its threshold.

### 2. Non-commensurate endpoint score scales

The v5 score is the maximum of four component risks, each normalized internally. That maximum orders failures reasonably across the aggregate. It does not guarantee that a value of 0.30 has the same error probability for a tensor curve, orientation angle or variogram range. The coherence/orientation cutoff split demonstrates this empirically.

A defensible v6 design needs a shared calibration algorithm that maps each endpoint family's raw support evidence to a comparable estimated risk. The algorithm and calibration procedure may be common while fitted endpoint-family parameters differ. Structure-specific thresholds remain prohibited because they would undermine sample-agnostic use.

### 3. Comparator ceiling

The combined full-contract AURC is only modestly better than conventional acquisition QC. Some NOSTOS-specific components are useful in ER, but the present evidence does not yet show a decisive gain over ordinary QC. Version 6 must compare calibrated NOSTOS risk against calibrated conventional QC at matched coverage, with reference-field-clustered uncertainty and prespecified endpoint-family analyses.

## Required v6 repair

The next method version must be treated as new development, not a continuation of the failed v5 confirmation path.

1. **Replace axis-specific range claims.** Preserve the full directional variogram response. Derive rotation-invariant major/minor correlation ranges only when the directional model is identifiable; otherwise abstain. Record specimen-coordinate direction only when an external coordinate transform is supplied.
2. **Calibrate endpoint-family risk.** Fit one predeclared calibration procedure per endpoint family using only the 12 pilot fields and these 63 now-open development fields. Candidate procedures must be compared by field-clustered cross-fitting, calibration error, monotonicity and risk–coverage behavior. No tissue or structure label may enter the mapping.
3. **Use cross-fitting during development.** Every reported development estimate for a fitted calibration map must be out of fold at the reference-field level. Patches, scales, signal levels and endpoints from the same reference field must remain in one fold.
4. **Freeze the complete v6 contract.** Lock endpoint definitions, transformations, eligible families, score calibration, risk ceilings, coverage floors, random seeds, comparator procedures, field partitions and failure rules before confirmation access.
5. **Retain a hard no-tuning boundary.** Microtubule and F-actin confirmation archives may be accessed only after the v6 code, profile, thresholds or calibration maps, tests and cryptographic receipt are immutable. If v6 fails confirmation, those data become development data and a v7 method is required.
6. **Do not expand claims prematurely.** Paired-acquisition agreement supports measurement reliability relative to a registered higher-resolution reference. It does not establish biological meaning, cross-microscope generalization, diagnosis, clinical use or intraoperative utility.

The v6 confirmation primary endpoint should remain silent-invalid rate at matched coverage, with area under the risk–coverage curve as a secondary ranking metric. A passing aggregate result must still pass every assessable endpoint family or explicitly withhold that family from the profile before confirmation.

## Software verification

The repository was verified after the diagnostic implementation:

- `uv run --frozen pytest -q`: 224 passed, 4 skipped, 0 failed; 12 dependency deprecation warnings.
- `uv run --frozen python -m compileall -q src scripts`: exit code 0.
- Focused failure-diagnostic, threshold-selector and lock-lineage tests: 10 passed.
- Threshold lock existence check: absent, as required.

The 12 warnings arise from scikit-image calling the deprecated `numpy.fix` function during phase-correlation tests. They are not NOSTOS failures but should remain visible in dependency maintenance.

## Reproducibility objects

- Frozen score formula: `manifests/paired_acquisition_support_score_formula_lock_v2.json`
- Prospective calibration result: `outputs/nostos0-biosr-threshold-calibration-v5/threshold_calibration.json`
- Prospective verdict: `outputs/nostos0-biosr-threshold-calibration-v5/THRESHOLD_VERDICT.md`
- Post-failure machine diagnostic: `outputs/nostos0-biosr-threshold-calibration-v5/failure_diagnostics.json`
- Endpoint diagnostic table: `outputs/nostos0-biosr-threshold-calibration-v5/structure_endpoint_best_points.csv`
- Human diagnostic summary: `outputs/nostos0-biosr-threshold-calibration-v5/FAILURE_DIAGNOSTIC.md`
- Diagnostic implementation: `src/nostos/validation/failure_diagnostics.py`
- Executable audit: `scripts/audit_biosr_threshold_failure_v5.py`
- Diagnostic tests: `tests/test_failure_diagnostics.py`
- Final failure receipt: `manifests/paired_acquisition_support_threshold_failure_receipt_v5.json`

The final receipt hashes every primary input, run artifact, diagnostic artifact, implementation file and this audit.

## Final decision

The validation process worked correctly because it stopped an attractive aggregate result from becoming an unsupported tool claim. NOSTOS v5 shows promising selective-risk ranking but does not have a defensible operating point. It is not ready for confirmation, clinical use, Nature-level submission or any statement that the validity contract has been validated.

The next valid gate is a prospectively locked v6 repair followed by untouched confirmation. Until that gate passes, NOSTOS remains a research prototype with explicitly developmental evidence.
