# NOSTOS BioSR v6 prospective confirmation failure

**Decision:** FAIL after the first untouched confirmation structure  
**Method version:** `nostos-paired-acquisition-support/6.0`  
**Threshold or endpoint refitting after access:** none

## What was tested

The complete v6 implementation, endpoint families, family thresholds, field-selection rule and decision gates were SHA-256 locked before any Microtubules or F-actin archive was downloaded, listed or decoded. The first confirmation tranche comprised eight Microtubules fields selected by the frozen hash-only rule. The run produced 72 registered acquisition pairs and 1,512 endpoint rows.

The result is a prospective failure. The full contract accepted 703 of 927 reference-eligible measurements (75.84% coverage), of which 45 were invalid (6.40% observed risk). Its clustered 95% risk upper bound was 17.77%. The contract reduced risk–coverage area by 31.40% relative to always emitting a value, but that ranking improvement did not satisfy the operating policy.

| Endpoint family | Eligible | Accepted | Coverage | Invalid | Risk | Frozen family decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Hessian response shape | 144 | 144 | 100.00% | 0 | 0.00% | Pass |
| Spectral order | 144 | 144 | 100.00% | 0 | 0.00% | Pass |
| Tensor coherence | 360 | 181 | 50.28% | 0 | 0.00% | Fail: insufficient coverage |
| Tensor orientation | 279 | 234 | 83.87% | 45 | 19.23% | Fail: excessive accepted-case risk |

The contract therefore did something useful but insufficient: it removed many invalid measurements, yet rejected too many coherence measurements and failed to identify many wrong orientation estimates. Conventional acquisition QC emitted all 927 eligible measurements with 18.66% risk. Full NOSTOS reduced risk to 6.40%, and cases rejected only by the full contract were enriched 3.06-fold for invalidity, but the 24.16-percentage-point coverage loss exceeded the frozen 10-point comparator allowance.

## Why the remaining confirmation pixels are being preserved

The combined v6 gate cannot pass once a required structure–family combination has failed. Decoding the F-actin fields now would consume prospective evidence without changing that decision. The eight Microtubules fields are therefore reclassified as development-only for the next method version. F-actin image members remain undecoded and no F-actin endpoint outcome has been calculated.

The official linear F-actin archive also exposed a manifest error during ZIP central-directory indexing: every field contains levels 01–12, whereas the v6 configuration declared 01–09. The runner failed closed before field selection and before opening an image member. The archive byte count and deposited MD5 both match. A future lock must correct this layout fact explicitly; it cannot silently modify the v6 record.

## Next valid gate

1. Diagnose tensor coherence and axial orientation using only the eight receipted Microtubules fields.
2. Preserve the already successful Hessian and spectral families unless an implementation audit finds a defect.
3. Replace raw family cutoffs only through an explicit v7 development analysis with field-level cross-validation and component-correct comparators.
4. Freeze the v7 implementation, gates, corrected 12-level F-actin layouts, endpoint tolerances and deterministic field identities before opening any F-actin image member.
5. Run the linear and nonlinear F-actin tranches once. A passing v7 must satisfy every retained structure–family risk and coverage gate and demonstrate incremental value beyond clean conventional QC.

Until that gate passes, NOSTOS remains a research prototype. This result does not establish universal measurement validity, clinical usability, biological truth, diagnostic performance, intraoperative utility or Nature-level readiness.
