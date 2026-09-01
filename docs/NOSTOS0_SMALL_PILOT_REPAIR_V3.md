# NOSTOS-0 paired-acquisition small-pilot repair, version 3

## Status

This is a developmental repair, not a confirmatory amendment. It was designed after inspecting the deterministic 6-CCP/6-ER pilot receipted in `manifests/biosr_small_pilot_v1.json`. Threshold-calibration fields and confirmation archives remained sealed.

## Failures exposed by the small pilot

1. The version-2 FFT characteristic-scale comparison used the same *fraction* of each image's Nyquist frequency. Because input and reference grids have different sampling, it compared different physical frequency bands. The scalar was therefore not the same estimand.
2. Tensor orientation observability was proxied by the mean local tensor coherence. A field can contain strong local edges but no coherent global axial direction. In that case the global angle is undefined even though mean local coherence is high.
3. A Hessian winning-scale scalar could be returned at the first or last requested scale. Such a boundary maximum is censored by the search interval and is not an identified characteristic scale.
4. The implementation receipt omitted imported estimator modules and the frozen dependency lock.

## Frozen repairs

### Common physical FFT band

The prior 0.02-0.90 fractional band is retained, but it is calculated once from the effective input Nyquist frequency and expressed in cycles/mm. Exactly those physical limits are applied to both input and reference. The analyzed limits are stored with every measurement.

### Correct axial observability

For every tensor scale, version 3 retains mean local coherence and additionally reports the magnitude of the global doubled-angle resultant:

\[
R_2 = \left|\frac{\sum_x w_x e^{2 i \theta_x}}{\sum_x w_x}\right|.
\]

The existing 0.15 gate is preserved numerically but attached to the correct quantity, \(R_2\). Orientation is reference-ineligible when reference \(R_2<0.15\), and the tool abstains when input \(R_2<0.15\).

### Scalar-scale identifiability

Hessian response curves remain valid outputs. A winning-scale scalar is reference-ineligible or input-abstained when its maximum lies at either boundary of the requested scale grid. No new fitted coefficient is introduced.

### Complete implementation identity

The implementation digest now covers the runner, paired-support logic, FFT estimator, response modules, QC, validation metrics, `pyproject.toml`, and `uv.lock`.

## Claim boundary

The same twelve fields may be rerun to test whether these defects are removed. They cannot validate final thresholds, generalization, clinical use, or a submission claim. Any later threshold calibration and confirmation must use untouched partitions under a new prospective lock.
