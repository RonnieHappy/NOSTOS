# NOSTOS Prevents Silent Acquisition- and Scale-Specific Failure in Quantitative Microscopy

*Yan Jun Lin*

Department of Orthopaedic Surgery, University of Pittsburgh Medical Center, Pittsburgh, Pennsylvania, USA

Correspondence: Yan Jun Lin, Linyj2@upmc.edu

Funding: The author received no specific funding for this work.

**Keywords:** quantitative microscopy, measurement validity, selective prediction, abstention, uncertainty calibration, reproducible software

## Abstract

Quantitative microscopy software often reports a value whenever an algorithm can run, although image sampling may not support the requested measurement. NOSTOS compiles paired acquisition–reference data into input-only validity profiles for continuous measurements. On eight untouched BioSR fields, a frozen profile retained 95.0% of eligible tensor-coherence measurements while reducing silent-invalid risk from 0.0735 to 0.0387. In the Fluorescence Microscopy Denoising archive, pooled validation concealed a condition in which every emitted measurement was invalid; hierarchical support removed it on four new fields. In unstained PSHG-TISS, NOSTOS retained 7 invalid outputs versus 47 for acquisition quality control and 24 for endpoint quality control at matched 63.9% coverage. A sealed, independently acquired tendon pSHG archive then tested single-image structural recovery. Across 37 untouched fields, NOSTOS coherence from one mean SHG image correlated with withheld polarization-derived organization (Spearman ρ = 0.891; specimen values 0.904 and 0.842). Under 592 programmed cases, NOSTOS retained 2 invalid outputs among 229 versus 86 and 26 for the comparators. Preregistered coverage and clean-preservation gates were missed, so the experiment remains a qualified failure rather than a converted pass. NOSTOS makes support, abstention and failure history executable without assigning universal biological meaning.

## 1. Introduction

Microscopy has become a quantitative measurement system, but the software layer
rarely behaves like one. Structural descriptors are commonly computed after a
small set of image-level quality checks, and a successful return value is then
treated as evidence that the measurement was supported. The assumption is
unsafe. Focus, contrast and signal-to-noise can be adequate while the requested
spatial scale is undersampled, the structure is not identifiable, a
perturbation changes the endpoint or the acquisition belongs to an unsupported
family. Instrument-quality initiatives have made acquisition calibration and
metadata more visible, and image-analysis validation frameworks have clarified
the importance of task-appropriate metrics. Neither, by itself, turns a
downstream scientific measurement into an object that can refuse unsupported
input[1–4].

Selective prediction supplies the useful idea of trading coverage for lower
risk, and subgroup calibration warns that pooled performance can conceal
localized failure[5–9]. These ideas have largely been developed for class or set
prediction. Quantitative microscopy poses a different operational problem. The
output is often a continuous physical or image-domain measurement; validity can
depend simultaneously on acquisition metadata, endpoint family and the scale
or threshold at which the measurement was requested; repeated tiles, captures
and scales are nested within a field or specimen; and the deployed software
must preserve units, coordinate conventions and provenance. NOSTOS was built
to make that measurement-support decision explicit.

## 2. Results and Discussion

### 2.1. Executable validity profiles and prospective BioSR confirmation

NOSTOS separates the estimator from its validity profile. The estimator can be
any deterministic or learned algorithm that maps an image and declared
measurement coordinate to a value. The profile decides whether that value may
be emitted. Development rows pair an acquisition with a higher-support
reference and record the endpoint error, a frozen invalidity tolerance, the
highest available independent group and diagnostics available from the input
alone. An invalidity indicator is one when endpoint-specific loss exceeds the
declared tolerance. Reference eligibility is evaluated separately so an
uninformative reference cannot certify an acquisition.

For each endpoint family, the compiler maps input-only support scores to
empirical invalidity risk using quantile bins, Jeffreys smoothing and isotonic
calibration. Complete independent groups are assigned to deterministic folds;
the operating threshold is chosen only from out-of-group predictions. The
selected point maximizes emitted coverage subject to prespecified limits on
observed risk, the field- or specimen-clustered bootstrap upper bound and
minimum coverage. The serialized profile contains the calibration maps,
threshold, supported acquisition strata, development-group receipt, gates and
content hash. Confirmation is a separate command that rejects overlapping
groups or a modified profile.

**[Figure 1 near here: measurement contract, real microscopy inputs, response coordinates, compilation and fail-closed deployment.]**

The hierarchical compiler adds a second condition. Base-accepted development
rows are partitioned by declared coordinates such as acquisition modality,
capture level, endpoint family and requested scale. A cell enters the supported
set only when it contains enough accepted measurements from enough independent
groups and passes cellwise risk and uncertainty limits. At deployment, a value
is emitted only if its hard preconditions pass, its calibrated risk does not
exceed the frozen threshold and its declared cell is supported. Unseen,
underrepresented or unsafe cells abstain. One failed supported cell fails the
complete confirmation even when pooled risk passes.

This design changes the unit of interpretation. NOSTOS does not claim that high
tensor coherence, Fourier anisotropy, tubeness or network persistence has the
same biological meaning in every sample. It guarantees only that the requested
measurement, coordinate system and evidence state travel together. The
measurement engine currently exposes spectral organization, structure tensors,
scale-normalized Hessian morphology, maximal-sphere local thickness, network
erosion survival, directional variograms, bulk registration and dense
deformation through a typed response schema. These established estimators are
not the methodological novelty; they provide heterogeneous measurement objects
on which the validity machinery can operate[13–26].



**[Figure 2 near here: BioSR fields, controlled degradation, risk–coverage behavior and enrichment of rejected invalid measurements.]**

We first tested selective support on BioSR, a public collection of paired
ordinary-resolution and ground-truth structured-illumination microscopy[12]. The
development history contained several failed profiles and calibration repairs;
all remain in the evidence ledger. The final v9 confirmation used eight
untouched F-actin fields, four linear and four nonlinear, selected by a frozen
hash rule after excluding every field opened during earlier versions. Raw SIM
phase frames were averaged according to the deposited acquisition layout and
compared with the registered ground-truth SIM image. The primary endpoint was
tensor coherence at declared physical scales under fixed blur, noise,
resampling and contrast challenges. Scale and degradation measurements were
nested within field.

Among 980 eligible primary rows, ordinary acquisition QC emitted all 980 and 72
were invalid, for risk 0.0735. The frozen NOSTOS profile emitted 931 rows
(95.0% coverage), of which 36 were invalid, for risk 0.0387 and relative risk
reduction 47.4%. The field-clustered upper 95% risk estimate was 0.0513. The 49
values rejected only by NOSTOS were enriched tenfold for invalidity and carried
73.5% risk. Difference in risk–coverage area favored the complete contract by
0.00217; the stratified field-bootstrap 95% interval was
0.00092–0.00592. Risk was lower than ordinary QC in both linear and nonlinear
F-actin strata. A negative-control set of mild degradations retained complete
coverage with zero observed error, arguing against indiscriminate abstention.

The BioSR result establishes bounded selective validity for tensor coherence in
one controlled-degradation resource. It is not biological ground truth, a
super-resolution benchmark or a universal support rule. Its main role was to
show that measurement-aware input diagnostics could remove disproportionately
invalid values while preserving useful coverage.


### 2.2. Hidden FMD failure and hierarchical repair

The FMD archive offered a harder and more revealing test[10,11]. It contains
repeated real fluorescence acquisitions from commercial confocal, two-photon and
widefield microscopes. For each field, images formed from one, two, four, eight
or sixteen captures can be compared with an average-of-fifty reference. We used
the repeated captures as nested technical observations and the field of view as
the independent unit. Because pixel spacing is absent, all requested scales are
declared in pixels and no physical-scale claim is made.

**[Figure 3 near here: FMD acquisition ladder, the v1.3 conditional risk landscape, development/confirmation localization and failure-preserving repair lineage.]**

The first complete cross-modality profile passed its frozen aggregate gates.
It emitted 142 of 360 eligible primary tensor-coherence values with risk 0.141,
compared with 0.303 for matched ordinary QC. That headline was incomplete. A
post-confirmation stratified audit showed zero errors among 48 accepted confocal
and 46 accepted two-photon values, but 20 errors among 48 accepted widefield
values (risk 0.417). The profile was therefore not promoted across modalities.
This failure motivated an acquisition-specific widefield profile and a minimum
development-field requirement for every declared acquisition stratum.

The frozen widefield v1.3 profile then passed every pooled confirmation gate on
four untouched FOVs. It emitted 68 of 240 eligible values (28.3% coverage) with
four errors (risk 0.0588), versus 41 errors among 68 values for matched ordinary
QC. Yet all seven accepted development errors and all four confirmation errors
belonged to one average-of-8-captures by 8-pixel tensor-coherence cell. Within
that cell, every emitted value was wrong in both development and confirmation.
Safe average-of-16 and coarse-scale values diluted this deterministic failure
in the pooled statistic. The v1.3 pass was retained, but it was not accepted as
the terminal profile.

This sequence provides a direct empirical reason for hierarchical measurement
support. The problem was not a weak global score or an unfavorable average.
The acquisition could support some scales and capture levels but not others,
and the unsafe combination was known from input metadata. A scalar quality
decision could not represent that topology.



**[Figure 4 near here: frozen v1.4 support cells, untouched FOV decisions, matched-QC failures, risk–coverage curves and finite-sample boundary.]**

After the v1.3 result was opened, its eight development and confirmation FOVs
were explicitly relabelled as v1.4 development. The v1.3 calibrated risk maps,
score and threshold remained byte-identical. Before decoding new confirmation
pixels, we froze a conditional table over declared capture level and requested
tensor-coherence scale. A cell required at least eight accepted cases from at
least four independent FOVs, observed risk no greater than 0.10 and a
FOV-bootstrap upper 95% risk no greater than 0.30. Four cells were supported:
average-of-16 at 4, 8 and 16 pixels, and average-of-8 at 16 pixels. Eleven cells,
including the failed average-of-8 by 8-pixel cell, were unsupported and forced
to abstain.

The one-shot v1.4 confirmation used four new FOVs selected by the frozen hash
rule and four frozen repeat indices at each capture level. The hierarchical
profile emitted 64 of 240 eligible primary values (26.7% coverage) with no
observed invalid measurement. Every supported cell emitted 16 values spanning
all four FOVs and had no observed error. Matched ordinary acquisition QC emitted
31 invalid values among 64 (risk 0.484; tie-robust upper risk 0.500). The
relative risk reduction was 1.0. Risk–coverage area was 0.263 for the
hierarchical profile and 0.543 for ordinary QC; the observed difference was
0.281, with FOV-bootstrap 95% interval 0.187–0.416 and all 5,000 draws favoring
NOSTOS. All ten pooled and cellwise gates passed.

No zero-event result warrants certainty. The percentile cluster bootstrap is
identically zero when every observed FOV has zero errors and therefore cannot
serve as a population upper confidence limit. A separate exact audit gave a
two-sided Clopper–Pearson upper 95% limit of 0.056 for the 64 nested emitted
measurements and 0.602 for the proportion of comparable FOVs with any emitted
error. Each 16-value cell had an upper limit of 0.206 when its nested rows were
treated descriptively. The large FOV-level bound is the correct warning: four
independent fields provide a strong technical demonstration of the repaired
failure, but narrow evidence for population generalization.


### 2.3. Selective validity in unstained PSHG tissue

The prior studies established selective validity in fluorescence archives, but
they did not test a label-free tissue image against a physically derived local
orientation reference. We therefore used the unstained-breast forward-SHG
subset of PSHG-TISS[30]. Each region contains ten frames acquired from 0° to
180° in 20° increments, together with a polarization-fit orientation map and
fit-quality maps. The NOSTOS endpoint was the sigma-2-pixel local axial
structure-tensor direction. A 90° instrument-to-raster offset had been frozen
on a separate skin qualification subset before the breast orientation result.

The 48 breast regions were ordered by a prespecified SHA-256 rule and divided
into 24 development and 24 confirmation regions before any shifted image was
generated. Fifteen conditions were fixed: clean input; three levels each of
blur, noise and circular inter-frame motion; two resampling levels; low
contrast; and moderate and severe compound shifts. A case was invalid when its
median axial error exceeded 15° or its 75th-percentile error exceeded 30°.
Every policy used the same orientation estimator. Policies differed only in
input-known acquisition diagnostics, coherence, scale consistency and
alternating-frame consistency. The polarization reference and its fit-quality
maps were withheld from every deployment decision.

The confirmation contained 360 cases, of which 77 were invalid. At the frozen
risk threshold, the complete contract accepted 230 cases (63.9% coverage) and
retained 7 invalid outputs (3.04% risk). At the same 230-case coverage,
acquisition quality control retained 47 invalid outputs (20.43% risk), whereas
endpoint quality control retained 24 (10.43%). Absolute risk reductions were
17.39 and 7.39 percentage points, respectively. Across 5,000 region-level
bootstrap samples, the 95% intervals were 0.131–0.245 and 0.047–0.114 for the
two matched-risk differences; both risk–coverage-area intervals also excluded
zero. Clean-input coverage was 22 of 24 regions, with 7.29° median axial error.

Removing scale consistency increased risk–coverage area by 0.0521. Removing
alternating-frame consistency improved it slightly by 0.00035, so that
component is not claimed as necessary. Acquisition quality control produced no
operating point at the frozen risk cutoff; its matched-coverage comparison is a
stable score ranking, not a deployable threshold. A separate audit
implementation verified all 312 confirmation source files and exactly
reconstructed the split, scores, decisions, summaries and 5,000 bootstraps.
This result demonstrates selective validity under programmed shifts in one
deposited PSHG acquisition family, not independent-microscope transfer or
native clinical degradation.

**[Figure 5 near here: unstained PSHG acquisition-shift challenge, local orientation reference, selective-risk comparison and region-level uncertainty.]**


### 2.4. Single-image structural recovery in independent tendon pSHG

We next asked whether the orientation contract and an interpretable structural coordinate transferred beyond PSHG-TISS. A separate public study deposited mean SHG intensity, polarization-derived orientation (φ₂) and organization (I₂) maps from non-mineralizing, early-mineralizing and late-mineralizing turkey leg tendon, together with synchrotron X-ray measurements of collagen hierarchy[31,32]. Each 512 × 512-pixel field spans 384.5 × 384.5 µm. Only the mean SHG intensity image entered NOSTOS; φ₂, I₂, zone identity and X-ray measurements were unavailable to the support decision.

**[Figure 6 near here: authentic tendon SHG, NOSTOS and pSHG maps, organization recovery, matched invalid outputs and tied-score risk–coverage curves.]**

The four specimens were separated before array inspection by a deterministic SHA-256 rule. Samples 1 and 3 supplied 36 development fields, while Samples 2 and 4 remained sealed. Development selected a log-intensity transform, a 12 µm primary tensor scale, a 6 µm scale-consistency comparator and zero coordinate offset. An initial smoothed-gradient disagreement component worsened development risk–coverage area and was rejected before confirmation. The locked contract retained acquisition QC, local coherence and physical-scale consistency. Sixteen clean and programmed blur, noise, resampling, contrast and compound conditions were fixed. A field-condition case was invalid when its median axial error exceeded 20° or its 75th-percentile error exceeded 35°.

The sealed confirmation contained 37 fields and 592 cases, of which 273 were invalid. The contract accepted 229 cases and retained 2 invalid outputs (0.87% risk). At the nearest complete tied-score groups with the same 229 cases, acquisition QC retained 86 invalid outputs (37.55%) and endpoint QC retained 26 (11.35%). Absolute risk reductions were 36.68 and 10.48 percentage points. Specimen-bootstrap intervals were 18.35–47.50 and 5.83–10.48 percentage points; with two independent specimens these are descriptive, not population inference. Tied-score risk–coverage areas were 0.4004, 0.1845 and 0.1607, respectively. Removing scale consistency worsened area by 0.0238.

The clean images supplied a second, distinct test. NOSTOS median coherence from one mean SHG image correlated with the withheld polarization-derived I₂ organization value across 37 fields (Spearman ρ = 0.891). Correlations were 0.904 and 0.842 in the two sealed specimens. Mean coherence increased from 0.287 in non-mineralizing Sample2 fields to 0.609 and 0.708 in early- and late-mineralizing fields; Sample4 values were 0.421, 0.446 and 0.734. Deposited I₂ changed in the same direction. Thus a scale-declared single-image coordinate recovered substantial information normally derived from a twelve-angle polarization series.

The experiment did not pass every preregistered gate. Coverage was 38.68%, below the frozen 40% requirement, and 59.46% of clean fields were retained, below the 70% requirement. Accepted clean fields nevertheless had 12.12° median field error, and full-contract risk was 1.67% in Sample2 and zero in Sample4. No threshold was changed after unsealing. An independent code path reconstructed all decisions, tied-score analyses, organization correlations and 5,000 specimen bootstraps; 22 of 22 audit checks passed. The result is therefore a qualified second-acquisition-family confirmation: strong measurement and selective-risk evidence accompanied by explicit deployment coverage failure, not a validated replacement for pSHG.





The generic interface exposes separate commands for profile compilation,
confirmation audit, hierarchical compilation and hierarchical confirmation.
The latter automatically writes exact finite-sample intervals in addition to
the frozen audit and row-level decisions. A terminal independent code-path
audit reproduced the FMD field and realization selections, checked all archive
member hashes, verified unique row identities and formulae, reapplied the
serialized profile exactly and demonstrated reference-label blindness by
mutating reference errors without changing deployment decisions. All 17 checks
passed. The evidence bundle indexes every required receipt with a checksum and no missing entry.

The FMD programme also preserves the steps that did not work: a metadata
failure before endpoint analysis, a performance abort before row export, a
development profile with no operating point, the cross-modality pooled pass
with widefield failure and the v1.3 pooled pass with a scale-specific failure.
A reporting-only label amendment is stored separately and did not recompute a
statistic or change a gate. This immutable lineage is not incidental
bookkeeping. It prevents the final profile from appearing to have been designed
before the failures that motivated it.

NOSTOS remains a broader measurement engine, and supplementary validations
exercise its component estimators. Twenty-four analytic module–perturbation
tests passed their declared operating envelopes. On supplied reference masks,
network erosion survival and skeleton length agreed across sampling in 20 STARE
images (Spearman correlations 0.988 and 0.995). In eight public trabecular-bone
volumes, local thickness agreed with archived maps and BoneJ (median voxelwise
Spearman correlation 0.927; concordance correlation coefficient 0.926).
Programmed dense deformation and continuation tracking have separate bounded
tests. Negative results—including failed universal response concatenation,
failed global Fourier transfer, failed automatic vessel proposals and failed
division inference—remain visible. These studies establish implementation
breadth and claim discipline; they are not pooled into a universal score.


NOSTOS addresses a simple but neglected distinction: computation is not
measurement validity. It turns support for a requested microscopy measurement
into a versioned object that can be compiled, frozen, audited and applied
without access to reference labels. Its principal contribution is the
composition of input-only calibrated risk with acquisition and measurement
coordinates, grouped validation and fail-closed behavior. The FMD sequence
shows why this composition matters. A conventional pooled analysis passed twice
while first hiding an acquisition-family failure and then a deterministic
acquisition-by-scale failure. Hierarchical support made the failure explicit and prevented its recurrence in the untouched confirmation. The PSHG-TISS challenge then tested the same governing idea on unstained tissue: a physically adjudicated local orientation field failed under controlled acquisition shifts, and an input-only contract removed most invalid outputs without inspecting the reference. A sealed tendon resource extended the test to a separately acquired pSHG family and a tangible structural endpoint. One mean SHG image recovered polarization-derived collagen organization in both untouched specimens, while the same contract sharply reduced invalid orientation outputs. The missed coverage gates remain equally important: they delimit deployment even when accepted-case accuracy is excellent.

NOSTOS is related to selective prediction but does not claim to have invented
abstention or risk–coverage analysis. It differs in the object being governed:
a continuous structural measurement whose validity depends on declared units,
acquisition conditions and requested coordinates. It is also related to
multicalibration, but the current support table is not a general algorithm over
arbitrary overlapping subgroups. It implements a deliberately finite hierarchy
chosen from scientifically interpretable acquisition and measurement
coordinates. Risk-controlling prediction sets and Learn-then-Test provide
stronger finite-sample guarantees under their assumptions. The present
profiles use prespecified empirical gates, grouped bootstrap inference and exact
descriptive intervals; they are not distribution-free guarantees.

The evidence has important limits. BioSR, FMD and PSHG-TISS are public archives with their own reference constructions. FMD v1.4 contains only four independent
confirmation FOVs, all from one widefield sample/acquisition family. The
average-of-fifty image is a high-support computational reference, not noiseless
truth. Pixel spacing is unavailable. The FMD score uses declared capture count,
which must be known at deployment. Ordinary acquisition QC is a matched
internal comparator, not every possible external QC system. The PSHG-TISS result uses programmed shifts in one microscope family. The tendon resource is independently acquired and provides a second pSHG family, but confirmation contains only two specimens and its degradations are still computational. The tendon contract missed its frozen coverage and clean-preservation gates. The organization correlation is therefore evidence that a single-image coordinate contains polarization-related structural information, not proof that NOSTOS can replace pSHG, infer mechanics or generalize to an unseen instrument population. These boundaries are stated in the serialized profiles and must travel with every output.

The claim evaluated here is computational: measurement validity on paired
public data. The present work does not establish biological interpretation,
diagnosis, mechanics, clinical usefulness or intraoperative performance, and
none should be inferred from software correctness or rapid post-acquisition
runtime.

The immediate value of NOSTOS is practical. A method developer can adapt any
paired acquisition/reference resource to a small JSONL evidence contract,
compile a profile with independent groups intact and distribute the measurement
algorithm together with its validity object. A user receives a value, its
coordinate system, its evidence maturity and a reason when the method abstains.
That workflow makes hidden support assumptions reviewable and makes negative
results part of the software rather than an unpublished prelude to it.

## 3. Conclusion

NOSTOS makes the validity of a requested quantitative microscopy measurement an executable, versioned decision rather than an assumption. Across four public resources, the framework reduced silent-invalid outputs, exposed a pooled pass that concealed deterministic subgroup failure, removed that failure on untouched fields and transferred a scale-declared structural measurement across two unstained pSHG acquisition families. In the second family, a single SHG intensity image recovered polarization-derived collagen organization while the preregistered coverage miss remained visible. NOSTOS is therefore a practical fail-closed measurement layer, bounded to the acquisitions, instruments and coordinates on which each profile was established.

## 4. Experimental Section

### 4.1. Software implementation and response schema

NOSTOS 0.3.0 is implemented in Python 3.12 or newer using NumPy, SciPy,
scikit-image and scikit-learn[23–26]. Core dependencies are locked with uv. Each
response records module, measurement, axes, units, optional direction, values,
stability statistics, validity state, abstention reasons, input identity,
configuration identity and software provenance. Physical scales are permitted
only when pixel or voxel spacing is supplied. Otherwise, endpoints are
explicitly pixel-relative or abstain.

The release is CPU-first. Optional GPU segmentation environments are isolated
and are not required for either validity confirmation. The release builder
allowlists source, configurations, compact receipts and figure assets; excludes
bulk public microscopy; scans staged text for credentials and private absolute
paths; and writes a SHA-256 manifest for every file and for the deterministic
archive.

### 4.2. Evidence-row contract and invalidity

One JSONL row represents one endpoint comparison from a paired acquisition and
reference. Required fields are a unique case identifier, independent reference
group, endpoint family, pair-registration eligibility, reference eligibility,
frozen invalidity indicator, input-only score dictionary and input-only hard
abstention reasons. Rows may retain measurements, errors, tolerances and
reference diagnostics for audit, but those fields are not accessible to the
deployed decision.

For endpoint family m, acquisition image I, requested coordinate q, estimator
f_m and reference value y*, the reported value is y = f_m(I,q). The binary
invalidity label is Z = 1 when the prespecified endpoint loss L_m(y,y*) exceeds
tolerance epsilon_m. Tensor orientation uses axial circular error; tensor
coherence and spectral summaries use absolute error; thickness and scale use
declared physical or relative errors. Reference eligibility is endpoint
specific and is applied before calibration.

### 4.3. Base-profile compilation

Rows eligible for calibration require both valid pairing and an eligible
reference. Complete independent groups are assigned to deterministic,
stratified folds using SHA-256 ordering. The number of folds is the smaller of
the configured maximum and the number of independent groups available to an
endpoint family, with at least two groups required. Within each training fold,
scores are quantile binned, bin risks receive a Beta(0.5,0.5) Jeffreys
adjustment and isotonic regression enforces monotonic risk. Each held-out group
receives predictions from a map that did not use that group. A final map for
deployment is fit to all development groups only after out-of-group operating
point selection.

Candidate scores share identical folds. A score-specific hard-gate policy
prevents comparators from inheriting NOSTOS preconditions. The primary
threshold maximizes coverage among out-of-group predictions satisfying the
configured observed-risk, clustered upper-risk and minimum-coverage criteria.
If no threshold qualifies, the compiler writes a failure audit and no
deployable operating point. Supported acquisition strata must contain the
configured minimum number of independent development groups; unseen or
underrepresented strata hard-abstain.

### 4.4. Hierarchical conditional support

The conditional compiler consumes an immutable base profile and development
rows already scored by that profile. Cell dimensions are declared in the
protocol and may draw from acquisition metadata or requested measurement
coordinates. The FMD v1.4 dimensions were capture level and requested tensor
scale. A cell was supported when it contained at least eight base-accepted rows
from at least four FOVs, observed risk at most 0.10 and a FOV-bootstrap upper
95% risk at most 0.30. These values were frozen before v1.4 confirmation.

The deployed acceptance indicator is the conjunction of three input-known
conditions: no hard abstention, calibrated risk at or below the frozen base
threshold and membership in the supported-cell set. A missing cell coordinate,
an unseen cell or an unsupported cell produces an explicit abstention. Cell
support is not given to the ordinary acquisition-QC comparator.

### 4.5. Confirmation statistics

Confirmation first verifies profile schema and content hash, source receipts
and disjoint independent groups. Primary coverage is the number emitted divided
by eligible rows. Selective risk is the fraction of emitted rows whose frozen
invalidity label is one. Ordinary acquisition QC is ranked independently and
truncated to the same emitted count; deterministic case-ID ordering resolves a
boundary tie, and best- and worst-case invalid counts within the tie are also
reported.

Risk–coverage area is computed by ordering eligible rows by calibrated risk and
integrating cumulative empirical risk over coverage. Differences are defined
as ordinary-QC area minus NOSTOS area, so positive values favor NOSTOS.
Bootstrap inference resamples complete independent groups, stratified where
declared. Repeated captures, scales, perturbations and endpoints never enter a
bootstrap as independent samples.

Percentile cluster bootstrap cannot produce a nonzero upper limit after zero
events in every observed group. The confirmation interface therefore also
reports exact two-sided Clopper–Pearson intervals for emitted rows and for the
proportion of independent groups with at least one failure. The row interval is
descriptive because rows are nested; the group-any-failure interval states the
independent-unit limitation directly[27].

### 4.6. BioSR v9 confirmation

BioSR version 9 was obtained from Figshare record 13264793. F-actin linear and
nonlinear archives were checksum locked. After excluding every cell used by
earlier development, four fields per structure were selected by frozen SHA-256
ordering. Nine raw SIM phase frames were arithmetically averaged where required
by the deposited layout. Reference construction, MRC header spacing,
registration, scale grid, degradation definitions, tensor implementation,
error tolerance, score and threshold were frozen in the versioned protocol.

The primary family was tensor coherence. There were 980 reference-eligible rows
from eight fields under the primary degradation set and 210 rows under mild
negative-control degradations. The independent unit was the field; degradation,
signal level and requested scale were nested. The confirmation was executed
once. A separate audit rehashed the complete archives and 27 locked artifacts,
recomputed all 2,240 endpoint rows and reproduced every gate.

### 4.7. FMD source and selection

The FMD dataset was obtained from the University of Notre Dame repository (DOI
10.7274/r0-ed2r-4052). The analyzed archive was
`WideField_BPAE_R.tar` (709,232,640 bytes; MD5
`e02b07bc4cfcd19dc911bd9d0c4e65a0`; SHA-256
`4914cd7d951b4ddc1a01f6c7f121b7e9936fd2a7d1505f3e802984ffee69cad7`).
The tar central directory was indexed without bulk extraction. Selected member
payloads were hashed before image decoding.

FOV 19 was excluded because it had supplied an earlier exploratory subset.
Remaining FOV identifiers were sorted by SHA-256 of a frozen seed, archive name
and FOV identifier. V1.3 used fields 7, 15, 13 and 9 for development and fields
16, 17, 18 and 11 for confirmation. After v1.3 was opened, all eight became
explicit v1.4 development. V1.4 confirmation fields 20, 14, 5 and 1 were next in
the frozen order and remained unopened until the conditional profile and
artifact lock were written. Seven FOVs remain unused.

Within each selected FOV, realization indices 0–49 were ordered by a second
frozen SHA-256 rule and the first four were used at every acquisition level.
Each split therefore contained four FOVs × four realizations × five capture
levels = 80 paired acquisitions. Every pair was evaluated at 4, 8 and 16 pixels
for tensor orientation, tensor coherence, spectral anisotropy and spectral
entropy, producing 640 endpoint rows per split before reference eligibility.
The primary family was tensor coherence.

### 4.8. FMD measurement and score

The input levels were raw, average-of-2, average-of-4, average-of-8 and
average-of-16; `avg50.png` was the reference. The primary input-only score was a
declared capture-stability contract: max(0, sqrt(16/n) − 1) plus measured
perturbation instability, where n is the declared number of independent
captures in the analyzed average. Capture count is therefore a deployment
precondition, not an inferred tissue attribute. The v1.3 base threshold was
0.6303073201.

Reference orientation was eligible only with sufficient resultant and spectral
anisotropy, agreement between estimators and stable reference probes. Tensor
coherence was invalid when absolute error relative to avg50 exceeded 0.15.
Pixel calibration was unavailable, so the 4-, 8- and 16-pixel coordinates must
not be converted to micrometres.

### 4.9. PSHG acquisition-shift confirmation

PSHG-TISS was obtained from OSF record UDTQP[30]. The analyzed subset comprised
all 48 unstained-breast forward-SHG regions. Each 512 × 512-pixel field spans
125 × 125 µm and contains ten polarization frames. Reference support required
finite polarization orientation and fit diagnostics, coefficient of
determination at least 0.90, signal-to-noise ratio at least 3 dB, positive mean
FSHG intensity and an eight-pixel edge exclusion. These quantities were used
only to define adjudicable reference pixels, never to accept an output.

Regions were ordered by SHA-256 of the fixed salt and region name; the first 24
formed development and the remaining 24 confirmation. Perturbations were
applied in the frozen order blur, inter-frame motion, downsample-and-restore,
contrast and additive Gaussian noise. Noise seeds were derived from the frozen
seed, region, condition and frame. The primary estimator was the local
structure tensor at sigma 2 pixels. Comparators were the identical estimator
with acquisition QC only or with acquisition QC plus coherence, and upstream
sigma-4 tensor and smoothed-gradient estimators on clean images.

Development used four region-grouped folds, six quantile bins, Jeffreys
adjustment and monotone isotonic calibration. The complete raw support score
was the maximum of acquisition-QC, minimum-coherence, sigma-2-to-sigma-4
disagreement and alternating-frame disagreement components. The common
operating cutoff was calibrated risk at most 0.15. Confirmation compared
policies at their frozen threshold and at the exact complete-contract accepted
count. Risk–coverage area grouped tied scores. Percentile intervals resampled
the 24 regions with replacement for 5,000 draws. The independent audit did not
import the confirmation summary functions; it rehashed all artifacts and
source files, reconstructed every score and decision with independent
interpolation and repeated the bootstrap from the frozen seed.

### 4.10. Tendon pSHG-XRD transfer

The tendon resource and associated study are available at Zenodo DOI 10.5281/zenodo.10979115 and publication DOI 10.1098/rsfs.2023.0046[31,32]. Four specimens contain aligned 512 × 512-pixel mean SHG, thresholded φ₂ orientation and thresholded I₂ organization maps from three mineralization zones. The field of view gives 0.75098 µm pixel spacing. SHA-256 ordering of specimen identity under the fixed salt assigned Samples 3 and 1 to development and Samples 2 and 4 to confirmation. All zones and fields from a specimen remained together. Repository byte counts and MD5 checksums were verified before opening confirmation arrays.

The single-image estimator applied `log1p` to nonnegative SHG intensity and computed local axial structure tensors at 12 and 6 µm integration scales. A 16-pixel edge was excluded. Input support was defined from finite intensity and the twentieth percentile of positive pixels; at least 10,000 pixels were required. Deposited finite φ₂ pixels defined adjudicable reference support only and never entered eligibility. The full support score was the maximum of normalized acquisition-QC, minimum-coherence and interscale-disagreement components, with an emission cutoff of 0.40.

The 16 conditions were clean input; Gaussian blur at 1, 2, 4 and 8 pixels; additive noise at 30, 20, 10 and 5 dB; downsample-and-restore factors 2, 4 and 8; contrast factors 0.5 and 0.25; and moderate and severe compound degradations. Noise seeds were derived from field identity, condition and the frozen seed. Comparators used the identical orientation estimator with acquisition QC alone or acquisition QC plus coherence. Matching retained complete tied-score groups nearest to the full-contract count. Risk–coverage curves never split ties.

Organization recovery was evaluated once on clean confirmation fields. NOSTOS median local coherence was calculated on input-derived support, whereas mean deposited I₂ was calculated independently on finite reference support. Spearman correlation was evaluated pooled and separately in each specimen. Bootstrap draws resampled the two specimens with all nested fields and conditions retained. Because the independent sample count is two, these intervals are explicitly descriptive. The hash lock froze 12 gates, including coverage, matched risk reduction, scale ablation, clean preservation, within-specimen risk, organization correlation and label blindness, before the six confirmation files were downloaded. The independent audit reimplemented source verification, invalidity, policy scores, tied selection, risk–coverage area, correlation and bootstrap calculations without importing the production summary functions.

### 4.11. Failure lineage and terminal audit

Every protocol revision has a distinct identifier and output directory.
Existing results are never overwritten. Confirmation locks record configuration
and code hashes, profile identities, selected sources and artifact hashes. The
v1.4 terminal audit used a code path separate from the analysis scripts to
reproduce selection, check development–confirmation disjointness, verify row
counts and uniqueness, re-evaluate scores, reapply the profile and compare all
decisions. It also toggled reference-only invalidity and error fields and
verified unchanged deployment decisions. Seventeen of seventeen checks passed.

### 4.12. Synthetic and supplementary estimator validation

Analytic constructs encode programmed orientation, wavelength, blob, tube and
sheet morphology, local thickness, roughness, network structure and directional
spatial correlation. Registered perturbations include rotation, resampling,
crop, blur, noise, contrast, anisotropic point-spread function, partial volume
and mask error. Twenty-four required module tests and their tolerances were
frozen before execution; mask-error experiments were treated as sensitivities,
not invariance claims. External supplementary comparisons use public STARE
reference masks, trabecular-bone volumes with archived thickness maps, BBBC
time series and isolated upstream software environments. The independent image
or volume is used for uncertainty[20,28,29].

## Data Availability Statement

All microscopy data remain in their originating public repositories. FMD is available under CC BY-SA 4.0 at DOI 10.7274/r0-ed2r-4052; BioSR is available at DOI 10.6084/m9.figshare.13264793; PSHG-TISS is available at DOI 10.17605/OSF.IO/UDTQP; the tendon pSHG-XRD resource is available under CC BY 4.0 at DOI 10.5281/zenodo.10979115. Dataset identifiers, licences, archive and member hashes, frozen selection rules and exact commands are included in the software evidence record. Source code is publicly available at https://github.com/RonnieHappy/NOSTOS under the BSD 3-Clause License. A versioned archival DOI will be added to the accepted manuscript when the submission snapshot is deposited.

## Author Contributions

Yan Jun Lin conceived the framework, implemented the software and analyses, curated the evidence record, interpreted the results, generated the figures and wrote the manuscript.

## Acknowledgements

Generative AI systems, including OpenAI Codex and Anthropic Claude Code, assisted with code review, statistical-script checks, deterministic figure-generation code, citation verification and language editing. No generated microscopy, biological observation or numerical result appears in the manuscript. All microscopy, maps, plots, numerical labels and statistics derive from the cited public resources and checksum-locked deterministic code. BioRender was used only to explore data-free workflow layouts; those exploratory panels are not present in the final main figures. The author verified the executable results and final text and accepts full responsibility for the work.

## Conflict of Interest

The author declares no conflict of interest.

## Funding

The author received no specific grant funding for this work.

## Ethics Statement

This study is a secondary computational analysis of public de-identified images and analytic data. No participants, specimens or new acquisitions were added.

## Figure legends

**Figure 1. NOSTOS separates computation from measurement validity.** **a,** Authentic BioSR and FMD microscopy, the paired BioSR reference, deterministic orientation fields and Fourier power. FMD remains pixel-relative because spacing is unavailable. **b,** An authentic FMD image and its deterministic orientation field pass through the frozen acquisition-by-scale support lattice to an emit or abstain decision. **c,** BioSR tensor-coherence response across declared physical scales. **d,** Frozen FMD acquisition-by-scale support; white circles denote supported cells and crosses unsupported cells. **e,** Output states. Every biological pixel originates in the cited public archives; every map and summary is deterministic.

**Figure 2. Selective support lowers silent-invalid risk in untouched BioSR fields.** **a,** A paired F-actin reference and ordinary-resolution input, their deterministic orientation field, and a controlled blur challenge. **b,** Valid emissions, invalid emissions and abstentions across the frozen perturbation panel. **c,** Invalid-emission risk paired by each of eight independent fields under acquisition quality control and NOSTOS. **d,** Tied-score risk–coverage curves; 36 of the 49 measurements rejected only by NOSTOS were invalid. Perturbations, scales and signal levels remain nested within fields.

**Figure 3. Pooled validation conceals a deterministic acquisition-by-scale failure.** **a,** One FMD field across increasing capture averages and the average-of-50 reference. **b,** Development localization: every emitted average-of-8 by 8-pixel tensor-coherence measurement was invalid, whereas supported average-of-16 cells had no observed error. **c,** The same failure recurred on untouched confirmation fields. **d,** The data-bearing repair sequence: pooled support emitted 68 of 240 measurements, stratification isolated four invalid outputs in four attempts, and the frozen repair abstained from that unsafe cell. All numbers are frozen audit results.

**Figure 4. Frozen hierarchical support prevents recurrence on new fields.** **a,** Average-of-16 images from the four untouched confirmation fields. **b,** Development-only support lattice. **c,** Each supported capture-by-scale cell emitted four measurements in each field. **d,** At matched coverage, acquisition quality control emitted 31 invalid values among 64; NOSTOS emitted none. **e,** Risk–coverage curves. **f,** Field-bootstrap difference in risk–coverage area, acquisition quality control minus NOSTOS, with the 95% interval. **g,** Exact two-sided 95% upper limits for 64 nested measurements and four independent field-level any-failure events.

**Figure 5. A frozen input-only contract lowers silently invalid orientation outputs in unstained PSHG tissue.** **a,** Authentic clean forward-SHG, the severe compound shift, the deterministic NOSTOS local axial orientation field and the withheld polarization-derived reference for the first region in the frozen confirmation lock. **b,** Condition-by-policy acceptance; circle area encodes coverage, fill encodes invalidity among accepted cases and crosses denote no accepted cases. **c,** Tied-score risk-coverage curves. **d,** Invalid outputs among the same 230 accepted cases: 47 for acquisition quality control, 24 for endpoint quality control and 7 for NOSTOS. **e,** Region-bootstrap differences for matched risk and risk-coverage area; positive values favor NOSTOS. Conditions are nested within 24 independent regions.

**Figure 6. A single SHG image recovers polarization-derived collagen structure in a sealed second acquisition family.** **a,** Deposited mean SHG intensity from the SHA-256-first confirmation field; the scale bar is 100 µm. **b,** NOSTOS 12 µm local axial orientation from that single image. **c,** Withheld pSHG φ₂ orientation. **d,** Pixelwise axial error on common support. **e,** NOSTOS local coherence. **f,** Withheld pSHG I₂ organization. **g,** Field-level NOSTOS coherence versus pSHG I₂ across all 37 untouched clean fields; colors denote mineralization zones and marker shapes denote the two specimens. **h,** Invalid outputs among complete tied-score groups nearest to the same 229 accepted cases: 86 for acquisition quality control, 26 for endpoint quality control and 2 for NOSTOS. **i,** Tied-score risk–coverage curves over 592 programmed cases; the vertical line marks NOSTOS coverage. The preregistered overall status remains fail because coverage was 38.68% versus the 40% gate and clean-field retention was 59.46% versus the 70% gate.

## References

1. Nelson, G. et al. QUAREP-LiMi: a community-driven initiative to establish guidelines for quality assessment and reproducibility for instruments and images in light microscopy. *J. Microsc.* **284**, 56–73 (2021). https://doi.org/10.1111/jmi.13041
2. Faklaris, O. et al. Quality assessment in light microscopy for routine use through simple tools and robust metrics. *J. Cell Biol.* **221**, e202107093 (2022). https://doi.org/10.1083/jcb.202107093
3. Bray, M.-A. & Carpenter, A. E. Quality control for high-throughput imaging experiments using machine learning in CellProfiler. *Methods Mol. Biol.* **1683**, 89–112 (2018). https://doi.org/10.1007/978-1-4939-7357-6_7
4. Maier-Hein, L. et al. Metrics reloaded: recommendations for image analysis validation. *Nat. Methods* **21**, 195–212 (2024). https://doi.org/10.1038/s41592-023-02151-z
5. Geifman, Y. & El-Yaniv, R. Selective classification for deep neural networks. *Adv. Neural Inf. Process. Syst.* **30** (2017). https://arxiv.org/abs/1705.08500
6. Geifman, Y. & El-Yaniv, R. SelectiveNet: a deep neural network with an integrated reject option. *Proc. Mach. Learn. Res.* **97**, 2151–2159 (2019). https://proceedings.mlr.press/v97/geifman19a.html
7. Bates, S., Angelopoulos, A. N., Lei, L., Malik, J. & Jordan, M. I. Distribution-free, risk-controlling prediction sets. *J. ACM* **68**, 43 (2021). https://doi.org/10.1145/3478535
8. Angelopoulos, A. N., Bates, S., Candès, E. J., Jordan, M. I. & Lei, L. Learn then Test: calibrating predictive algorithms to achieve risk control. https://arxiv.org/abs/2110.01052 (2021).
9. Hébert-Johnson, U., Kim, M. P., Reingold, O. & Rothblum, G. Multicalibration: calibration for the computationally-identifiable masses. *Proc. Mach. Learn. Res.* **80**, 1939–1948 (2018). https://proceedings.mlr.press/v80/hebert-johnson18a.html
10. Zhang, Y. et al. A Poisson-Gaussian denoising dataset with real fluorescence microscopy images. *Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit.*, 11710–11718 (2019). https://arxiv.org/abs/1812.10366
11. Howard, S., Mannam, V., Zhang, Y. & Zhu, Y. Fluorescence Microscopy Denoising (FMD) dataset. University of Notre Dame (2020). https://doi.org/10.7274/r0-ed2r-4052
12. Qiao, C. et al. Evaluation and development of deep neural networks for image super-resolution in optical microscopy. *Nat. Methods* **18**, 194–202 (2021). https://doi.org/10.1038/s41592-020-01048-5
13. Zwanenburg, A. et al. The Image Biomarker Standardization Initiative. *Radiology* **295**, 328–338 (2020). https://doi.org/10.1148/radiol.2020191145
14. van Griethuysen, J. J. M. et al. Computational radiomics system to decode the radiographic phenotype. *Cancer Res.* **77**, e104–e107 (2017). https://doi.org/10.1158/0008-5472.CAN-17-0339
15. Carpenter, A. E. et al. CellProfiler: image analysis software for identifying and quantifying cell phenotypes. *Genome Biol.* **7**, R100 (2006). https://doi.org/10.1186/gb-2006-7-10-r100
16. Schneider, C. A., Rasband, W. S. & Eliceiri, K. W. NIH Image to ImageJ: 25 years of image analysis. *Nat. Methods* **9**, 671–675 (2012). https://doi.org/10.1038/nmeth.2089
17. Frangi, A. F., Niessen, W. J., Vincken, K. L. & Viergever, M. A. Multiscale vessel enhancement filtering. In *Medical Image Computing and Computer-Assisted Intervention*, 130–137 (1998). https://doi.org/10.1007/BFb0056195
18. Sato, Y. et al. Three-dimensional multi-scale line filter for segmentation and visualization of curvilinear structures in medical images. *Med. Image Anal.* **2**, 143–168 (1998). https://doi.org/10.1016/S1361-8415(98)80009-1
19. Hildebrand, T. & Rüegsegger, P. A new method for the model-independent assessment of thickness in three-dimensional images. *J. Microsc.* **185**, 67–75 (1997). https://doi.org/10.1046/j.1365-2818.1997.1340694.x
20. Doube, M. et al. BoneJ: free and extensible bone image analysis in ImageJ. *Bone* **47**, 1076–1079 (2010). https://doi.org/10.1016/j.bone.2010.08.023
21. Mallat, S. Group invariant scattering. *Commun. Pure Appl. Math.* **65**, 1331–1398 (2012). https://doi.org/10.1002/cpa.21413
22. Andreux, M. et al. Kymatio: scattering transforms in Python. *J. Mach. Learn. Res.* **21**, 1–6 (2020). http://jmlr.org/papers/v21/19-047.html
23. Harris, C. R. et al. Array programming with NumPy. *Nature* **585**, 357–362 (2020). https://doi.org/10.1038/s41586-020-2649-2
24. Virtanen, P. et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. *Nat. Methods* **17**, 261–272 (2020). https://doi.org/10.1038/s41592-019-0686-2
25. van der Walt, S. et al. scikit-image: image processing in Python. *PeerJ* **2**, e453 (2014). https://doi.org/10.7717/peerj.453
26. Pedregosa, F. et al. Scikit-learn: machine learning in Python. *J. Mach. Learn. Res.* **12**, 2825–2830 (2011). https://jmlr.org/papers/v12/pedregosa11a.html
27. Clopper, C. J. & Pearson, E. S. The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika* **26**, 404–413 (1934). https://doi.org/10.1093/biomet/26.4.404
28. Ljosa, V., Sokolnicki, K. L. & Carpenter, A. E. Annotated high-throughput microscopy image sets for validation. *Nat. Methods* **9**, 637 (2012). https://doi.org/10.1038/nmeth.2083
29. Maška, M. et al. The Cell Tracking Challenge: 10 years of objective benchmarking. *Nat. Methods* **20**, 1010–1020 (2023). https://doi.org/10.1038/s41592-023-01879-y
30. Hristu, R. et al. PSHG-TISS: a collection of polarization-resolved second harmonic generation microscopy images of fixed tissues. *Sci. Data* **9**, 376 (2022). https://doi.org/10.1038/s41597-022-01477-1
31. Zheng, K. et al. Effects of mineralization on the hierarchical organization of collagen—a synchrotron X-ray scattering and polarized second harmonic generation study. *Interface Focus* **14**, 20230046 (2024). https://doi.org/10.1098/rsfs.2023.0046
32. Zheng, K. Raw data of journal paper of Effects of Mineralisation on the Hierarchical Organisation of Collagen—a Synchrotron X-ray Scattering and Polarised Second Harmonic Generation Study. Zenodo (2024). https://doi.org/10.5281/zenodo.10979115

## Supporting Information

Supporting Information accompanies this article as a separate editable document and contains the extended validation tables, perturbation definitions, audit receipts and supplementary figures.

## Table of Contents

NOSTOS turns quantitative microscopy outputs into measurements that can refuse unsupported input. In a sealed second SHG acquisition family, one intensity image recovered polarization-derived collagen organization across two specimens. At matched coverage, invalid outputs fell from 86 under acquisition quality control and 26 under endpoint quality control to two, while missed preregistered coverage gates remained explicit.

**[Graphical abstract near here]**
