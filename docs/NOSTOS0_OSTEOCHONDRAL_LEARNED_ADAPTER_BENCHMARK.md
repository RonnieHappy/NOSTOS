# NOSTOS-0 learned osteochondral ROI-adapter benchmark

Protocol version: `nostos-osteochondral-learned-adapter/1.1`

Frozen: 26 August 2026 after the training-free adapter confirmation failed and all masks were opened. This is explicitly post-failure development, not pristine confirmation.

## Purpose

Determine whether NOSTOS can preserve boundary-conditioned measurements when its ROI is supplied by a competent learned adapter. This benchmark tests the adapter/measurement interface and patient-grouped generalization within one public human PTA micro-CT dataset. It cannot establish cross-acquisition transfer.

## Data and grouping

Use all 35 public samples from 19 patient prefixes in the Tiulpin *et al.* PTA dataset (3.2-µm isotropic voxels; archive SHA-256 `20A809AF46BD4AF0E7E71859F25EB445FC35B1D386E92BE5B7F17A3EC234E10F`). Patient prefixes are ordered by SHA-256 and assigned round-robin to five outer folds. No patient may occur in more than one fold. Both `ZX` and `ZY` slices at indices 8, 24, ..., 440 are included when present. Images and masks are downsampled twofold to 6.4 µm per pixel for training and inference.

For outer fold *k*, fold *k* is held out for testing and fold `(k+1) mod 5` is used only for epoch selection; the other three folds train the model. Test-fold masks are not used for optimization, threshold selection or stopping.

## Frozen model and optimization

The adapter is a three-level single-channel U-Net with base width 16, batch normalization and SiLU activations. Optimization uses AdamW (learning rate 3×10^-4; weight decay 10^-4), batch size 12, binary cross-entropy plus soft Dice loss, automatic mixed precision and seed 8,262,603. Training lasts at most 30 epochs with patience six on validation loss. Augmentation is limited to horizontal reflection, gamma 0.7–1.4, multiplicative contrast 0.8–1.2 and Gaussian noise up to 0.03 after percentile normalization. The output threshold is fixed at 0.5. The final mask retains the largest connected component and fills holes smaller than 64 downsampled pixels.

Version 1.1 is a pre-result integration amendment. The one-epoch software smoke test showed that the version-1.0 lower-border rule was anatomically inapplicable: none of the first 100 discovered reference masks touched the literal bottom row, and reference-mask vertical maxima across all 1,960 slices ranged from 4.7% to 77.9% of image height. The invalid 30-epoch run was stopped during fold 1 before a receipt was produced. No outer-fold performance result was inspected. Component selection was therefore replaced by the label-independent largest-component rule before the benchmark was restarted; the amendment and failed smoke receipts remain outside confirmatory evidence.

## Endpoints and comparators

Out-of-fold endpoints are full-mask Dice and IoU, vertical interface median absolute error, 90th-percentile error, fraction of columns within 30 µm and IoU in a ±75-µm reference band. Results collapse slice → sample → patient; a 10,000-draw patient bootstrap (seed 8,262,603) supplies intervals.

Fixed comparators are the global Otsu/lower-component method and the rejected training-free dynamic-path adapter (`sigma=1`, contrast weight 0, jump penalty 1). Paired patient-bootstrap intervals compare boundary error.

The 100-µm non-calcified band above predicted and reference interfaces is evaluated with the six frozen NOSTOS measurements used in the preceding confirmation: normalized mean and standard deviation, angular spectral entropy, structure-tensor coherency at 12.8 and 25.6 µm, and variogram anisotropy at 25.6 µm. Concordance correlation, Spearman correlation and standardized absolute error are reported.

## Development targets

The benchmark is considered technically promising, but not confirmed, only if all targets are met:

1. all 19 patients and 35 samples have out-of-fold predictions;
2. median patient-level Dice is at least 0.75;
3. median interface error is no greater than 30 µm and its bootstrap upper limit no greater than 45 µm;
4. at least 70% of boundary columns are within 30 µm;
5. median ±75-µm band IoU is at least 0.80;
6. learned-adapter boundary error is lower than both comparators with paired-bootstrap upper limits below zero;
7. at least four of six downstream measurements have concordance correlation at least 0.85, with median standardized absolute error no greater than 0.20.

Any failed target remains visible. No result from this dataset can be promoted to independent confirmation. Promotion requires a separately acquired, untouched dataset with reference masks and the complete frozen inference package.

The machine-readable receipt additionally requires every discovered slice to yield an evaluable prediction and lists any abstention explicitly. This coverage check was identified during fold-3 evaluation, before the aggregate receipt or any patient-level performance statistic was produced; it was applied during checkpoint-only receipt regeneration without retraining or altering predictions.

## Reproduction

Create a separate Python 3.13 environment and install `requirements-segmentation-cu128.txt`. The recorded execution used PyTorch 2.11.0+cu128 on an NVIDIA GeForce RTX 5070 Ti. CPU execution is valid but substantially slower. Obtain the source archive from its original public repository and verify SHA-256 `20A809AF46BD4AF0E7E71859F25EB445FC35B1D386E92BE5B7F17A3EC234E10F` before extraction.

```powershell
py -3.13 -m venv <SEGMENTATION_ROOT>\.venv-seg
<SEGMENTATION_ROOT>\.venv-seg\Scripts\python.exe -m pip install -r requirements-segmentation-cu128.txt
<SEGMENTATION_ROOT>\.venv-seg\Scripts\python.exe scripts\run_osteochondral_learned_adapter.py `
  <DATA_ROOT>\mCTSegmentation\extracted\Data\pre_processed `
  --development-receipt outputs\nostos0-osteochondral-interface-development-v1\osteochondral_interface_development.json `
  --output <BULK_DATA_ROOT>\outputs\nostos0-osteochondral-learned-adapter-v1_1 `
  --epochs 30 --batch-size 12 --workers 0
```

Checkpoint-only receipt regeneration uses `--reuse-checkpoints`; it does not retrain or change predictions. The compact receipt is versioned in the repository. The full 1,956-slice receipt and five model checkpoints remain bulk artifacts on T7 until archival deposition.
