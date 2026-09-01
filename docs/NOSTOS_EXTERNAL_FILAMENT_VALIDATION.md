# NOSTOS-0 external filament-domain validation

## Status

**Exploratory cross-domain validation.** The result establishes measurable sensitivity, not a universal biological classifier.

The frozen NOSTOS response geometry was applied to all 30 manually masked images in the `labeled-GS_PO_TS` portion of MyceliumSeg: 10 *Ganoderma sinense*, 10 *Pleurotus ostreatus* and 10 *Trametes* spp. images. Images and masks were created independently of NOSTOS.

The archive does not provide microscopy-style pixel calibration for these images. NOSTOS therefore used dimensionless normalized image coordinates and did not report micrometre-scale measurements.

## Analysis

Images were resized with preserved aspect ratio to a maximum dimension of 256 pixels. Masks used nearest-neighbour resampling. The same frozen modules measured coverage, tensor orientation/coherency, Hessian morphology, maximal-sphere thickness, erosion survival and directional spatial variation.

Species sensitivity was evaluated by a linear support-vector machine after standardization, using repeated stratified five-fold cross-validation. The result is not interpreted as a taxonomic classifier because species, cultivation and acquisition may be confounded.

## Results

| Representation | Repeated balanced accuracy |
|---|---:|
| Conventional scalar comparator | 0.668 |
| Naïve block summaries | 0.553 |
| Complete NOSTOS response geometry | 0.680 |
| NOSTOS without tensor | 0.670 |
| NOSTOS without Hessian | 0.655 |
| NOSTOS without geometry | 0.685 |
| NOSTOS without network | 0.703 |
| NOSTOS without spatial | 0.723 |

The complete geometry exceeded the conventional comparator by only 0.012 balanced-accuracy units. Its permutation P value was 0.00498, showing non-random species sensitivity, but removing the network or spatial block improved discrimination. Thus this dataset does **not** demonstrate that every module or the complete concatenation is optimal. It supports the narrower claims that the frozen representation transfers without tissue-specific feature retraining and contains cross-species structural information.

## Limitations

- Images, rather than independently cultured biological specimens, are the evaluation units.
- Acquisition and cultivation may be confounded with species.
- Physical pixel spacing is unavailable; only dimensionless scales are valid.
- Species discrimination does not establish the biological meaning of any response.
- The modest advantage over conventional features requires replication on calibrated filament microscopy.
- Ablations indicate redundancy and possible small-sample overfitting.

## Reproduction

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_filament_reference_subset.ps1
uv run nostos validate-filament --data <DATA_ROOT>\data\public\myceliumseg-zenodo-15224240\extracted\labeled-GS_PO_TS --output outputs/external-filament-v1
```

## Sources

Yuan Q et al. *A Mycelium Dataset with Edge-Precise Annotation for Semantic Segmentation*. *Scientific Data* (2025). DOI: 10.1038/s41597-025-06265-1. Dataset DOI: 10.5281/zenodo.15224240.
