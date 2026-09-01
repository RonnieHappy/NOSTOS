# NOSTOS-0 FMD widefield no-refit extended confirmation v1.5

**State at freeze:** seven extension fields unopened for NOSTOS measurement analysis  
**Study type:** computation-only secondary analysis of public microscopy  
**Independent unit:** field of view

## Purpose

The v1.4 conditional-support profile passed its one-shot confirmation on four untouched fields: 64 of 240 eligible primary measurements were accepted, none was invalid, and matched ordinary acquisition QC emitted 31 invalid measurements. Four fields are nevertheless too few to bound field-level recurrence tightly. With zero observed field events, the two-sided exact 95% upper bound remains 60.2%.

V1.5 is a no-refit extension. It applies the byte-identical v1.4 base risk profile, operating threshold and acquisition-by-scale support table to every FMD widefield field deliberately left unopened after v1.4. It is not another repair cycle.

## Frozen selection

The original seed and SHA-256 rules remain unchanged. FOV 19 stays excluded because it supplied the earlier `test_mix` experiment. The first twelve ranked non-excluded fields were opened during v1.3 and v1.4. The seven remaining fields are, in frozen order, FOVs 3, 12, 6, 8, 4, 2 and 10.

Four repeated realizations per field are fixed by the original realization hash rule and reused at raw, average-of-2, average-of-4, average-of-8 and average-of-16 acquisition levels. This produces 140 paired acquisitions and 420 tensor-coherence primary cases across the three requested pixel scales.

## Immutable estimator and comparators

The following objects remain byte-identical to v1.4:

1. the v1.3 measurement protocol and estimator implementation;
2. the v1.3 calibrated-risk maps and primary operating threshold;
3. the v1.4 four-cell acquisition-by-scale support table;
4. the conventional acquisition-QC comparator;
5. invalidity definitions, mild perturbations, registration gates and tie handling; and
6. the field-clustered bootstrap procedure and all inherited v1.4 gates.

No outcome label is available to the estimator or support table at application time.

## Extension and cumulative tests

The extension-only audit must contain exactly seven independent fields and pass every inherited v1.4 gate. It must emit zero invalid accepted values, no field may contain an accepted failure, and every frozen supported cell must be represented in every field.

The cumulative audit combines the four original untouched v1.4 fields with the seven v1.5 extension fields without refitting. It must contain exactly eleven independent fields, pass every inherited v1.4 gate, emit zero invalid accepted values and contain zero fields with any accepted failure. The two-sided Clopper-Pearson upper 95% bound for the field-event probability must be at most 0.30. At zero events among eleven fields this bound is approximately 0.285.

Repeated captures and endpoint rows are nested observations. The field-level event and field-clustered bootstrap are the primary uncertainty statements; row-level exact intervals are descriptive.

## Failure policy

All seven fields are analyzed once. A failed gate is retained as a failed prospective extension. No field, realization, support cell, scale, endpoint, threshold, perturbation or comparator may be removed, reweighted or repaired after decoding.

## Claim boundary

A pass would show that the frozen v1.4 contract prevented recurrence of the known unsafe subgroup across all remaining unopened fields in this archive and would reduce the exact field-level upper bound from 60.2% to below 30% cumulatively. It would not establish transfer to another instrument or modality, physical calibration, biological meaning, clinical utility or population prevalence.
