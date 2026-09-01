# NOSTOS-0 version-5 small-pilot verdict

## Decision

**Promising and materially corrected, but not yet a validated or clinically usable tool.** The twelve-field pilot is sufficient to identify what currently works, what must be disabled, and what requires untouched calibration. It is not sufficient to establish generalization.

## What the pilot actually tested

- 12 independent BioSR reference fields: six CCP and six ER.
- 90 paired acquisitions and 1890 endpoint cases.
- 1228 registered, reference-eligible endpoint cases across all measured endpoints.
- A frozen physically calibrated estimator, input-only validity evidence, registered high-resolution reference labels, and field-level provenance.

## Result after the acquisition profile is applied

The profile retains 10 endpoint families and disables three scalar outputs. Among retained claim endpoints, always-emitting risk was 4.5%. The descriptive unit score boundary accepted 99.6% with 4.5% observed risk. This is not the final threshold.

Full-contract AURC on retained endpoints was 0.0041, versus 0.0447 for always emit and 0.0054 for conventional QC.

As a descriptive ranking check, the closest tied-score point at or below 80% coverage accepted 79.9% with 0.0% observed risk. At or below 90% coverage it accepted 89.6% with 1.5% risk. These points were observed on development data and are not operating thresholds.

## Clean observations

18 structure-endpoint combinations had zero observed failures among reference-eligible pilot cases. This includes the response curves, angular entropy, anisotropy, variogram outputs, CCP coherence, and consensus-gated ER orientation. Zero observed failures in a small developmental pilot is encouraging, not a population guarantee.

## Explicitly disabled

- CCPs / `hessian_blob_scale`: The high-resolution reference maximum was at a scale-grid boundary, so the scalar was censored rather than identified; retain the curve.
- CCPs / `hessian_tube_scale`: The high-resolution reference maximum was at a scale-grid boundary, so the scalar was censored rather than identified; retain the curve.
- CCPs / `spectral_scale`: Eighty-five of 86 reference-eligible pilot pairs exceeded the frozen 25% relative-error tolerance; retain the calibrated spectrum but do not emit this scalar for this acquisition profile.
- ER / `hessian_blob_scale`: The high-resolution reference maximum was at a scale-grid boundary, so the scalar was censored rather than identified; retain the curve.
- ER / `hessian_tube_scale`: The high-resolution reference maximum was at a scale-grid boundary, so the scalar was censored rather than identified; retain the curve.
- ER / `spectral_scale`: Eighty-five of 86 reference-eligible pilot pairs exceeded the frozen 25% relative-error tolerance; retain the calibrated spectrum but do not emit this scalar for this acquisition profile.

## Remaining failure

- ER / `tensor_coherence` retained 51 silent invalid cases at the descriptive unit boundary (risk 28.3%).


ER tensor coherence is the principal unresolved item. All observed errors occurred at the two lowest signal levels, and the corrected score ranks those failures, but an untouched calibration partition must establish a threshold with field-clustered uncertainty.

## Go/no-go

- **Go** for continued research-tool development and frozen threshold calibration.
- **No-go** for clinical interpretation, intraoperative use, submission claims, or access to confirmation data before the threshold lock.
- **No further score or endpoint editing on these twelve fields.** Any additional change starts a new development version and leaves the calibration and confirmation partitions untouched.
