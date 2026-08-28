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
- Manual segmentation accuracy, independent acquisition and clinical utility
  remain unproven.

## Reproduction commands

From the repository root, using the core environment:

```powershell
nostos validate-synthetic --output outputs\nostos0-synthetic-v1
nostos validate-modules --output outputs\nostos0-module-perturbations-v1
nostos benchmark-synthetic --output outputs\nostos0-benchmark-v1
nostos validate-bone --data <DATA_ROOT>\data\public\trabecular-bone-zenodo-11061947 --output outputs\external-bone-v1
nostos validate-filament --data <DATA_ROOT>\data\public\myceliumseg-zenodo-15224240\extracted\labeled-GS_PO_TS --output outputs\external-filament-v1
nostos validate-cartilage --medial outputs\universal_cartilage\safo_medial.csv --lateral outputs\universal_cartilage\safo_lateral.csv --scores manifests\metadata.scores_raw.csv --output outputs\external-cartilage-v1
nostos validate-nuclei --data <DATA_ROOT>\BBBC039v1 --output outputs\external-nuclei-v1_1
nostos validate-nuclei-confirmatory --data <DATA_ROOT>\BBBC007v1 --output outputs\external-nuclei-confirmatory-v1
nostos validate-nuclei-bbbc020 --data <DATA_ROOT>\BBBC020v1 --output outputs\external-nuclei-bbbc020-v1
python -m nostos.evaluation.cartilage_ablations manifests\dataset_manifest.json --stain SafO --site Medial --workers 4 --output outputs\cartilage-ablations-v1_1\safo_medial.csv
python -m nostos.evaluation.cartilage_ablations manifests\dataset_manifest.json --stain SafO --site Lateral --workers 4 --output outputs\cartilage-ablations-v1_1\safo_lateral.csv
python -m nostos.evaluation.cartilage_ablation_analysis --medial outputs\cartilage-ablations-v1_1\safo_medial.csv --lateral outputs\cartilage-ablations-v1_1\safo_lateral.csv --scores manifests\metadata.scores_raw.csv --output outputs\cartilage-ablation-analysis-v1_1
nostos build-evidence-bundle --project-root . --output outputs\nostos0-evidence-bundle-v1
python -m pytest -q
```

Kymatio and PyRadiomics commands are implemented in
`scripts/benchmark_kymatio.py` and `scripts/benchmark_pyradiomics.py` and must
be executed in their declared isolated environments.

## Release boundary

Local `C:\` and `E:\` paths are development locations and must not appear in a
submitted manuscript as data availability. `nostos-build-release` constructs a
deterministic, data-free archive, rewrites private development roots to portable
placeholders, scans for credentials and private absolute paths, and emits file
and archive SHA-256 receipts. The 0.3.0 candidate was installed from its ZIP in
a fresh Python 3.13 environment with `UV_LINK_MODE=copy`; all 112 packaged tests
passed and two optional-comparator tests skipped. Submission still requires an
immutable public tag and archived DOI. No DOI currently exists, so that gate
remains open.
