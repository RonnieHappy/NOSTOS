# Frozen HRF network-module validation protocol

**Protocol:** `nostos-hrf-network/1.0`  
**Frozen:** 27 August 2026, before outcome computation  
**Dataset:** High-Resolution Fundus Image Database, 45 images and expert vessel masks  
**Primary scope:** measurement stability on reference masks; not retinal diagnosis

## Design

All 45 official images, field-of-view masks and `manual1` vessel masks are included. Filename is the case identifier. No parameter is selected from the observed endpoint values.

NOSTOS erosion-survival and component-count curves are computed on the native manual mask with relative pixel spacing 1 and on a twofold area-max-pooled mask with spacing 2. Both curves are evaluated at physical thresholds 0, 2, 4 and 8 native pixels. This tests whether the physically indexed response is stable under a declared sampling change when the foreground itself is held to the expert reference.

The pinned upstream comparator is scikit-image 0.25.2 `skeletonize`. Endpoint count, branch-junction count, total skeleton length and graph cycle rank are extracted from the resulting eight-connected skeleton at native and twofold sampling. These outputs are comparator measurements, not inventions of NOSTOS.

An image-derived vessel proposal is evaluated separately using a frozen green-channel Frangi response and Otsu threshold inside the supplied field-of-view mask. Dice is reported only to quantify segmentation error. It cannot validate the reference-mask measurement pathway.

## Gates

1. All 45 reference masks are discovered and processed without case loss.
2. Every response is finite and component survival is non-increasing with erosion threshold.
3. Across cases, the median absolute native-versus-twofold difference in surviving fraction is at most 0.05 at every nonzero threshold.
4. Spearman correlation across cases is at least 0.85 for survival-curve area.
5. Native-versus-twofold skeleton-length Spearman correlation is at least 0.90.
6. Median absolute relative skeleton-length difference is at most 0.15.
7. The upstream comparator version and source-archive SHA-256 are recorded.

The complete result is `pass` only if every gate passes. Branches, endpoints and cycles are retained as sensitivity outputs but are not primary gates because small changes in digital skeleton junction geometry can alter these counts without changing the underlying vascular tree.

## Interpretation boundary

A pass supports physically indexed network measurement stability in one public manual-mask domain. It does not support image segmentation accuracy, vascular diagnosis, cross-modality generalization or superiority over dedicated retinal analysis software. A failure is retained and narrows the eligible network endpoints.
