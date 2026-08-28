# Frozen protocol: local orientation along annotated SHG collagen centerlines

## Aim

Test whether a scale-resolved local orientation field recovers the tangent direction of manually annotated collagen centerlines and can abstain at locally unsupported positions. This replaces the invalid assumption that a heterogeneous collagen patch has one meaningful global angle.

## Data and partition

Use the 1,188 patches in `final_train_test/train` from Zenodo DOI 10.5281/zenodo.7243211. The official 199-patch test split remains excluded because it was opened during the failed global-orientation transfer. Source groups are formed by dropping the final underscore-delimited tile field. The SHA-256 group partition frozen for consensus reliability is retained: modulo-10 values 0–5 are development and 6–9 are confirmation. No tile from one source group may cross partitions.

## Reference tangent

Manual centerline labels are resized from 256 × 256 to 128 × 128 pixels by nearest-neighbour interpolation and reduced to a one-pixel skeleton. At every skeleton pixel at least 6 pixels from an image edge, collect skeleton coordinates within a 5-pixel Euclidean radius. A reference is eligible when at least 5 coordinates are present and the local coordinate-covariance anisotropy `(lambda_max-lambda_min)/(lambda_max+lambda_min)` is at least 0.70. The principal covariance eigenvector defines the axial reference tangent.

## Image estimators

For the grayscale SHG image, compute Gaussian structure-tensor fields at sigma 1, 2, 4 and 8 pixels. The local fiber axis is perpendicular to the dominant gradient axis. Tensor coherence is `(lambda_max-lambda_min)/(lambda_max+lambda_min)` and energy is `lambda_max+lambda_min`.

NOSTOS selects, independently at each eligible reference position, the scale maximizing `coherence × sqrt(energy / median_energy_at_scale)`. Its label-free confidence is the selected coherence multiplied by `exp(-axial_spread/20)`, where axial spread is the maximum disagreement among scale estimates whose energy is at least 25% of the maximum local scale energy.

Comparators are fixed-scale structure tensors at sigma 2 and sigma 4 pixels. They use the same reference positions and report both unconditional error and coherence-selective error.

## Development and locked confirmation

At each development source group, aggregate pixel results to avoid treating centerline pixels as independent specimens. Select the lowest NOSTOS confidence threshold whose pooled accepted-pixel invalid risk is at most 10%, requiring at least 40% coverage and at least 100 development source groups. Invalid means axial error greater than 10 degrees. If no threshold qualifies, confirmation has zero coverage.

Apply the frozen threshold once to confirmation groups. Report pixels and groups, coverage, median axial error, invalid risk, group-median error, source-group bootstrap 95% intervals (10,000 draws; seed 7243213), and comparator results. Confirmation passes only if all gates hold:

- at least 100 eligible confirmation source groups and 10,000 eligible reference pixels;
- coverage at least 40%;
- source-group bootstrap upper 95% bound for invalid risk at most 15%;
- accepted median axial error at most 5 degrees;
- median source-group median error at most 7.5 degrees;
- NOSTOS accepted median error no worse than the better fixed-scale comparator by more than 1 degree at matched-or-greater coverage.

This experiment validates an algorithmically derived local tangent against manual centerline geometry within one archive. It is not independent-acquisition, physical-scale, tissue-mechanism or clinical validation. All outcomes, including failure, remain in the evidence ledger.

