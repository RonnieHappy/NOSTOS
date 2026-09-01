# Frozen protocol: estimator-consensus reliability development and internal confirmation

## Rationale

The synthetic self-perturbation score failed prospectively on annotated SHG collagen. This experiment tests a tissue-label-free reliability model that combines perturbation stability with agreement among independently formulated FFT and structure-tensor orientation estimators. Manual centerlines define validity during development and evaluation but are never measurement inputs.

## Data partition

Use only the 1,188 patches in the externally supplied `final_train_test/train` split from Zenodo DOI 10.5281/zenodo.7243211. The previously analyzed 199-patch official test split is excluded. Source groups are formed by dropping the final underscore-delimited field from the supplied index identifier. Assign a complete source group to development when the first eight bytes of SHA-256(`source_group`) interpreted as an unsigned integer modulo 10 are 0–5; assign values 6–9 to confirmation. This deterministic 60:40 group partition is frozen before inspecting any train-split outcome.

## Label-free reliability coordinates

For each 128 x 128 grayscale image, retain the existing self-perturbation score and its six components; FFT anisotropy, entropy, log-SNR and log-wavelength; structure-tensor orientation and coherence at 1, 2, 4 and 8 pixels; axial FFT–tensor disagreement at each scale; and maximum interscale tensor disagreement. Standardize coordinates on development data and fit an L2-penalized logistic regression (`C=1`, balanced class weights, maximum 2,000 iterations, fixed random state 7243211) to predict invalid orientation.

Reference eligibility and invalidity remain unchanged from the SHG transfer: manual-centerline coverage at least 0.1%, label FFT anisotropy at least 0.15, and invalidity defined as image-to-label axial disagreement greater than 10 degrees.

Select the highest-coverage probability threshold on development data whose accepted risk is at most 10%, requiring at least 30% development coverage. If no threshold qualifies, development fails and confirmation is not assigned a pass.

## Locked confirmation

Apply the fitted scaler, coefficients and development-selected threshold once to confirmation source groups. Report eligible patches/groups, coverage, risk, Wilson and 10,000-draw source-group bootstrap intervals (seed 7243212), median accepted disagreement, invalid-detection AUC, and the unchanged legacy comparator.

Confirmation passes only if every gate holds:

- at least 200 eligible patches from at least 100 source groups;
- selective coverage at least 40%;
- source-group bootstrap risk upper 95% bound at most 15%;
- accepted median disagreement at most 5 degrees;
- invalid-detection AUC at least 0.75;
- selective risk lower than unselected and legacy risk, unless legacy coverage is less than half selective coverage.

No confirmation label may alter the model, threshold, gates or preprocessing. This is an internal same-archive confirmation and cannot replace confirmation on a separate acquisition.

