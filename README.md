# NOSTOS

NOSTOS-0 is a CPU-first computational-microscopy framework for failure-aware
quantitative measurement. Its central contribution is an executable validity
profile: a frozen, input-only contract that decides whether a particular
measurement is supported for a declared acquisition and requested analysis
scale. Unsupported or unseen conditions abstain instead of returning an
unqualified number.

The measurement engine exposes established spectral, tensor, Hessian,
geometric, network, spatial and dynamic estimators through one typed response
schema. Every response can retain physical or declared pixel-relative scale,
direction, uncertainty, perturbation behavior, evidence maturity, provenance
and explicit abstention reasons. NOSTOS uses the same measurements without
tissue-specific retraining; what a measurement means biologically still
requires a domain-specific study.

The current paper is computation-only. No wet-lab experiment, device or
clinical workflow is part of the NOSTOS-0 claim. Clinical and intraoperative use
remain prohibited extensions rather than submission gates. The live claim
boundary is in `docs/NOSTOS0_CLAIM_EVIDENCE_LEDGER.md`; the terminal
computational audit is `docs/NOSTOS0_FINAL_COMPUTATIONAL_METHODS_AUDIT_V3.md`.

The official Kymatio comparison is intentionally isolated because Kymatio 0.3.0 is incompatible with the core environment's current SciPy. Reproduce it with Python 3.12 and `requirements-comparators.lock.txt`, export the frozen data with `write_external_comparator_dataset`, then run `scripts/benchmark_kymatio.py`. The current synthetic held-out result is 0.875 balanced accuracy for Kymatio versus 1.000 for NOSTOS response curves; this is not evidence of biological superiority.

The upstream PyRadiomics comparison uses the pinned conda environment in `configs/radiomics39-environment.yml` (exact URLs in `configs/radiomics39-explicit.txt`) and `scripts/benchmark_pyradiomics.py`. It passes 14/14 published IBSI digital-phantom first-order reference values and reaches 1.000 balanced accuracy on the frozen synthetic split, equal to NOSTOS. `scripts/benchmark_pyradiomics_ibsi_texture.py` additionally parses the official IBSI workbook read-only and passes 75/75 definitionally matched 3-D texture features at three significant digits; four unsupported or non-equivalent features remain explicitly not comparable. These results remove any basis for claiming universal NOSTOS superiority over radiomics.

Run `nostos build-evidence-bundle --project-root . --output outputs/nostos0-evidence-bundle-v30` to regenerate the SHA-256 index of all 112 required evidence receipts. A complete index is an integrity result, not a venue guarantee.

## Measurement-validity compiler

Development and confirmation are deliberately separate commands:

```powershell
nostos compile-validity-profile development.jsonl --config protocol.json --output compiled-profile
nostos audit-validity-profile confirmation.jsonl --profile compiled-profile\validity_profile.json --output confirmation-audit

nostos compile-conditional-support development.jsonl --config protocol.json `
  --base-profile compiled-profile\validity_profile.json --output conditional-profile
nostos audit-conditional-support confirmation.jsonl --config protocol.json `
  --base-profile compiled-profile\validity_profile.json `
  --conditional-profile conditional-profile\conditional_support_profile.json `
  --output conditional-confirmation
```

The hierarchical compiler learns support cells over declared acquisition and
measurement coordinates using development data only. Confirmation decisions do
not consume reference values or invalidity labels. The confirmation command
writes the frozen audit, row-level decisions and exact finite-sample intervals
that keep nested measurements separate from independent fields or specimens.

The strongest current confirmation uses the public FMD widefield archive. A
pooled v1.3 profile passed but concealed a reproducible fully invalid
average-of-8-captures by 8-pixel cell. The frozen hierarchical v1.4 repair
emitted 64 of 240 eligible measurements on four new FOVs with zero observed
errors, whereas matched ordinary acquisition QC emitted 31 errors among 64
values. The FOV-clustered AURC difference was 0.281 (95% interval
0.187–0.416). This is bounded same-family evidence, not zero-risk or
cross-instrument proof; the exact upper 95% limit for the proportion of FOVs
with any failure is 60.2% because only four independent FOVs were available.

The network module has a prospectively confirmed reference-mask endpoint. A frozen HRF experiment first failed and exposed a background-centre distance discretization defect. The corrected, versioned boundary-distance response was developed only on HRF, then passed all seven gates on untouched official STARE hand labels. This validates sampling stability of the measurement, not automatic vessel segmentation or retinal diagnosis.

The explicit `measure-series` pathway has a prospectively confirmed bulk-registration endpoint. It passed all six frozen gates on untouched BBBC035 microscopy content under programmed noisy translations and matched the pinned scikit-image phase-correlation comparator. Dense flow, cell tracking and native biological motion are not implied.

## Learned osteochondral ROI-adapter development

The prospective training-free PTA micro-CT interface adapter failed and is rejected. A post-failure three-level U-Net was subsequently evaluated using five patient-grouped outer folds over 19 patients, 35 samples and 1,960 discovered slices. It achieved median whole-mask Dice 0.912, but its apparent 21.6 µm interface error is not a definitive accuracy estimate: the public reference is a threshold-derived mineralized-tissue mask rather than a manually traced continuous interface, and frozen extraction policies changed patient-median error from 16.0 to 512.8 µm and changed model ranking. A boundary-aware v2 model also failed its prespecified gates. The masks remain useful for whole-tissue segmentation development; a manually adjudicated interface set is required for an interface claim.

The frozen protocol and exact CUDA environment are in `docs/NOSTOS0_OSTEOCHONDRAL_LEARNED_ADAPTER_BENCHMARK.md` and `requirements-segmentation-cu128.txt`. The compact receipt is `outputs/nostos0-osteochondral-learned-adapter-v1_1/osteochondral_learned_adapter_summary.json`; full checkpoints and slice-level output are bulk artifacts and are not committed.

## External replication challenge

An external user can test the frozen, data-free foundation with one command:

```powershell
uv run nostos replication-challenge --operator "laboratory-or-reviewer-name" --affiliation "institution" --unaided --no-author-environment --source-kind release_archive --assistance "none" --output replication-result
```

The command regenerates the synthetic truth validation, representation benchmark and module perturbation matrix, checks eight prespecified gates and writes `replication_receipt.json` plus three hashed source receipts. Return the unedited directory through the repository's external-replication issue form. A pass establishes independent execution of the released software; it does not establish biological or clinical validation. The complete protocol is in `docs/NOSTOS0_EXTERNAL_REPLICATION_PROTOCOL.md`.

The locked cartilage segmentation review packet is stored under `<DATA_ROOT>/validation/cartilage-mask-review-v1`. It contains 40 outcome-free cases from eight validation participants, paired source/proposal renders, a reviewer manifest and a separately hashed crosswalk. Its status is `pending_human_reference_masks`; packet generation is not segmentation validation.

## Frozen synthetic validation

Run the CPU validation foundation before biological analysis:

```powershell
uv run nostos validate-synthetic --output outputs/synthetic-validation
uv run nostos benchmark-synthetic --output outputs/synthetic-benchmark
```

The receipt `validation.json` contains the frozen protocol version, deterministic truth registry and hashes, controlled perturbation results, measurement errors, pass/fail decisions, and abstentions. Protocol v1.1 registers orientation, wavelength, blob, tube, sheet, thickness, roughness, network, and spatial-heterogeneity constructs. It applies independent synthetic gates to spectral orientation/scale, structure-tensor orientation, 3-D Hessian morphology, calibrated thickness, network erosion survival, and directional spatial heterogeneity. These are foundation gates, not substitutes for biological or external validation.

Universal framework code lives under `nostos.core` and `nostos.validation`. The existing public cartilage analysis remains an application rather than the definition of NOSTOS itself.

The synthetic representation benchmark uses fixed training perturbations and disjoint held-out perturbations. It compares conventional scalar features, naïvely collapsed response summaries, complete NOSTOS response curves, and six leave-one-module-out ablations. Its receipt explicitly labels the experiment as synthetic and descriptive; it is not evidence of biological or clinical superiority.

## External trabecular-bone reference

The first external-domain check uses a checksum-locked subset of Zenodo record `11061947` containing public 100³ micro-CT bone masks and archived IPL thickness maps:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_bone_reference_subset.ps1
uv run nostos validate-bone --data <DATA_ROOT>/data/public/trabecular-bone-zenodo-11061947 --output outputs/external-bone-v1
```

NOSTOS computes maximal-inscribed-sphere thickness over 32 frozen logarithmic physical-radius levels. The receipt reports agreement, bias and error against the archived reference while retaining the simpler twice-nearest-boundary calculation as a baseline. The eight-volume single-archive result is preliminary external validation, not evidence of broad generalization.

## Bone validity-contract stress program

The larger label-free/3-D bone program is stored on the T7 under
`<DATA_ROOT>/data/public/bone-contract-benchmark`; hashes, licences, roles and
independent-unit boundaries are indexed in
`manifests/bone_contract_datasets.json`. After downloading the archives, the
complete frozen sequence, integrity audit, receipt consolidation and focused
tests run from one command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_bone_contract_program.ps1 -DataRoot <DATA_ROOT>\data\public\bone-contract-benchmark
```

The machine-readable disposition is
`outputs/nostos0-bone-contract-summary/bone_contract_program_summary.json`;
its reviewer-facing companion is the adjacent Markdown file. Every input
receipt is SHA-256 indexed, and an incomplete input set fails closed.

This program currently strengthens the failure ledger rather than a flagship
performance claim. Perturbation-only mouse-SHG support failed, the rat-network
stress contract reduced silent-invalid risk but missed its coverage gate, and
human nanoCT scalar and scale-indexed responses also failed frozen coverage or
risk gates. The UV-PAM contract correctly withheld an uncalibrated,
semantically unsupported physical endpoint, which is governance evidence rather
than accuracy validation. None of these runs supports disease, mechanics or
clinical claims.

## External filament-domain reference

The cross-species MyceliumSeg subset contains 30 manually masked images. Because physical pixel spacing is not supplied, NOSTOS uses dimensionless normalized coordinates and refuses micrometre-scale claims:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_filament_reference_subset.ps1
uv run nostos validate-filament --data <DATA_ROOT>/data/public/myceliumseg-zenodo-15224240/extracted/labeled-GS_PO_TS --output outputs/external-filament-v1
```

The validation compares the full response geometry with conventional scalars, naïve block summaries and leave-one-module-out ablations. It is explicitly exploratory because acquisition may be confounded with species.

## External nuclei-field validation

BBBC039v1 supplies 200 Hoechst fluorescence fields and manual instance masks. NOSTOS evaluates only the official 50-image test list, performs no fitting and abstains from physical-scale claims because pixel calibration is unavailable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_bbbc039_reference.ps1 -Destination <DATA_ROOT>/BBBC039v1
uv run nostos validate-nuclei --data <DATA_ROOT>/BBBC039v1 --output outputs/external-nuclei-v1_1
```

BBBC039 informed the bright-object polarity refinement, so it is development evidence.
Two separately frozen transfer protocols retain failures as well as successes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_bbbc007_reference.ps1 -Destination <DATA_ROOT>/BBBC007v1
uv run nostos validate-nuclei-confirmatory --data <DATA_ROOT>/BBBC007v1 --output outputs/external-nuclei-confirmatory-v1

powershell -ExecutionPolicy Bypass -File scripts/fetch_bbbc020_reference.ps1 -Destination <DATA_ROOT>/BBBC020v1
uv run nostos validate-nuclei-bbbc020 --data <DATA_ROOT>/BBBC020v1 --output outputs/external-nuclei-bbbc020-v1
```

Both independent transfers produced strong localization but failed their prespecified
superiority gate against Laplacian-of-Gaussian. NOSTOS therefore presents the Hessian
field as an interpretable coordinate, not a superior or novel segmentation algorithm.

## Selective FFT measurement

The frozen analytic confirmation evaluates whether self-perturbation probes can detect
unsupported orientation and wavelength estimates:

```powershell
uv run python scripts/run_selective_fft_confirmation.py --output outputs/nostos0-selective-fft-confirmation-v1
```

The confirmation retains every accepted and abstained case, exact truth error, coverage,
selective risk, Wilson interval, legacy-QC comparison and prespecified gate.

The unchanged rule can be audited against external filament images and manual masks:

```powershell
uv run python scripts/run_selective_filament_transfer.py --data-root <MYCELIUMSEG_ROOT> --output outputs/nostos0-selective-filament-transfer-v1
```

This frozen transfer failed because branching networks rarely supplied a defined global mask axis (2/30 eligible). The failure is retained to prevent an inappropriate global-orientation claim.

A fit-for-purpose transfer uses only the externally supplied SHG collagen test split and its manual centerlines:

```powershell
uv run python scripts/run_selective_shg_transfer.py --dataset-root <COLLAGEN_CENTERLINES_ROOT> --output outputs/nostos0-selective-shg-transfer-v1
```

This prospective transfer also failed: 183/199 patches were reference-eligible, but 95.1% coverage carried 33.3% selective risk and invalid-detection AUC was 0.677. The result forbids extending the synthetic abstention claim to biological SHG.

The subsequent estimator-consensus redesign is reproducible with:

```powershell
uv run python scripts/run_consensus_reliability.py --dataset-root <COLLAGEN_CENTERLINES_ROOT> --output outputs/nostos0-consensus-reliability-v1
```

It also failed prospectively: development AUC was 0.740 and no operating point met the frozen risk/coverage requirement, so the held-out group confirmation correctly reported zero coverage rather than manufacturing a favorable threshold.

Local centerline orientation is evaluated separately from the failed global endpoint:

```powershell
uv run python scripts/run_local_orientation_validation.py --dataset-root <COLLAGEN_CENTERLINES_ROOT> --output outputs/nostos0-local-orientation-v1
uv run python scripts/run_local_orientation_external_test.py --dataset-root <COLLAGEN_CENTERLINES_ROOT> --output outputs/nostos0-local-orientation-external-v1
uv run python scripts/download_pshg_tiss.py --root-folder 61b242879c71e30270f67e31 --subset "breast tissue unstained / FSHG" --output <PSHG_BREAST_ROOT>
uv run python scripts/run_pshg_external_orientation.py --dataset-root <PSHG_BREAST_ROOT> --output outputs/nostos0-pshg-breast-orientation-v1 --reference-offset-degrees 90 --protocol-version nostos-pshg-breast-orientation/1.0 --protocol-sha256 2d579bdb7f122b6900f4dfbc084d73c40671832f2d7cf85d4b854657ecef4705 --bootstrap-seed 7242323
```

Adaptive scale selection failed development and remains in the ledger. The subsequently frozen scale-declared sigma-2 endpoint passed all eight external-test gates on 19,657 annotated tangent pixels from 115 source groups (median axial error 6.72°, source-group bootstrap 95% interval 6.24–7.25°, axial alignment 0.832). The test split had previously been opened for a distinct global endpoint, so this is endpoint-new evidence rather than pristine dataset-level confirmation.

The polarity-aware Hessian field improves over a multiscale Laplacian baseline but remains inferior to raw Hoechst intensity. Because polarity was refined after the initial sign-agnostic result on the same test split, this result is explicitly post-test development and requires prospective confirmation on another acquisition.

## Cartilage-domain response validation

The public OA cohort now receives the same spectral, tensor, Hessian and spatial response modules. Site-specific outcomes remain site matched and all inference is specimen level:

```powershell
uv run nostos validate-cartilage --medial outputs/universal_cartilage/safo_medial.csv --lateral outputs/universal_cartilage/safo_lateral.csv --scores manifests/metadata.scores_raw.csv --output outputs/external-cartilage-v1
```

The complete response concatenation does not outperform the focused FFT representation in this cohort. NOSTOS therefore does not expose a universal diagnostic score; it exposes calibrated response curves whose biological meaning and eligible modules must be validated per domain.

Reproducible public-data pilot for participant-level cartilage morphology analysis.

> Research use only. NOSTOS does not provide a diagnosis, surgical boundary, treatment recommendation, or validated estimate of tissue mechanics.

## Install and verify

```powershell
git clone https://github.com/RonnieHappy/NOSTOS.git
cd NOSTOS
uv sync --extra dev
uv run nostos doctor
```

`nostos doctor` returns a machine-readable readiness report covering Python dependencies, the browser application and configured storage paths.

## Analyze one microscopy image

For the sample-agnostic measurement interface:

```powershell
nostos measure path\to\image.tif --spacing 0.65 --unit um --output outputs\field-001
nostos measure path\to\volume.nii.gz --spacing 5,1,1 --unit um --mask path\to\mask.nii.gz --output outputs\volume-001
nostos measure-series path\to\series.npy --spacing 0.65 --unit um --temporal-spacing 2 --temporal-unit min --output outputs\series-001
```

An optional acquisition profile can suppress measurements known to be unsupported for a compatible acquisition family and label retained endpoints with their evidence maturity:

```powershell
nostos measure path\to\biosr-compatible-image.tif --spacing 0.0626 --unit um `
  --measurement-profile configs\biosr_widefield_measurement_profile_v1.locked.json `
  --output outputs\profiled-field
```

Profiles are not tissue classifiers and must not be applied merely because an image looks similar. Without a compatible profile, NOSTOS reports empirical evidence as `unvalidated` rather than silently promoting successful computation to biological or clinical validity.

Profile application is fail-closed. NOSTOS verifies the linked pilot receipt, audit and protocol hashes; checks dimensionality, unit, pixel spacing and the frozen analysis-scale grid; and applies the profile's preprocessing and spectral-band contract. A mismatch leaves measurements available only as `unvalidated` and cannot suppress endpoints. Acquisition identity and the required nine-phase mean construction cannot be inferred from a standalone array, so they remain explicit user declarations in the output provenance.

`measure-series` has an explicit time-first contract. It reports calibrated bulk translation by default and, with `--dense`, a spatially indexed deformation field with frozen uncertainty bounds, eligibility and low-information abstention. Analytic and BBBC035 public-content confirmations are released. Optical flow remains a field-registration measurement: it is not object tracking, cell correspondence, strain, mechanics or native-motion validation.

`track-series` links imported framewise instance masks into calibrated continuation trajectories. Continuation tracking is confirmed on exact SIM+ truth and two real HeLa training sequences, with F1 values of 0.997, 0.988 and 0.977. Division inference is disabled by default because its final pristine transfer gate failed; `--experimental-divisions` exposes it with that status embedded in the output. NOSTOS does not represent imported silver masks as automatic segmentation or report hidden CTC test-set performance.

The cartilage-specific application remains available separately:

```powershell
nostos analyze path\to\section.tif `
  --stain SafO `
  --pixel-size-um 5.16 `
  --output outputs\case-001
```

The output directory contains:

- `analysis.json`: calibration, QC warnings, class proportions, tile coordinates and median FFT/texture measurements;
- `overlay.png`: segmentation proposal over the source image;
- `mask.png`: indexed tissue-region proposal;
- `spectrum.png`: whole-cartilage Fourier-power preview.

SafO is the validated pilot pathway. H&E is supported as a stain-specific comparator. PLM segmentation remains experimental. The default path is deterministic and CPU-only; `--learned-checkpoint` enables the optional learned proposal model.

## Analyze one unstained PSHG acquisition

The confirmed label-free profile expects ten polarization-resolved FSHG TIFFs
at 0:20:180 degrees plus shape-matched `R2.tif` and `SNR.tif` maps:

```powershell
nostos intraop-pshg path\to\acquisition-folder `
  --pixel-size-um 1.0 `
  --output outputs\operator-case
```

The command exports orientation, coherence and accepted-support arrays; four
visual products; and a hash-indexed JSON receipt. Exact locked public inputs can
report confirmed evidence. A format-compatible new acquisition is automatically
demoted to `review` with `unvalidated_new_acquisition`. Clinical output is always
withheld. Acquisition time is not included in the reported compute/export
latency. See `docs/NOSTOS0_OPERATOR_GUIDE.md` for the complete operator and
new-instrument bridge contract.

## Launch the local workstation

```powershell
nostos serve
```

The workstation binds to `127.0.0.1:8765` by default and opens in the local browser. To run without opening a browser, use `nostos serve --no-browser`. Do not expose the server to an untrusted network; it is a local research workstation, not a hardened clinical service.

## Analyze a cohort

```powershell
nostos batch manifests\dataset_manifest.json `
  --stain SafO `
  --site Medial `
  --section-rank 1 `
  --workers 4 `
  --output outputs\cohort\safo-medial.csv
```

The batch command preserves participant identity and section rank, writes one participant-section row per input record, and creates a companion `.report.json` file. Cohort comparisons must use participant-grouped inference; tiles must never be split independently across training and validation sets.

## First dataset

- Human Knee Cartilage Histopathology Assessment
- Source: SimTK DOI `10.18735/77ye-yh24`
- Expected scale: 90 participants, 180 specimens, approximately 27.81 GB
- Modalities: H&E, Safranin O/Fast Green, and polarized light microscopy TIFFs
- Labels: HHGS, OARSI, PLM, age, sex, and surgery side
- Source article license: CC BY-NC-ND 4.0; repository files remain subject to the terms presented by SimTK at acquisition and are not redistributed by NOSTOS

This dataset supports morphology pretraining, segmentation, grading experiments, and image-quality modeling. It does not contain co-registered tissue mechanics and therefore cannot independently validate mechanical competence.

## Layout

```text
NOSTOS/
  configs/                 experiment and data contracts
  data/public/             immutable downloaded and extracted source data
  manifests/               generated audits and participant splits
  src/nostos/              NOSTOS Python package
  tests/                   unit tests
```

## Initial workflow

1. Finish and extract the official archive under `data/public/human-knee-cartilage-histopathology/raw/`.
2. Run `python -m nostos.data.audit <raw-directory> --output manifests/dataset_manifest.json`.
3. Run `python -m nostos.data.split manifests/dataset_manifest.json --output manifests/splits.json`.
4. Review audit warnings and lock participant-level splits before generating image tiles.
5. Create human-reviewed semantic masks using the ontology in `docs/segmentation_protocol.md`; validate their CSV manifest before training.
6. Train the stain-conditioned model with `python -m nostos.segmentation.train <annotation-manifest.csv>`.
7. Evaluate complete held-out sections with `python -m nostos.segmentation.infer`, not randomly sampled tiles.
8. Extract ZSD and comparator features only from boundary-eroded articular cartilage.

Never split tiles, sections, or specimens independently across training and validation sets. Every record from one participant stays in one split.

## Run the microscopy application

From PowerShell, run `./launch_nostos.ps1` or `uv run nostos serve`. Local storage may be configured in `storage.json`; no particular drive letter is required. The primary endpoint is CPU-first; a learned CUDA proposal model is an optional experimental comparison and is not required for FFT analysis.

## Rebuild the CPU pilot

Run `./run_cpu_pilot.ps1` to regenerate participant-level Safranin-O and H&E features, association reports, paired-site validation, confounder-adjusted estimates, perturbation tests, mask-boundary sensitivity, and manuscript tables. Configure bulk-image storage through `storage.json`; generated tables and figures are written under `outputs/cpu_pilot/`.

## Rebuild the flagship validation

After the CPU pilot exists, run `./run_flagship_validation.ps1`. The command verifies the frozen protocol and dataset-manifest hashes before extracting the lexicographically second Safranin-O sections, then regenerates adjacent-section agreement, second-section outcome confirmation, raw-reader reliability, the participant-safe severity benchmark, and the complete test suite. Post-freeze operational changes and the single retained image-safety failure are recorded in `docs/confirmatory_deviations.md`.

## Evidence and claim boundary

The locked plan is in `docs/analysis_plan.md`; the living pre-results manuscript is in `docs/manuscript_draft.md`. Unsupervised color clusters are annotation proposals only and are never treated as reference masks. The locked test set is evaluated once after the segmentation and feature definitions pass validation.

The public cohort can support claims about histologic morphology, zonal organization, staining, reproducibility, and participant-level prediction. It cannot establish mechanical properties or clinical utility. Source images remain outside Git and must be acquired from SimTK under the applicable noncommercial terms.

The evidence-ranked expansion plan for depth-resolved, cellular, osteochondral, multimodal, and translational modules is in `docs/toolkit_expansion_review.md`.

The first implemented expansion is the versioned depth-normalized atlas. Reviewer-facing installation, commands, output definitions, validation criteria, and limitations are documented in `docs/depth_atlas_reproducibility_protocol.md`.

Its first 90-participant cohort QC run is documented in `docs/depth_atlas_v1_qc_report.md`. Version 1.0.0 failed the complete-depth coverage gate with weak masks and is not authorized for outcome association testing until the documented boundary-review and geometry-remediation steps are completed.

The two-track publication package is indexed in `docs/NBE_PACKAGE_README.md`. It separates the evidence-complete public-histology Article from the explicitly gated Nature Biomedical Engineering flagship development manuscript.
