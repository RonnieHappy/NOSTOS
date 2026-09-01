# NOSTOS-0 bone contract-ablation benchmark

**Protocol version:** `nostos-bone-contract/1.0`  
**Frozen:** 28 August 2026, before label-dependent analysis  
**Primary purpose:** determine whether the complete NOSTOS validity contract reduces silently invalid emitted measurements at matched coverage.

## Central hypothesis

Across unseen acquisition shifts, the full NOSTOS validity contract will lower case-level silent-invalid risk relative to the same estimator that always emits a value and relative to conventional endpoint-specific QC, without reducing overall coverage below 80% or any endpoint/acquisition stratum below 70%.

## Public archives and roles

1. Zenodo 3355937, mouse-bone SHG: development of orientation and abstention rules. Disease labels are not used to tune measurement validity.
2. Figshare 20765659, paired SHG/autofluorescence bone: untouched compact acquisition-family confirmation. Mouse is the independent unit.
3. Zenodo 11061868, rat confocal lacunar-canalicular network: 3D topology and anisotropic-sampling confirmation using supplied masks.
4. Zenodo 17909733, human synchrotron nanoCT: external human 3D acquisition-family transfer using supplied lacunar, canalicular and remodeling masks.
5. Zenodo 6345772, UV photoacoustic microscopy: out-of-family modality challenge. Only endpoints with declared structural support are eligible; otherwise abstention is the correct output.

## Endpoint families

### Local orientation

- Estimator: the already declared local structure-tensor direction field.
- Reference: coherent versus mixed/non-informative SHG regions, adjacent-section continuity and perturbation stability. Rough region labels are not treated as exact angular truth.
- Invalidity: an emitted orientation in an annotation-incompatible region or an emitted orientation whose axial disagreement exceeds 10 degrees across a registered mild perturbation pair.

### Network survival

- Estimator: skeleton length, branch density, connected fraction and erosion-survival curve from imported reference masks.
- Invalidity: emitted output when resampling or a one-voxel mask perturbation changes prespecified topology beyond the registered tolerance, or when crop-boundary contact invalidates a spanning claim.

### Three-dimensional geometry

- Estimator: local thickness and mask-conditioned topology in physical coordinates.
- Invalidity: physical error above 15% under a truth-preserving resampling pair, use of isotropic spacing for anisotropic data, or topology emission after connectivity is destroyed.

## Compared conditions

1. **Full NOSTOS:** calibration checks, endpoint preconditions, perturbation probes, uncertainty and abstention.
2. **Always emit:** identical measurement estimator with no failure logic.
3. **Endpoint QC:** identical estimator with conventional intensity, size, sampling and SNR filters.
4. **Partial contract:** remove calibration, perturbation stability, annotation compatibility or topology-preservation logic one component at a time.

No tissue or disease classifier is trained. Estimator parameters are not optimized against genotype or disease labels.

## Perturbations

Apply registered small translations, crop shifts, contrast changes, blur, noise, isotropic and anisotropic resampling and one-voxel mask erosion/dilation where applicable. Perturbations are paired within original scan. They do not create independent biological samples.

## Independent units and splits

- Mouse-bone SHG development: mouse is the primary unit; scan and section are nested.
- Paired SHG/autofluorescence confirmation: mouse is the primary unit; modality and field are repeated measures.
- Rat confocal: animal/specimen is the primary unit; subvolumes are nested.
- Human nanoCT: donor/specimen is the primary unit; remodeling regions and crops are nested.
- UV-PAM: source specimen or slide group is the primary unit. Patches are never treated as independent biological samples.

If source metadata cannot identify the declared independent unit, inferential analysis for that archive must abstain and remain descriptive.

## Primary endpoint

Macro-averaged area under the case-level risk-coverage curve. Silent-invalid risk is the proportion of accepted cases whose emitted measurement violates the endpoint-specific frozen invalidity rule.

### Primary success gate

The full contract must reduce macro risk-coverage area by at least 20% relative to the strongest ablation, and the paired 95% specimen-level bootstrap interval for the difference must exclude zero.

## Secondary gates

- Overall coverage at least 80% and every endpoint/acquisition stratum at least 70%.
- At 80% matched coverage, silent-invalid risk is lower for every endpoint and materially lower for at least two.
- Among accepted valid cases, NOSTOS is non-inferior to the best focused estimator at frozen endpoint-specific margins.
- Case-level empirical uncertainty coverage lies between 90% and 97.5%; no major acquisition stratum is below 85%.
- Removing calibration, stability testing or abstention materially worsens at least two endpoints.
- Runtime and usable-sample fraction are reported without success gates.

## Statistical analysis

All intervals resample the highest identifiable independent biological unit and retain nested scans, sections, fields, frames, volumes, masks and patches. Risk-coverage comparisons are paired within the original case. Macro averages weight endpoint/acquisition strata equally. Missing or ambiguous hierarchy is reported and cannot be repaired by treating nested observations as independent.

## Interpretation rules

- Passing the benchmark supports a failure-aware measurement-contract advantage across the tested bone acquisition families.
- Failure rejects the broad platform-advantage claim. Individual endpoint validation remains reportable.
- SHG and autofluorescence are not required to produce identical biological measurements.
- Programmed or image-derived deformation is not tissue mechanics.
- Imported-mask topology does not validate automatic segmentation.
- No result establishes diagnosis, treatment guidance or intraoperative utility.

## Frozen outputs

- `source_manifest.json` with API metadata, file URLs, sizes, licenses and deposited checksums.
- `download_receipt.json` with local SHA-256 values.
- `case_registry.csv` with independent-unit and nesting fields.
- `protocol_receipt.json` containing this file's SHA-256 before outcome analysis.
- Condition-specific case outputs, risk-coverage curves, paired bootstrap intervals, failures and abstention reasons.
- A final machine-readable gate table retaining every pass and failure.
