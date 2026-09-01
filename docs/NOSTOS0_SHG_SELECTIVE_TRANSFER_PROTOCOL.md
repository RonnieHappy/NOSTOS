# Frozen protocol: selective FFT orientation in annotated SHG collagen

## Question

Does the unchanged NOSTOS FFT abstention rule identify unsupported global-orientation measurements in external second-harmonic-generation (SHG) collagen microscopy when manual fiber centerlines provide the reference?

## External test set

Use only the 199 patches in `final_train_test/test` from *Collagen fiber images and centerline annotations based on SHG imaging* (Zenodo DOI 10.5281/zenodo.7243211; published archive MD5 `fad5956015f7802d27b3d312bfddc8ec`). The training split will not be used. NOSTOS investigators did not acquire, split or annotate these data. The test-set index is parsed as supplied. Patch identifiers that differ only in the final underscore-delimited field are treated as one source group for cluster resampling.

## Frozen measurements

1. Pair each test image, binary centerline label and index entry by integer filename.
2. Resize the 256 x 256 image and label to 128 x 128 pixels (bilinear image, nearest-neighbour label). No tissue-specific training, enhancement or mask-conditioned intensity processing is allowed.
3. Apply `self_perturbation_score(image, spacing=1)` and accept only scores no greater than the previously frozen threshold `1.0943159403934886`.
4. Estimate the reference axis from the manual centerline label with the same global FFT estimator. The label is never supplied to the intensity-image score.
5. A patch has an interpretable global reference when centerline coverage is at least 0.1% and label anisotropy is at least 0.15. All others abstain from reference-based evaluation and remain counted in the eligibility summary.
6. An eligible intensity orientation is invalid when axial disagreement from the centerline reference exceeds 10 degrees.
7. The legacy comparator accepts when image SNR is at least 3 and measured wavelength spans at least 4 pixels.

## Prespecified inference

Report test patches and source groups; reference eligibility; selective coverage; accepted invalid count; selective risk; Wilson and source-group bootstrap 95% intervals; unselected risk; invalid-detection ROC AUC; legacy coverage and risk; and accepted median axial disagreement. Cluster bootstrap uses 10,000 source-group draws with replacement and seed 7243211.

The transfer passes only if every gate holds:

- at least 100 eligible patches from at least 50 source groups;
- selective coverage at least 50%;
- source-group bootstrap upper 95% bound for selective risk at most 15%;
- accepted median axial disagreement at most 5 degrees;
- invalid-detection AUC at least 0.75;
- selective risk is lower than unselected risk and lower than legacy risk, unless legacy coverage is less than half selective coverage.

The synthetic threshold, reference criteria, error limit, comparator and gates will not be changed after inspecting NOSTOS outcomes. Failure will remain in the evidence ledger. This validates only global 2D orientation support, not collagen biology, local fiber direction, physical wavelength or clinical utility.

