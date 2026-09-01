# NOSTOS BBBC007 prospective confirmation protocol

**Frozen before outcome calculation:** 26 August 2026  
**Dataset:** BBBC007 v1, Drosophila Kc167 fluorescence microscopy  
**Source:** https://bbbc.broadinstitute.org/BBBC007  
**License:** CC0

## Purpose

This experiment tests the BBBC039-informed bright-object Hessian rule on a separate,
previously unevaluated acquisition. No BBBC007 image or annotation may be used to
choose scales, polarity, score aggregation, baselines, metrics, or success gates.

## Locked inputs

| Archive | SHA-256 |
|---|---|
| `images.zip` | `b7009e2fce0a3152a5c9adda916eaa699d09696f4bd02a7d05d12d041e30c6d1` |
| `outlines.zip` | `6a5246f9a9d743d22eafdb409fae638a8461af97e9ff9c4a92f25eba236224d3` |

All 16 DNA fields are included. DNA channels are selected only by the acquisition
filenames: names ending in `d.tif`, `_D_1UL.tif`, or `d0.tif`. The matching manual
outline is inverted and its closed contours are filled. No case may be excluded
after inspection of a score or label.

## Frozen computation

1. Resize each image so its longest dimension is 256 pixels; bilinear interpolation
   is used for intensity and nearest-neighbour interpolation for the filled mask.
2. Normalize intensity by the 1st and 99.8th percentiles.
3. Compute the scale-normalized two-dimensional Hessian blob field at 2, 4, and 8
   pixels with **bright-object polarity**.
4. Use the maximum response across scales as the NOSTOS localization score.
5. Compare against normalized intensity and the maximum absolute scale-normalized
   Laplacian-of-Gaussian response at the same scales.
6. Calculate pixelwise average precision (AP) and ROC AUC separately for each field.
   Inference is at the image level: means and paired differences receive percentile
   bootstrap 95% intervals with 10,000 resamples and seed 7007.

This evaluates foreground localization, not instance segmentation, cell counting,
phenotype prediction, or physical-scale accuracy. Because pixel spacing is absent,
NOSTOS must abstain from reporting micrometre-scale measurements.

## Prospective success gates

The confirmation passes only if all gates pass:

1. Mean NOSTOS ROC AUC is greater than 0.75.
2. The lower 95% confidence limit for NOSTOS AP minus image foreground fraction is
   greater than zero.
3. The lower 95% confidence limit for paired NOSTOS-minus-LoG ROC AUC is greater
   than zero.

Raw intensity is an acquisition-specific positive-control baseline, not a required
superiority target. All results, including a failed confirmation, will be retained.
