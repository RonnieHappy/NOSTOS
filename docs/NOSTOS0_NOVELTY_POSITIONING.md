# NOSTOS-0 novelty position: executable validity contracts for quantitative microscopy

## The problem NOSTOS solves

Most microscopy software answers *what value can be computed from this image?*
NOSTOS asks the prior question: *does this acquisition support this particular
measurement at this particular requested scale?* A successful function call is
not evidence that the returned number is scientifically supported. Conventional
image-quality control is also insufficient because focus, contrast or signal
statistics can be acceptable while a scale-specific structural measurement is
wrong.

NOSTOS compiles a deployable validity profile from grouped development data and
then applies it without reference labels. The deployed object combines:

1. declared measurement preconditions and hard abstentions;
2. an input-only calibrated risk score;
3. support for declared acquisition families;
4. hierarchical support cells over acquisition conditions and requested
   measurement coordinates; and
5. an immutable record of development, failures, amendments and one-shot
   confirmation.

The defining output is therefore not a classifier confidence score. It is an
auditable decision about whether a continuous scientific measurement may be
emitted under a declared acquisition and scale contract.

## Formal object

For measurement algorithm \(f_m\), image \(I\), requested coordinate \(q\), and
reference measurement \(y^*\), define

\[
y=f_m(I,q),\qquad
Z=\mathbb{1}\{L_m(y,y^*)>\epsilon_m\}.
\]

Only development data expose \(Z\). Input-visible diagnostics \(x(I,q)\) are
mapped to calibrated risk \(\hat r(x)\). A declared cell
\(c=(a,q)\), containing acquisition condition \(a\) and measurement coordinate
\(q\), enters the supported set \(\mathcal S\) only if its development evidence
passes minimum accepted-case, independent-group, observed-risk and uncertainty
gates. Deployment emits a value exactly when

\[
A(I,m,q)=
\mathbb{1}\{\text{preconditions pass}\}
\mathbb{1}\{\hat r(x)\le t\}
\mathbb{1}\{c\in\mathcal S\}.
\]

The reference value, invalidity label and confirmation outcome are forbidden
inputs to \(A\). Unsupported or unseen cells abstain rather than inherit the
pooled behavior of neighboring cells.

## Relationship to the closest prior methods

| Prior method family | What it establishes | What NOSTOS adds | What NOSTOS does **not** claim |
|---|---|---|---|
| Selective classification and reject-option prediction | A predictor can trade coverage for lower prediction risk, often by thresholding confidence | Treats a continuous microscopy measurement and its requested scale as the object of validity; preserves acquisition preconditions, independent-unit structure, cellwise support and measurement provenance | NOSTOS did not invent risk–coverage analysis or abstention |
| Risk-controlling prediction sets and Learn-then-Test | Holdout calibration can provide finite-sample or distribution-free risk control under stated assumptions | Supplies an executable microscopy-specific contract and immutable prospective failure/repair workflow | Current NOSTOS confirmations are empirical grouped validations, not distribution-free population guarantees |
| Multicalibration and subgroup calibration | Aggregate calibration can hide errors in identifiable subgroups | Compiles hard support over acquisition×measurement cells and fails the complete profile if any declared supported cell fails | The current cell table is not a general multicalibration algorithm over arbitrary overlapping groups |
| Microscope and image QC | Instrument performance, focus, illumination, noise and artifacts can be monitored | Tests whether a *specific downstream measurement* is supported and compares against ordinary acquisition QC at matched emitted-sample coverage | NOSTOS does not replace instrument calibration or facility QC |
| Radiomics and feature platforms | Large standardized families of image descriptors can be computed | Binds output values to units, requested coordinates, support, stability, evidence maturity and explicit abstention | NOSTOS does not claim that its component estimators or feature collection are universally superior |

Key antecedents are Geifman and El-Yaniv's selective-classification framework
([NeurIPS 2017](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html)),
Bates *et al.* on distribution-free risk-controlling prediction sets
([JACM 2021](https://arxiv.org/abs/2101.02703)), Angelopoulos *et al.* on
Learn-then-Test ([arXiv 2021](https://arxiv.org/abs/2110.01052)), and
Hébert-Johnson *et al.* on multicalibration
([ICML 2018](https://proceedings.mlr.press/v80/hebert-johnson18a.html)).
Microscopy context comes from QUAREP-LiMi's call for common quality-control and
metadata standards ([J. Microsc. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC10388377/)),
routine microscope-performance metrics
([J. Cell Biol. 2022](https://doi.org/10.1083/jcb.202107093)), and
problem-aware validation guidance in Metrics Reloaded
([Nature Methods 2024](https://doi.org/10.1038/s41592-023-02151-z)).

## Evidence that distinguishes the contribution from packaging

The critical result is a failure that a flat pipeline would have hidden. A
widefield-specific FMD profile passed all pooled v1.3 confirmation gates, yet
every accepted error in development and confirmation occurred in the same
average-of-8-captures by 8-pixel tensor-coherence cell. The hierarchical v1.4
compiler marked that cell unsupported using only opened development fields,
froze the complete profile, and was then evaluated once on four new FOVs.

The frozen v1.4 profile emitted 64 of 240 eligible measurements (26.7% coverage)
with zero observed errors. Matched ordinary acquisition QC emitted 31 errors
among 64 values (48.4% risk). The difference in risk–coverage area was 0.281
(FOV-clustered bootstrap 95% interval 0.187–0.416). Every supported
acquisition×scale cell passed its prespecified confirmation gate. The full
failure history, selected FOVs, archive members, decoded-pixel hashes, profile
hashes and exact decisions remain auditable.

This result is paired with the earlier BioSR v9 confirmation on eight untouched
F-actin fields: 931 of 980 tensor-coherence measurements were emitted (95.0%
coverage), with risk 0.0387 versus 0.0735 under ordinary acquisition QC, a 47.4%
relative reduction. Together, these are two bounded public-data confirmations
of the validity-contract concept on distinct acquisition resources.

## Defensible claim and explicit limit

The strongest current claim is:

> NOSTOS compiles input-only, measurement-specific validity profiles that bind
> calibrated risk to declared acquisition and measurement coordinates; in two
> public microscopy challenges, frozen profiles reduced silent-invalid
> structural measurements relative to ordinary acquisition QC, and
> hierarchical support prevented a pooled result from concealing a reproducible
> acquisition-by-scale failure.

The FMD confirmation contains only four independent FOVs. Zero observed errors
therefore do not imply zero population risk: the exact 95% upper limit is 5.6%
when the 64 nested emissions are treated descriptively and 60.2% for the
proportion of comparable FOVs with any failure. No biological, diagnostic,
clinical, intraoperative, cross-instrument or distribution-free guarantee is
claimed.

