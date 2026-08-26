# NOSTOS-0 response-geometry benchmark v2 protocol

**Frozen before feature extraction or outcome calculation:** 26 August 2026

## Question

Does preserving calibrated response curves provide reproducible information under
unseen acquisition shifts beyond collapsing the same modules into scalar summaries,
while remaining non-inferior to established high-dimensional image representations?

## Frozen dataset

Six analytic construct classes are used: orientation, spectral scale, blob, roughness,
network and spatial heterogeneity. Each class has 40 training and 40 test images
(480 images total), generated at 96 × 96 pixels from disjoint seeds. Physical parameters
vary independently within prespecified ranges. Training images receive mild noise,
blur and contrast changes. Test images receive compound, disjoint shifts: larger noise
and blur, arbitrary axial rotation, contrast change and partial-volume resampling followed
by center crop or padding. Masks are not supplied to any representation.
After perturbation, every image is standardized once by its own mean and standard
deviation and clipped to [−5, 5]; every representation receives those identical values.

Randomness is generated only from NumPy `PCG64` with master seed 260826. The exported
NPZ stores images, labels, split, case identifier and generation parameters. Its SHA-256
is written before comparator execution.

## Frozen representations

1. **NOSTOS response geometry:** ordered scale-, threshold- and separation-resolved
   response curves; no scalar collapse.
2. **Matched collapsed summaries:** mean, standard deviation, minimum and maximum of
   every NOSTOS response block.
3. **Conventional scalar features:** intensity histogram and gradient summaries.
4. **PyRadiomics:** its conformance-audited first-order and texture feature families,
   fixed bin count 16.
5. **Kymatio:** `Scattering2D(J=3, L=8, max_order=2)` with spatial averaging.

Every representation uses the same standardized linear SVM (`C=1`). No tuning,
feature selection or test-set fitting is permitted. The full training split is used once;
the test split is evaluated once.

## Metrics and uncertainty

The primary metric is test balanced accuracy. Case-level correctness is resampled
10,000 times with seed 82626 to obtain percentile 95% intervals for balanced accuracy
and paired accuracy differences. Per-class recall and the full prediction vector are
retained. Because the test set is balanced, paired accuracy difference is the paired
difference in balanced accuracy.

## Prospective gates

The platform-level claim passes only if every gate passes:

1. Lower 95% confidence limit for NOSTOS balanced accuracy is greater than 0.80.
2. Lower 95% confidence limit for NOSTOS minus matched collapsed-summary accuracy is
   greater than zero.
3. NOSTOS is non-inferior to PyRadiomics with a −0.02 margin: the lower 95% confidence
   limit for the paired accuracy difference is greater than −0.02.
4. NOSTOS is non-inferior to Kymatio with the same −0.02 margin.
5. At least two module ablations reduce balanced accuracy by 0.03 or more, demonstrating
   that the result is not carried by a single familiar module.

All failures and comparator outputs will remain in the evidence bundle. Passing this
synthetic benchmark supports response-geometry retention under controlled shifts; it
does not establish biological interpretation or clinical utility.
