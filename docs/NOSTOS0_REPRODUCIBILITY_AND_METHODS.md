# NOSTOS-0 reproducibility and methods specification

## Software object

NOSTOS-0 represents a calibrated image or volume as a collection of response
surfaces rather than an unordered feature vector. Each response records a
module and measurement name, physical-scale axes, optional specimen-relative
axes, direction where applicable, response values, stability metadata,
validity flags and explicit abstention reasons. The implemented core comprises
spectral organization, structure tensors, scale-normalized Hessian morphology,
maximal-sphere local thickness, network erosion survival and directional
variograms.

The core environment requires Python 3.12 or newer and is declared in
`pyproject.toml` and `uv.lock`. External comparators are isolated because their
supported dependency ranges conflict with the core environment. Kymatio 0.3.0
uses the pinned Python 3.12 environment in
`requirements-comparators.lock.txt`. PyRadiomics uses the Windows conda
environment in `configs/radiomics39-environment.yml`; exact package URLs are
recorded in `configs/radiomics39-explicit.txt`.

## Validity-profile compiler

The primary methods object is a pair of separately executable stages. During
development, `compile-validity-profile` fits input-only risk calibration within
group-preserving folds and selects an operating threshold from prespecified
risk, uncertainty and coverage gates. During confirmation,
`audit-validity-profile` applies the frozen maps and threshold once. Candidate
decisions may use declared acquisition metadata and features computed from the
input image, but never the reference measurement, error or invalidity label.

The hierarchical extension is compiled with
`compile-conditional-support`. Base-accepted development rows are partitioned
by declared coordinates such as acquisition modality, capture level, requested
physical or pixel scale and endpoint family. A cell is supported only when it
passes minimum accepted-row, independent-group, observed-risk and uncertainty
requirements. `audit-conditional-support` composes this table over the
immutable base profile. Missing, unseen, underrepresented or unsafe cells hard
abstain. Ordinary acquisition QC is evaluated at matched emitted-row count and
does not receive the conditional gate.

Every confirmation writes three complementary artifacts: the audit and gate
decisions, all scored rows including abstentions, and exact finite-sample
intervals. The latter reports nested-emission risk separately from the
proportion of independent groups with any failure. A zero-event percentile
cluster bootstrap is explicitly not interpreted as a population upper bound.

### BioSR confirmation

BioSR v9 uses eight untouched F-actin fields and 980 eligible tensor-coherence
rows under controlled degradation. The frozen contract emitted 931 rows
(95.0% coverage), with 36 invalid measurements (risk 0.0387) versus 72/980
(0.0735) for ordinary acquisition QC. Relative risk reduction was 47.4% and the
clustered AURC-difference interval excluded zero. Repeated scales and
degradations are nested within field.

### FMD failure-repair-confirmation programme

FMD source data are the public `WideField_BPAE_R.tar` archive (DOI
`10.7274/r0-ed2r-4052`; SHA-256
`4914cd7d951b4ddc1a01f6c7f121b7e9936fd2a7d1505f3e802984ffee69cad7`).
Each FOV contains 50 repeated acquisitions; raw, average-of-2, -4, -8 and -16
inputs are compared with the average-of-50 reference. Four realization indices
per acquisition level are selected by frozen SHA-256 rules. The FOV is the
independent unit. Because the archive does not supply pixel spacing, every
endpoint is explicitly pixel-relative.

The programme retains five stages. A metadata attempt failed before endpoint
analysis; a runtime attempt was stopped before row export; v1.1 found no valid
operating point; v1.2 passed in aggregate but failed in widefield; and a
widefield-specific v1.3 profile passed pooled confirmation while reproducing a
fully invalid average-of-8 by 8-pixel cell. Those failures were not overwritten.

V1.4 combined the eight now-open v1.3 FOVs as post-failure development and
compiled acquisition-level×requested-scale support over an unchanged base
profile. Four cells were supported: average-of-16 at 4, 8 and 16 pixels, and
average-of-8 at 16 pixels. Four new FOVs were then decoded once. The profile
emitted 64/240 eligible primary values with zero observed errors. Matched
ordinary acquisition QC emitted 31/64 errors (risk 0.484). The FOV-bootstrap
AURC difference was 0.281 (95% interval 0.187–0.416). Exact two-sided
Clopper–Pearson upper 95% limits were 0.056 for the 64 nested emissions and
0.602 for the four-FOV any-failure proportion.

## Synthetic truth and perturbations

Deterministic analytic phantoms encode orientation, wavelength, blob/tube/sheet
morphology, thickness, roughness, network structure and anisotropic spatial
correlation. Ground truth, spacing and random seed are stored with every
phantom. Controlled perturbations include rotation, resampling, crop, blur,
noise, contrast, anisotropic point-spread function, partial volume and mask
error.

The general synthetic receipt is
`outputs/nostos0-synthetic-v1/validation.json`. The module-specific prospective
matrix is `outputs/nostos0-module-perturbations-v1/module_perturbation_matrix.json`.
It contains 24 required tests and two mask-sensitivity tests. Mask error is not
treated as an invariance condition.

## Representation and upstream comparators

The frozen synthetic classifier split contains four constructs and disjoint
training/test perturbation types. The response geometry, naïve response
summaries and conventional scalar features use the same linear SVC and fixed
training/test samples. Six leave-one-module-out representations are retained.

The exact exported comparator dataset has SHA-256
`f84e1fbf6ac7ef16285a7aaa9e40d2036cdff77a7ffff5faa7df96b12a532d55`.
Official Kymatio Scattering2D uses J=3, L=8 and maximum order 2, with spatial
mean aggregation. PyRadiomics uses first-order, GLCM, GLRLM, GLSZM, GLDM and
NGTDM features with a fixed bin count of 16 for this comparator experiment.
The fixed-bin-count comparison is not called IBSI-equivalent.

PyRadiomics was separately checked against 14 published first-order values on
the official IBSI digital phantom. The image and mask, repository commit and
hashes are recorded in `manifests/ibsi_reference_subset.json`. PyRadiomics
kurtosis was converted to excess kurtosis by subtracting three, following the
documented implementation difference. All 14 values matched the published
three-significant-digit reference precision. This is subset conformance, not a
claim of complete IBSI texture-matrix conformance.

## External bone validation

Eight public trabecular-bone volumes and matched reference thickness maps from
Zenodo record 11061947 were processed without parameter tuning after the
declared three-case development pilot. Maximal-sphere thickness was evaluated
voxelwise and by volume summary against the provided reference. The frozen
method obtained mean absolute relative bias 8.05%, median voxelwise Spearman
correlation 0.927 and mean MAE 0.0189 mm. A twice-nearest-boundary proxy was
retained as a negative comparator; the paired MAE reduction was 0.0741 mm with
exact one-sided Wilcoxon P=0.00390625. Inputs and MD5 values are recorded in
`manifests/external_bone_subset.json`.

## External filament validation

Thirty annotated images from the MyceliumSeg cross-species collection were
processed by the frozen response implementation. The source lacks pixel-size
calibration, so only dimensionless image-relative coordinates are reported.
Species balanced accuracy was evaluated with participant/image-level samples
and a permutation test. Full response geometry reached 0.680 balanced accuracy
(P=0.00498), conventional scalars 0.668 and naïve summaries 0.553. Several
module ablations exceeded the full representation. The result supports
transfer and structural information, not universal superiority; species and
acquisition remain confounded.

## Cartilage validation and ablations

Safranin-O medial and lateral sections are evaluated at participant level.
Site-specific HHGS and OARSI scores are paired with same-site features; PLM is
evaluated medially only. Patch or tile rows are summarized before inference.
Associations use Spearman correlation, 2,000 participant bootstrap draws and
Benjamini–Hochberg control within site and outcome. Prediction uses ten repeats
of five-fold participant-level outer cross-validation with inner RidgeCV.

The semantic proposals are not reference masks. The current cartilage results
therefore have status `exploratory_weak_mask`. A locked review packet contains
all 40 images from eight pre-existing validation participants, with no outcome
fields in the reviewer manifest. Its pointer and hashes are in
`manifests/cartilage_mask_review_packet.json`.

The v1.1 ablation experiment processed 90/90 medial and 87/87 lateral sections.
Variants include 95% tile purity; 100 and 250 µm all-boundary erosion; 100 and
250 µm external-surface exclusion; proposal-class-4 exclusion; enclosed-hole
exclusion; and exclusion within 25 µm of the darkest 1% of proposal-cartilage
pixels. The latter two are sensitivity proxies, not lesion or cellular labels.
Paired correlation differences use common-participant bootstrap resampling.
Prediction folds are identical across FFT, geometry/optical-density, combined
and ablated families.

## Failure and negative-result accounting

- The full response representation does not outperform focused FFT in the
  cartilage cohort.
- PyRadiomics ties NOSTOS on the small synthetic classification split.
- Some filament module ablations outperform the full response geometry.
- Proposal-defined void and enclosed-hole exclusions are inert and therefore
  non-informative.
- Extreme-dark-object exclusion attenuates medial HHGS association and
  prediction, preventing cell/cluster-independent or matrix-specific claims.
- Manual segmentation accuracy and transfer to undeclared acquisition families
  remain unproven. Clinical utility is outside the computation-only NOSTOS-0
  claim.

## Unstained PSHG operator pathway

The only confirmed label-free deployment profile is the exact public PSHG-TISS
breast FSHG acquisition: ten polarization frames at 0:20:180 degrees plus R2
and SNR support maps. The scientific confirmation used 48 ROIs. Production
v1.4 then passed all 13 locked gates on four additional hash-selected fields,
including numerical equivalence, reference error, runtime, memory, artifact
registration and clinical withholding. Its p95 compute-plus-export time was
0.452 seconds; acquisition time was not measured.

```powershell
nostos intraop-pshg <PSHG_FIELD_FOLDER> --pixel-size-um 1.0 --output outputs\operator-case
python scripts\audit_intraop_operator_workflow_v1.py --dataset-root <PSHG_BREAST_ROOT>
python scripts\audit_intraop_workstation.py
```

Only a hash-identical public bundle can inherit confirmed evidence. A new
format-compatible acquisition is emitted as `review` and
`unvalidated_new_acquisition`; all diagnosis, boundary, mechanics and treatment
fields remain withheld. The complete file and new-instrument bridge contract is
in `docs/NOSTOS0_OPERATOR_GUIDE.md`.

## Reproduction commands

From the repository root, using the core environment:

```powershell
nostos validate-synthetic --output outputs\nostos0-synthetic-v1
nostos validate-modules --output outputs\nostos0-module-perturbations-v1
nostos benchmark-synthetic --output outputs\nostos0-benchmark-v1
nostos validate-bone --data <DATA_ROOT>\trabecular-bone-zenodo-11061947 --output outputs\external-bone-v1
nostos validate-filament --data <DATA_ROOT>\myceliumseg-zenodo-15224240\extracted\labeled-GS_PO_TS --output outputs\external-filament-v1
nostos validate-cartilage --medial outputs\universal_cartilage\safo_medial.csv --lateral outputs\universal_cartilage\safo_lateral.csv --scores manifests\metadata.scores_raw.csv --output outputs\external-cartilage-v1
nostos validate-nuclei --data <DATA_ROOT>\BBBC039v1 --output outputs\external-nuclei-v1_1
nostos validate-nuclei-confirmatory --data <DATA_ROOT>\BBBC007v1 --output outputs\external-nuclei-confirmatory-v1
nostos validate-nuclei-bbbc020 --data <DATA_ROOT>\BBBC020v1 --output outputs\external-nuclei-bbbc020-v1
python scripts\run_fmd_widefield_validity_profile_v1_3.py --data <DATA_ROOT>\measurement-support-benchmark\fmd\WideField_BPAE_R.tar --split development --output outputs\nostos0-fmd-widefield-v1-3-development
python scripts\compile_fmd_widefield_conditional_v1_4.py --base-profile outputs\nostos0-fmd-widefield-v1-3-compiled\validity_profile.json --output outputs\nostos0-fmd-widefield-v1-4-conditional-development
python scripts\run_fmd_widefield_conditional_confirmation_v1_4.py --data <DATA_ROOT>\measurement-support-benchmark\fmd\WideField_BPAE_R.tar --config configs\fmd_widefield_conditional_support_v1_4.locked.json --base-profile outputs\nostos0-fmd-widefield-v1-3-compiled\validity_profile.json --conditional-profile outputs\nostos0-fmd-widefield-v1-4-conditional-development\conditional_support_profile.json --confirmation-lock manifests\fmd_widefield_conditional_support_v1_4_confirmation_lock.json --output outputs\nostos0-fmd-widefield-v1-4-conditional-confirmation
python scripts\audit_fmd_widefield_conditional_v1_4.py outputs\nostos0-fmd-widefield-v1-4-conditional-confirmation\confirmation_rows.jsonl --config configs\fmd_widefield_conditional_support_v1_4.locked.json --base-profile outputs\nostos0-fmd-widefield-v1-3-compiled\validity_profile.json --conditional-profile outputs\nostos0-fmd-widefield-v1-4-conditional-development\conditional_support_profile.json --output outputs\nostos0-fmd-widefield-v1-4-conditional-confirmation-audit
python scripts\audit_fmd_finite_sample_uncertainty_v1_4.py outputs\nostos0-fmd-widefield-v1-4-conditional-confirmation-audit\confirmation_audit.json outputs\nostos0-fmd-widefield-v1-4-conditional-confirmation-audit\confirmation_scored.jsonl --output outputs\nostos0-fmd-widefield-v1-4-finite-sample-uncertainty.json
python scripts\build_fmd_program_final_audit.py --project-root . --output outputs\nostos0-fmd-validity-program-final-audit-v1
python -m nostos.evaluation.cartilage_ablations manifests\dataset_manifest.json --stain SafO --site Medial --workers 4 --output outputs\cartilage-ablations-v1_1\safo_medial.csv
python -m nostos.evaluation.cartilage_ablations manifests\dataset_manifest.json --stain SafO --site Lateral --workers 4 --output outputs\cartilage-ablations-v1_1\safo_lateral.csv
python -m nostos.evaluation.cartilage_ablation_analysis --medial outputs\cartilage-ablations-v1_1\safo_medial.csv --lateral outputs\cartilage-ablations-v1_1\safo_lateral.csv --scores manifests\metadata.scores_raw.csv --output outputs\cartilage-ablation-analysis-v1_1
nostos build-evidence-bundle --project-root . --output outputs\nostos0-evidence-bundle-v30
python -m pytest -q
```

Kymatio and PyRadiomics commands are implemented in
`scripts/benchmark_kymatio.py` and `scripts/benchmark_pyradiomics.py` and must
be executed in their declared isolated environments.

## Release boundary

Local `C:\` and `E:\` paths are development locations and must not appear in a
submitted manuscript as data availability. `nostos-build-release` constructs a
deterministic, data-free archive, rewrites private development roots to portable
placeholders, preserves byte-locked scientific artifacts, scans for credentials
and private absolute paths, and emits file and archive SHA-256 receipts. The
v29 remains an immutable historical candidate. Release v30 adds the generic
validity-profile compiler, hierarchical support, FMD failure/confirmation
lineage, finite-sample audit and rebuilt manuscript assets. It must be installed
from its ZIP in a fresh Python 3.13 environment using
`uv sync --extra dev --frozen --link-mode copy`, run the full applicable suite,
pass `nostos doctor`, reproduce all locked hashes and rebuild byte-identically.
Prior clean-room failures remain part of the record. Submission still requires
an immutable public tag, archived DOI and unaided external execution.
