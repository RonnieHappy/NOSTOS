# NOSTOS BBBC020 independent-acquisition protocol

**Frozen before outcome calculation:** 26 August 2026  
**Dataset:** BBBC020 v1, murine bone-marrow-derived macrophage fluorescence microscopy  
**Source:** https://bbbc.broadinstitute.org/BBBC020  

## Purpose and independence

This experiment transfers the BBBC039-developed bright-object Hessian field, unchanged,
to a different laboratory acquisition and organism. BBBC020 was not used to choose the
Hessian polarity, scales, aggregation, comparator, metrics, or gates. The result is
retained whether it passes or fails.

## Locked inputs and cases

| Archive | SHA-256 |
|---|---|
| `images.zip` | `edf4a87be957ec2b7ab268bef92c2efae8e098dc0855a4fa9df80895ff7062e4` |
| `outlines_nuclei.zip` | `b212f10013ae2a0260976cff2134204ecba226853922aea2ab5289051a47ceb7` |

The DAPI channel is `c5`, as encoded by both the blue-only image channel and the
`_c5_` nuclear-outline filenames. All 20 fields with at least one manual nuclear
outline are included. The five `jw-30min` fields have no archived nuclear outlines
and are excluded by label availability, not image appearance or outcome.
The official archive contains one zero-byte placeholder,
`jw-15min 5_c5_43.TIF`; it is ignored as an unreadable non-annotation. This integrity
rule was recorded after archive extraction failed and before any outcome was computed.

## Partial-annotation rule

BBBC020 intentionally omits nuclei that are strongly overlapping, blurred, or cross
the image boundary. Unannotated pixels therefore cannot be treated as true background.
For each manually filled nuclear mask, evaluation is restricted to that nucleus and a
four-pixel outer ring after resizing. Pixels belonging to any other annotated nucleus
are removed from the ring. Per-field AP and ROC AUC are calculated only on the union of
these local labeled supports. This tests local foreground localization for the eligible
manual objects; it does not estimate whole-field segmentation accuracy.

## Frozen computation and inference

Images and individual masks are resized to a maximum dimension of 256 pixels (bilinear
image, nearest-neighbour masks). Intensity is normalized by the 1st and 99.8th
percentiles. NOSTOS uses bright-object, scale-normalized two-dimensional Hessian blob
responses at 2, 4, and 8 pixels, maximized across scale. Baselines are normalized DAPI
intensity and maximum absolute scale-normalized Laplacian-of-Gaussian at the same
scales. Field-level AP and ROC AUC are summarized with 10,000 image-level bootstrap
resamples (seed 20020).

The independent-acquisition transfer passes only if all gates pass:

1. Mean NOSTOS ROC AUC is greater than 0.75.
2. The lower 95% confidence limit for NOSTOS AP minus local foreground prevalence is
   greater than zero.
3. The lower 95% confidence limit for paired NOSTOS-minus-LoG AP is greater than zero.

Raw intensity is a positive acquisition control, not a required superiority target.
Pixel spacing is not supplied, so physical-scale output must abstain.
