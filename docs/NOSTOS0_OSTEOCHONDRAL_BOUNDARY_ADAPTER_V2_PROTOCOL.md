# NOSTOS-0 boundary-aware osteochondral ROI-adapter development

Protocol version: `nostos-osteochondral-boundary-adapter/2.0`

Frozen after opening every result from learned-adapter version 1.1. This is post-test development on the same public PTA micro-CT archive. It cannot confirm the adapter, establish independent acquisition transfer or support clinical use.

## Motivation and fixed hypothesis

Version 1.1 achieved median whole-mask Dice 0.912 but failed six of nine gates. Four patients had median interface error above 100 µm; only 57.8% of columns were within 30 µm; median ±75-µm band IoU was 0.534; and only one of six downstream measurements reached concordance correlation 0.85. The mismatch between whole-mask overlap and interface-conditioned measurement motivates one fixed change: train the same model with an objective that explicitly weights the first foreground interface in each image column.

The hypothesis is that boundary-aware optimization will reduce patient-level interface error and improve agreement of measurements sampled immediately above that boundary without sacrificing mask overlap.

## Frozen change

Data, patient folds, architecture, initialization, augmentation, optimizer, learning rate, weight decay, batch size, epoch cap, patience, output threshold and largest-component postprocessing remain identical to version 1.1. The only change is the training and validation objective:

1. binary cross-entropy is weighted by `1 + 4 exp(-d²/(2·5²))`, where `d` is vertical pixel distance from the first reference foreground pixel in each eligible column;
2. soft Dice loss is retained;
3. a differentiable first-transition estimate is computed from positive vertical changes in predicted foreground probability;
4. smooth-L1 error between predicted and reference interface rows, normalized by image height, is added with weight 2 and beta 0.02.

No v2 parameter may be tuned after outer-fold outcomes are opened.

## Evaluation and promotion rule

The same 19-patient, five-fold outer evaluation, fixed Otsu and classical-path comparators, patient bootstrap, downstream measurements and nine version-1.1 gates are reused. V2 is considered a useful development advance only if:

1. all nine original gates pass; or
2. at least seven original gates pass, median interface error and band IoU improve over v1.1 for the same patients with paired 95% bootstrap intervals excluding zero, no original passing gate regresses, and at least four of six downstream measurements reach CCC 0.85.

Anything weaker remains failed development. Even a successful development result requires a frozen inference package and a separately acquired untouched dataset before promotion.

## Execution

Use the CUDA environment in `requirements-segmentation-cu128.txt` and the version-1.1 data manifest:

```powershell
<SEGMENTATION_ROOT>\.venv-seg\Scripts\python.exe scripts\run_osteochondral_learned_adapter.py `
  <DATA_ROOT>\mCTSegmentation\extracted\Data\pre_processed `
  --development-receipt outputs\nostos0-osteochondral-interface-development-v1\osteochondral_interface_development.json `
  --output <BULK_DATA_ROOT>\outputs\nostos0-osteochondral-boundary-adapter-v2 `
  --objective boundary --epochs 30 --batch-size 12 --workers 0
```
