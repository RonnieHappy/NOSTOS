# NOSTOS-0 figure-source table

No panel may be generated from an unindexed notebook or manually transcribed
number. Proposed panels remain provisional until the final manuscript figure
set is frozen.

| Figure concept | Required source | Statistical unit | Current eligibility |
|---|---|---|---|
| Response-geometry architecture | `src/nostos/core/response.py`; `src/nostos/features/universal.py` | Software object | Eligible as schematic |
| Synthetic ground-truth recovery | `outputs/nostos0-synthetic-v1/validation.json` | Phantom/perturbation instance | Eligible |
| Module perturbation matrix | `outputs/nostos0-module-perturbations-v1/module_perturbation_matrix.json` | Module × perturbation | Eligible |
| Representation comparison | `representation_benchmark.json`, `kymatio_benchmark.json`, `pyradiomics_benchmark.json` | Held-out phantom perturbation | Eligible with “synthetic” label |
| Bone thickness validation | `outputs/external-bone-v1/external_bone_validation.json` | Volume and voxel | Eligible; identify public reference |
| Filament cross-domain atlas | `outputs/external-filament-v1/external_filament_validation.json` | Image | Supplementary or exploratory main panel |
| Cartilage site-matched associations | `cartilage_response_associations.csv` | Participant | Provisional pending masks |
| Cartilage exclusion robustness | `outputs/cartilage-ablation-analysis-v1_1/ablation_associations.csv`; `ablation_correlation_contrasts.csv` | Participant | Provisional pending masks |
| Incremental prediction | `ablation_prediction_repeats.csv`; `ablation_prediction_summary.csv` | Participant, paired outer folds | Provisional pending masks and external cohort |
| Segmentation accuracy | Reviewed masks and `nostos-seg-evaluate` receipt | Held-out participant | Ineligible—reference masks absent |
| Clinical/intraoperative panel | Prospective acquisition and registered reference data | Specimen/patient | Ineligible—data absent |

Every final panel must have a panel identifier, source path, source SHA-256,
generation command, software environment, exclusions and denominator in the
archival figure manifest.
