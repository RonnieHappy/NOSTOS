# NOSTOS-0 BioSR v6 family-threshold development verdict

**Primary development gate:** PASS  
**Thresholds are structure-independent:** Yes  
**Confirmation data:** Not accessed  
**Confirmation access:** Not yet authorized; implementation freeze still required

## Primary policy

The component-complete family policy retained 91.98% of 4,823 eligible development cases with 2.12% observed risk. The structure-stratified reference-field cluster-bootstrap upper 95% risk was 2.60%.

- **hessian_response_shape:** threshold `0.456627501114`, 100.00% coverage, 0.00% risk, cluster upper 95% 0.00%.
- **spectral_order:** threshold `0.456627501114`, 100.00% coverage, 0.19% risk, cluster upper 95% 0.47%.
- **tensor_coherence:** threshold `0.309565405958`, 86.52% coverage, 3.68% risk, cluster upper 95% 4.55%.
- **tensor_orientation:** threshold `0.996457820327`, 78.72% coverage, 6.76% risk, cluster upper 95% 12.99%.

## Component-correct comparators

- **always_emit:** no complete family policy.
- **conventional_acquisition_qc:** PASS, 94.13% coverage and 2.33% risk.
- **physical_sampling_only:** no complete family policy.
- **perturbation_stability_only:** no complete family policy.
- **full_contract_without_qc:** no complete family policy.
- **full_contract_without_sampling:** PASS, 91.98% coverage and 2.12% risk.
- **full_contract_without_perturbation:** PASS, 93.99% coverage and 2.27% risk.
- **full_contract_without_identifiability:** PASS, 92.02% coverage and 2.19% risk.

Comparators no longer inherit hard abstentions from components they claim to omit. These are development-set comparisons; untouched confirmation must evaluate the locked policies without refitting.

## Boundary

A development pass permits construction of an immutable v6 confirmation package. It is not confirmation, clinical validation, biological ground truth or submission readiness. Axis-specific v5 variogram endpoints remain excluded; the intrinsic directional variogram is still a separate synthetic-development object.
