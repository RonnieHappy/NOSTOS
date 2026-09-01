# NOSTOS-0 small-pilot v5 final tool audit

**Audit date:** 29 August 2026  
**Decision:** Developmental pilot complete; proceed only to the untouched threshold-calibration partition.  
**Clinical status:** Research use only. No diagnosis, treatment decision, intraoperative decision or patient-specific interpretation is supported.

## Audit question

This audit asked whether a deliberately small experiment could expose fundamental estimator or software errors before NOSTOS processed additional public data. The experiment was not designed to establish biological generalization or clinical utility. It tested whether selected structural measurements from ordinary-resolution BioSR acquisitions agree with registered higher-resolution references, whether the validity contract ranks failures, and whether unsupported measurements are withheld rather than silently reported.

## Frozen sample

The sample contains 12 independently selected reference fields: six clathrin-coated-pit fields and six endoplasmic-reticulum fields. These fields generated 90 paired acquisitions and 1,890 endpoint cases. Four CCP acquisition pairs failed registration eligibility, leaving 86 paired acquisitions with reference comparisons. Repeated endpoint cases were never treated as independent biological specimens; risk uncertainty was clustered by reference field and stratified by structure.

The selection is fixed in `manifests/biosr_small_pilot_v5_selection_lock.json`. The complete artifact chain is fixed in `manifests/biosr_small_pilot_v5_artifact_receipt.json`. No threshold-calibration or confirmation archive was listed, extracted, decoded, summarized or visualized during this audit.

## Errors found and corrected

The small pilot exposed problems that a large run would have obscured.

1. The first spectral comparison used the same fraction of each image's Nyquist limit. Because the input and reference had different sampling grids, this compared different physical frequency bands. Version 5 applies one band in cycles per millimetre to both images.
2. Local tensor coherence had been mistaken for evidence that one global direction existed. Version 5 requires a global doubled-angle resultant, independent Fourier anisotropy and tensor–Fourier axial agreement before orientation is eligible.
3. Cross-scale variation had been used as an invalidity score even though scale dependence is part of the intended response geometry. It is now a visible diagnostic and cannot determine validity.
4. The generic measurement API had initially attached the BioSR profile to raw Hessian and variogram curves although the pilot evaluated L2-normalized curve shapes. Raw amplitudes and normalized shapes are now separate responses with separate evidence labels.
5. The acquisition profile still referenced a superseded version-4 receipt. It now resolves to the version-5 artifact receipt and final pilot audit and verifies both by size and SHA-256.
6. The generic spectral API treated spacing values as micrometres even when the declared unit was millimetres. Physical wavelength conversion is now unit-correct and is covered by a µm↔mm equivalence test.
7. A user could previously select a profile for an incompatible image. Profile application now fails closed: dimensionality, unit, spacing, analysis scales, preprocessing, spectral band and linked artifacts must match before any developmental evidence or endpoint suppression is applied.

Failed developmental versions remain documented. They were not deleted or rewritten as successes.

## Measurement result

The acquisition profile retains ten endpoint families for untouched threshold calibration:

- Hessian blob and tube curve shape.
- Fourier anisotropy and angular entropy.
- Tensor coherence and consensus-gated orientation.
- Horizontal and vertical normalized variogram curves.
- Horizontal and vertical variogram ranges.

Three scalar endpoints are disabled for this exact acquisition profile:

- Hessian blob winning scale.
- Hessian tube winning scale.
- Fourier characteristic wavelength.

The Hessian reference maxima occurred at a scale-grid boundary, so a winning scale was censored rather than identified. Fourier characteristic wavelength failed the frozen 25% relative-error tolerance in 85 of 86 reference-eligible pairs. The corresponding calibrated spectra and multiscale response curves remain available; the unsupported scalar summaries do not.

Across the retained claim endpoints, 1,142 reference-eligible cases contained 51 invalid comparisons. Every observed failure was ER tensor coherence at the two lowest signal levels. Eighteen structure-by-endpoint combinations had no observed invalid case among eligible pilot comparisons. CCP orientation appropriately had no reference-eligible case because the punctate fields lacked a coherent global direction; this is abstention, not success or failure.

## Selective-risk result

The retained-endpoint always-emit risk was 0.04466. Area under the risk–coverage curve was:

| Validity policy | AURC |
| --- | ---: |
| Full NOSTOS contract | 0.004059 |
| Conventional acquisition QC | 0.005449 |
| Perturbation stability alone | 0.013596 |
| Always emit | 0.044658 |

The full contract reduced AURC by 90.91% relative to always emitting a value. The difference from conventional acquisition QC was modest in this small developmental sample and is not evidence of a definitive advantage. That comparison must be repeated on untouched fields with cluster uncertainty.

Descriptive full-contract landmarks on development data were 0 observed risk at 79.95% coverage, 1.47% observed risk at 89.58% coverage and 3.41% observed risk at 94.92% coverage. These landmarks are not operating thresholds and cannot be carried forward as though they were confirmatory estimates.

The unresolved retained endpoint is ER tensor coherence. The contract ranks its failures well, but the convenient score boundary of one accepted all 51 invalid coherence cases. An operating threshold must therefore be selected on the untouched threshold-calibration fields; it cannot be chosen from these 12 pilot fields.

## Tool-level checks

The public `nostos measure` command was run on the arithmetic mean of the nine raw SIM phase frames for CCP Cell_001, signal level 09, at 0.0626 µm per pixel. The profile was machine-compatible. The output contained 10 developmental responses, nine unvalidated responses and three explicit profile-disabled measurements. Geometry and network endpoints abstained because no specimen mask was supplied.

The same image was then deliberately declared at 0.063 µm per pixel. The profile failed compatibility. All 22 computed responses remained unvalidated; no endpoint was suppressed using the incompatible profile. This is the intended fail-closed behavior.

Each response now carries exactly one amplitude unit, optional pointwise validity masks and reasons, and one evidence state: `unvalidated`, `developmental`, `calibrated` or `confirmed`. Profile selection cannot convert tissue interpretation or clinical validity into a software property.

## Software verification

The frozen environment completed:

- `uv run --frozen pytest -q`: 214 passed, 4 skipped, 0 failed.
- `uv run --frozen python -m compileall -q src scripts`: exit code 0.
- Compatible real-field CLI smoke test: exit code 0.
- Deliberately incompatible profile smoke test: exit code 0 with fail-closed evidence.

The 12 warnings arise from scikit-image calling the deprecated `numpy.fix` function during phase-correlation tests. They do not represent NOSTOS test failures, but dependency updates should continue to be monitored.

## Reproducibility objects

- Machine-readable audit: `outputs/nostos0-biosr-small-pilot-v5-audit/pilot_audit.json`
- Human pilot verdict: `outputs/nostos0-biosr-small-pilot-v5-audit/PILOT_VERDICT.md`
- Locked acquisition profile: `configs/biosr_widefield_measurement_profile_v1.locked.json`
- Final audit receipt: `manifests/biosr_small_pilot_v5_final_audit_receipt.json`
- Publication audit figure: `figures/nostos0/figure_small_pilot_v5_audit.svg`
- Figure provenance: `figures/nostos0/figure_small_pilot_v5_audit.manifest.json`
- Compatible CLI output: `outputs/nostos0-biosr-small-pilot-v5-audit/cli_smoke_profiled/response_geometry.json`
- Incompatible-profile control: `outputs/nostos0-biosr-small-pilot-v5-audit/cli_smoke_incompatible_profile/response_geometry.json`

The final receipt contains the path, byte count and SHA-256 for every primary audit object and records the verification commands and exit codes.

## Final decision

The small pilot achieved its purpose. It found and corrected estimator semantics, physical-band calibration, evidence-mapping, profile-lineage and unit-conversion defects before broad analysis. The current tool is suitable for research use in explicit developmental mode and is substantially safer than the pre-pilot implementation.

It is not yet a validated clinical tool, a finished high-impact paper or a confirmed acquisition-independent measurement system. The next allowed experiment is a limited run on the already frozen, untouched threshold-calibration partition. Its sole job is to choose the operating threshold and quantify selective risk and coverage with reference-field clustered uncertainty. Confirmation data must remain sealed until that threshold receipt is written and locked.
