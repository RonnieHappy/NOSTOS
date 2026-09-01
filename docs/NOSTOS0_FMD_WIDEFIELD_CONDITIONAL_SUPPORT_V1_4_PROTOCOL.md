# NOSTOS-0 FMD widefield conditional-support v1.4 protocol

**State at freeze:** post-v1.3 development; v1.4 confirmation pixels unopened  
**Study type:** computation-only secondary analysis of public microscopy  
**Independent unit:** FMD field of view

## Why v1.4 exists

The v1.3 widefield profile passed every frozen pooled confirmation gate. That aggregate result was not sufficient. All seven accepted development failures occurred in the average-of-8 by 8-pixel tensor-coherence cell, and the untouched v1.3 confirmation reproduced the concentration with four failures among four accepted values in the same cell. Pooling safe average-of-16 and coarse-scale measurements around this cell concealed a deterministic subgroup failure.

V1.4 therefore tests a general hierarchical rule: a calibrated measurement may be emitted only when both the pooled profile and its declared acquisition-by-requested-scale cell were supported during development. This is a post-v1.3 repair and will never be represented as part of the v1.3 confirmation.

## Development and confirmation boundary

The eight now-open v1.3 fields (7, 15, 13, 9, 16, 17, 18 and 11) form v1.4 development. Their original rows and hashes are locked in the configuration. Four new fields (20, 14, 5 and 1) form the one-shot v1.4 confirmation. FOV 19 remains excluded because it supplied the earlier `test_mix` experiment. Seven archive fields remain unused after v1.4.

Fields and repeated captures were selected only by the frozen SHA-256 rules in the configuration. Repeated noise realizations are nested observations. Cross-fitting, bootstrap resampling and inference use the field of view as the independent unit.

## Frozen conditional-support rule

The v1.3 risk maps, primary score and threshold remain byte-identical. No error label is used during confirmation. On development only, rows that pass the base profile are stratified by:

1. declared acquisition level (`raw`, `avg2`, `avg4`, `avg8` or `avg16`); and
2. requested tensor-coherence scale (4, 8 or 16 pixels).

A cell is supported only when it contains at least eight accepted cases from at least four independent fields, observed silent-invalid risk is at most 0.10, and the field-clustered bootstrap upper 95% bound is at most 0.30. A base-accepted value in any unsupported, unsafe or unseen cell hard-abstains. The ordinary acquisition-QC comparator does not receive this gate.

## Confirmation gates

The one-shot confirmation must pass every pooled gate in the locked JSON and every supported-cell gate. In particular, coverage must remain at least 0.20; pooled observed risk must be at most 0.10; every supported cell must contain at least eight accepted values from all four fields and have observed risk at most 0.15; matched ordinary QC must emit at least five invalid values; and the field-clustered AURC-difference interval must remain above zero.

The cellwise tests are deliberate multiplicity in the safety direction: one unsafe supported cell fails the complete profile even if the pooled result passes.

## Claim boundary

A pass would show that a hierarchical, input-known support table prevented the specific pooled-subgroup failure on untouched fields from the same public widefield acquisition family. It would not establish physical calibration, biological meaning, denoising quality, population prevalence, transfer to another microscope or clinical utility.
