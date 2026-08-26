# Frozen protocol: biological transfer of selective FFT orientation

## Purpose

Test whether the prospectively frozen NOSTOS FFT abstention score identifies unsupported orientation measurements in real biological microscopy. This is an external-transfer experiment, not a new threshold-development analysis.

## Data and independence

Use every paired image and manual binary mask in the public MyceliumSeg GS/PO/TS archive (DOI 10.5281/zenodo.15224240). NOSTOS investigators did not acquire or annotate these images. The archive has been used previously for exploratory species discrimination, but not for orientation agreement or selective measurement.

## Frozen processing

1. Locate image-mask pairs using the existing `external_filament._find_pairs` routine.
2. Convert each image to grayscale and its mask to binary.
3. center-crop both arrays to the largest common square and resize to 128 x 128 pixels (bilinear image; nearest-neighbour mask).
4. Measure intensity-image orientation and the self-perturbation score with the unchanged NOSTOS routine.
5. Measure the reference orientation from the manual binary mask with the same FFT estimator. The mask is used only as an independent structural reference, not as an input to the intensity-image score.
6. A specimen has an interpretable orientation reference when mask coverage is at least 0.5% and mask FFT anisotropy is at least 0.15. Other specimens are reported as reference-ineligible and excluded from agreement-risk denominators.
7. Among reference-eligible specimens, an intensity measurement is invalid when axial disagreement from the manual-mask reference exceeds 10 degrees.
8. Accept an intensity measurement only when the frozen synthetic-development score is no greater than 1.0943159403934886. Do not refit or recalibrate this threshold.
9. Legacy acceptance uses the previously specified rule: signal-to-noise ratio at least 3 and at least 4 pixels per measured wavelength.

## Prespecified summaries and gates

Report reference eligibility, selective coverage, selective disagreement risk with Wilson 95% interval, risk without abstention, invalid-detection ROC AUC when both classes occur, legacy coverage and risk, and accepted median axial disagreement.

The external transfer passes only if all gates hold:

- at least 15 reference-eligible specimens;
- selective coverage at least 40%;
- selective-risk Wilson upper bound at most 20%;
- accepted median axial disagreement at most 5 degrees;
- selective risk lower than both unselected risk and legacy risk (or legacy coverage less than half selective coverage);
- invalid-detection AUC at least 0.75 when estimable.

No gate, threshold, eligibility criterion, or validity limit will be changed after examining the result. Failure remains part of the evidence record.

