# NOSTOS-0 TLT pSHG-XRD transfer benchmark v1

**State:** analysis and numerical gates locked; confirmation sealed  
**Dataset:** Zenodo 10.5281/zenodo.10979115  
**Associated publication:** 10.1098/rsfs.2023.0046

## Purpose

The current principal NOSTOS validity advantage is confirmed within PSHG-TISS. This benchmark asks whether the same measurement-contract concept transfers to a separately acquired unstained collagen system and whether NOSTOS measurements recover deposited structural differences that are independently supported by polarization-resolved SHG and synchrotron X-ray scattering.

The benchmark does not assume that the same scalar has identical biological meaning in breast collagen and mineralizing tendon. It tests whether the declared structural measurement remains calibrated, stable, selectively emitted and directionally concordant with a withheld reference in the new acquisition family.

## Frozen specimen split

The experimental unit is the specimen. A deterministic SHA-256 ordering of `nostos_tlt_pshg_xrd_v1|SampleN` assigns Samples 3 and 1 to development and Samples 2 and 4 to confirmation. All three mineralization zones from a specimen remain in the same partition.

Until a locked analysis protocol is committed:

- Sample1 and Sample3 files may be downloaded and opened for schema inspection and method development.
- Sample2 and Sample4 files may be downloaded for checksum verification but their arrays may not be opened, summarized or used to select an endpoint, threshold or gate.
- XRD schema inspection is permitted to establish which reference variables exist. Its limited specimen coverage must be reported exactly.

## Development questions

1. Which deposited arrays are authentic image inputs and which are derived pSHG or XRD references?
2. Is physical pixel spacing available in the files or associated Methods?
3. Can a NOSTOS endpoint be computed from an image that does not itself contain the withheld reference?
4. Can support and abstention be determined without access to mineralization-zone labels or withheld reference values?
5. What aggregation preserves the specimen as the inferential unit?

## Candidate endpoint hierarchy

The following hierarchy is fixed before schema inspection. The first feasible endpoint is promoted; lower endpoints are used only if higher endpoints are absent or invalid.

1. Local axial-orientation error against a deposited pixelwise pSHG orientation reference, with support learned only from input-derived diagnostics.
2. Region-level organization concordance between an image-derived NOSTOS organization response and deposited pSHG `I2` values.
3. Within-specimen ordering of NM, EM and LM regions, using the publication's direction of increased collagen organization with mineralization as the reference.
4. Qualitative concordance with XRD structural direction only if XRD lacks registered or specimen-replicated measurements.

No result may be promoted merely because it is significant. The endpoint must be technically identifiable from the deposit and biologically interpretable from the associated publication.

## Comparator requirements

The locked confirmation must compare the identical eligible cases using:

- an always-emit form of the selected NOSTOS estimator;
- ordinary acquisition QC;
- a focused endpoint-QC policy;
- at least one recognized upstream or conventional orientation/texture implementation where the raw image permits it;
- the complete NOSTOS contract;
- single-component contract ablations.

Comparisons must be made at matched coverage where a selective policy is involved. Tied scores must remain tied in risk-coverage analysis.

## Perturbation requirements

If image arrays permit controlled perturbations, development may select from predeclared families already used by NOSTOS: blur, Poisson noise, contrast compression, downsampling/resampling, crop displacement and polarization-frame removal. The final protocol must specify severity values, validity references and gates before confirmation arrays are opened.

## Statistical unit and uncertainty

- Specimen is the independent biological unit.
- Zone is a repeated condition within specimen.
- Tiles or pixels may characterize a field but cannot inflate biological sample size.
- Confirmation must report every specimen and zone, not only a pooled statistic.
- With two confirmation specimens, uncertainty is descriptive or exact over the available specimen set; broad population claims are prohibited.
- Any bootstrap must resample specimens first and preserve within-specimen zones.

## Promotion gates to be frozen after development

The locked protocol must contain numerical gates for:

1. clean-input eligibility and error or reference concordance;
2. silent-invalid risk at matched coverage versus ordinary QC;
3. risk-coverage area;
4. performance of each contract ablation;
5. consistency of direction across both confirmation specimens;
6. failure attribution and abstention behavior;
7. runtime and schema conformance.

## Locked analysis after development

The development amendment records the only model-selection decisions. The estimator uses the deposited mean SHG intensity image, a `log1p` transform, a 12 µm primary integration scale, a 6 µm comparison scale and a zero-degree axial-coordinate offset. Reference `Phi2` and `I2` values are never inputs to eligibility or abstention.

The complete contract is the maximum normalized score across acquisition QC, local tensor coherence and 12-to-6 µm scale consistency. It emits a value when this score is at most 0.40. The rejected smoothed-gradient disagreement term remains an accuracy comparator but is not part of the support contract.

Sixteen conditions are fixed: clean; Gaussian blur at 1, 2, 4 and 8 pixels; additive noise at 30, 20, 10 and 5 dB; downsample-and-restore factors 2, 4 and 8; contrast factors 0.5 and 0.25; and moderate and severe compound degradations. Invalidity is fixed as field-level median axial error above 20 degrees or 75th-percentile axial error above 35 degrees against the withheld pSHG orientation map.

The confirmation succeeds only if all of the following hold:

1. exactly two sealed confirmation specimens and at least 20 fields are evaluated;
2. at least 40 programmed cases are invalid, so selective risk is assessable;
3. full-contract coverage is at least 0.40 and observed risk is at most 0.20;
4. full-contract risk is at most 0.25 within each specimen;
5. matched-coverage risk reduction is at least 0.05 versus acquisition QC and at least 0.025 versus endpoint QC;
6. full-contract tied-score risk-coverage area is lower than both comparators;
7. removal of scale consistency worsens risk-coverage area by at least 0.01;
8. at least 70% of clean fields are retained and clean median field error is at most 15 degrees;
9. the 12 µm estimator is non-inferior to the 6 µm and smoothed-gradient comparators within 2 degrees on clean fields;
10. the single-image NOSTOS coherence coordinate has pooled Spearman correlation of at least 0.50 with deposited pSHG `I2` and correlation of at least 0.50 within each confirmation specimen;
11. mutating withheld reference labels does not change any emit/withhold decision; and
12. all source checksums, output schemas and lock hashes verify.

With two confirmation specimens, bootstrap intervals are descriptive and cannot support a population-generalization claim. Every specimen-level result must be displayed.

## Claim boundary

A successful confirmation would establish a compact second-acquisition-family transfer of a declared NOSTOS structural endpoint on unstained collagen. It would not establish population generalization, tissue mechanics, diagnosis, intraoperative performance, clinical utility or universal collagen semantics. The orthogonal XRD measurements support structural interpretation only to the degree allowed by their specimen coverage and spatial registration.
