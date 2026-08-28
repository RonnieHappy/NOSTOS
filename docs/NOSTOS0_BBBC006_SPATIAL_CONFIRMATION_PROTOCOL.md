# Frozen BBBC006 spatial-response confirmation protocol

**Protocol:** `nostos-bbbc006-spatial-confirmation/1.0`  
**Frozen:** 27 August 2026, before downloading or inspecting the selected z-plane archives  
**Dataset:** BBBC006v1 U2OS z-stacks, public-domain dedication

## Design

BBBC006 contains matched microscopy fields acquired every 2 µm through focus; z=16 is optimal, z=11–23 are expert-classified in focus and z=0 is out of focus. Archives z=15, z=16 and z=0 are downloaded. DAPI (`w1`) images common to all three archives are ranked by SHA-256 of the case identifier and the first 64 are retained, independent of pixel values.

**Pre-outcome operational clarification:** archive inspection showed that the trailing UUID differs by focal plane. The case identifier is therefore frozen as the filename prefix through well, site and channel (for example `mcf-z-stacks-03212011_e14_s2_w1`), excluding the plane-specific UUID. No pixels or endpoint values were inspected before this clarification.

Pixel spacing is declared as 0.645 µm/pixel from the documented 6.45-µm camera pixels, 2× binning and 20× magnification. Horizontal and vertical NOSTOS semivariograms are evaluated at 0.645 × `(1,2,4,8,16,24)` µm. For each image, their mean curve is divided by its maximum to isolate spatial shape from exposure amplitude. Adjacent-in-focus distance is the root-mean-square difference between normalized z=15 and z=16 curves. Defocus distance is the corresponding z=0 versus z=16 value.

Estimated horizontal and vertical ranges and the directional contrast curve are retained. No biological interpretation is assigned to a range in nuclear fluorescence.

## Gates

1. All 64 hash-selected matched DAPI triplets execute without loss and retain source hashes.
2. Every semivariogram output is finite; cases with a zero maximum abstain prospectively rather than being replaced.
3. Spearman correlation of z=15 versus z=16 mean estimated range is at least 0.75.
4. Median adjacent-in-focus normalized curve distance is at most 0.15.
5. Defocus distance exceeds adjacent-in-focus distance in at least 75% of cases.
6. The paired bootstrap 95% interval for median defocus-minus-adjacent distance excludes zero, using 20,000 resamples and seed 6006.

The experiment confirms repeatability and expected focus sensitivity of the spatial estimator on one public acquisition. It does not establish an externally known biological correlation length or universal acquisition invariance.
