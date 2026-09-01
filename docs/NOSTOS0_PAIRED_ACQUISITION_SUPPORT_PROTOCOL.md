# NOSTOS-0 paired-acquisition measurement-support protocol

**Protocol:** `nostos-paired-acquisition-support/1.0`  
**Status at lock:** prospective; biological image archives not yet decoded  
**Primary public resource:** BioSR v9, doi:10.6084/m9.figshare.13264793.v9  
**Analysis unit:** a registered low-resolution/high-resolution acquisition pair nested within a unique reference field  
**Scope:** measurement support, not image restoration or biological inference

## Question and falsifiable claim

This experiment asks whether an input-only NOSTOS validity contract can identify
when a requested structural measurement made from a lower-quality image will
agree with the same frozen measurement made from its registered high-resolution
reference. The high-resolution image defines an independent reference for the
measurement comparison. It is not treated as perfect biological truth.

The confirmatory claim is deliberately narrow:

> Across unseen biological structures and acquisition conditions, the complete
> NOSTOS contract reduces silent-invalid structural measurements at useful
> coverage relative to ordinary acquisition QC, optical sampling rules,
> perturbation stability alone and leave-one-component-out contracts.

The claim is false if the complete contract fails any primary gate. A failed
experiment will remain in the evidence bundle and will not be repaired by
changing tolerances, excluding an unfavorable structure or redefining the unit.

## Prospective data roles

The official BioSR v9 record contains paired lower-resolution and GT-SIM images
for four biological structures, nine photon levels and two upscaling factors.
Only the small official acquisition-conditions workbook was opened before this
protocol was locked. It reports 488-nm excitation, 62.6-nm sampling for the raw
SIM reference and upscaling factors of two for CCPs, ER, microtubules and linear
F-actin and three for nonlinear F-actin.

The roles are frozen by archive rather than chosen after inspecting images:

| Archive | Role | Permitted use before threshold lock |
| --- | --- | --- |
| CCPs | Development | Score construction and software debugging |
| ER | Development | Score construction and threshold calibration |
| Microtubules | Internal confirmation | Integrity verification only |
| F-actin, linear SIM | Internal confirmation | Integrity verification only |
| F-actin, nonlinear SIM | Threefold-resolution stress confirmation | Integrity verification only |

Confirmation archives may be downloaded and byte-hash verified before the
threshold lock, but their member names, pixels, image dimensions, intensity
summaries and measurements must not be read. The source manifest records exact
Figshare file identifiers, byte counts and MD5 digests.

An external acquisition-family confirmation using SR-CACO-2 is secondary. It
may be indexed only after the BioSR score formula and threshold receipt is
locked. The external result cannot rescue a failed BioSR primary result and will
be reported separately because its license and experimental hierarchy differ.

## Pairing and independence

Archive member names will be parsed using rules written from the development
archives. A pair must have one lower-resolution input and one registered
high-resolution reference with an unambiguous shared field identifier. Files
that cannot be paired without manual interpretation are reported and excluded
before measurement. Duplicate references are identified by SHA-256 of decoded,
dtype-preserving pixels. All lower-resolution conditions sharing a reference
hash belong to the same reference-field cluster.

No image patch, photon condition or endpoint is called an independent
biological replicate. Inference resamples reference-field clusters within
structure. If the repository lacks donor, cell or experiment identifiers, the
analysis is explicitly technical and makes no population-level biological
claim.

Development fields are split without using measurement error. The first 64 bits
of `SHA256("BioSR-v9|" + structure + "|" + reference_group_id)` are reduced
modulo four. Remainders 0 and 1 are score-design fields; remainders 2 and 3 are
threshold-calibration fields. Confirmation structures are never used to fit a
weight, normalize a component, select an endpoint or choose a threshold.

## Frozen measurements

Every image is analyzed in physical coordinates. The reference spacing is
0.0626 micrometres. The effective lower-resolution spacing is reference spacing
multiplied by the declared upscaling factor. If the deposited lower-resolution
array has already been interpolated to the reference grid, its stored sampling
and its effective optical sampling are retained separately; interpolation never
creates physical support.

The requested physical scales are 0.5008, 0.7512, 1.0016, 1.5024 and 2.0032
micrometres. A scale is input-supported only when represented by at least four
effective lower-resolution samples. This makes the smallest scale unsupported
for the threefold nonlinear-SIM condition by design.

The frozen endpoint families are:

1. Scale-resolved axial orientation and coherency from the structure tensor.
2. Global Fourier anisotropy, angular entropy and characteristic scale.
3. Normalized Hessian blob- and tube-response curves and their winning scales.
4. Normalized horizontal and vertical variogram curves and estimated ranges.

No structure-specific classifier, learned restoration model, disease label or
biological outcome is used. Blob and tube coordinates are calculated for every
eligible image rather than selected according to the specimen name. Network
measurements are not evaluated in BioSR because the record does not provide a
reference mask; the existing public-bone mask benchmark remains a separate
module test.

## Reference eligibility and invalidity

The reference is used only to define evaluation eligibility and error. It is
never available to the support contract.

An orientation coordinate is reference-eligible when reference coherency is at
least 0.15 and its maximum axial drift under the frozen mild probes is at most
5 degrees. Scalar reference coordinates must drift by at most 0.10 after robust
normalization. A response curve must have normalized energy above 1e-6. Cases
that fail reference eligibility are labeled `reference_unsupported`, not valid
or invalid, and are excluded from selective-risk denominators while their count
is retained.

For eligible cases, a lower-resolution emission is silently invalid when it is
accepted by a contract but exceeds its endpoint tolerance:

| Endpoint | Invalidity tolerance |
| --- | ---: |
| Axial orientation | absolute circular error >10 degrees |
| Tensor coherency | absolute error >0.15 |
| Fourier anisotropy | absolute error >0.15 |
| Fourier angular entropy | absolute error >0.10 |
| Fourier characteristic scale | relative error >0.25 |
| Normalized Hessian response curve | normalized L2 distance >0.25 |
| Hessian winning scale | absolute log2 scale ratio >0.50 |
| Normalized variogram curve | normalized L2 distance >0.25 |
| Variogram range | relative error >0.50 |

The paired image registration is audited before endpoint comparison using phase
correlation on band-limited images. A pair requiring more than two effective
lower-resolution pixels of residual translation, or showing a registration peak
ratio below the frozen implementation threshold, is `pair_registration_failed`.
Registration failure is not counted as successful abstention by NOSTOS because
the support contract sees only the lower-resolution input; it is a dataset
eligibility failure reported separately.

## Input-only support contract

The contract receives only the lower-resolution image, declared sampling,
requested endpoint and requested physical scale. It produces an endpoint-level
risk score and named reasons. Hard prerequisites are finite data, calibration,
adequate image extent and at least four effective samples per requested scale.

The complete score is the maximum of four normalized evidence components:

1. **Acquisition support:** robust dynamic range, endpoint fraction,
   contrast-to-residual and normalized Tenengrad focus.
2. **Physical sampling support:** samples per requested scale and the declared
   diffraction/sampling limit.
3. **Mild-perturbation stability:** agreement after rotations of plus/minus 3
   degrees, 0.5-pixel Gaussian blur, a one-pixel translation and gamma 0.9/1.1.
   Rotation comparisons are made in specimen coordinates.
4. **Cross-scale/estimator agreement:** adjacent-scale response smoothness and,
   for direction, agreement between tensor and Fourier axial estimates when
   both are supported.

Component normalization is designed on the score-design half of CCP and ER.
No endpoint-error label may enter the component value itself. Only the final
acceptance threshold is selected from the threshold-calibration half. The
highest-coverage threshold whose 95% field-cluster bootstrap upper bound on
silent-invalid risk is at most 0.15 and whose point risk is at most 0.10 is
selected. If no threshold exists, the contract is locked as `no_operating_point`
and confirmation still runs without inventing a substitute.

## Comparators and ablations

All conditions use the identical lower-resolution measurement estimator and the
identical reference definition. They differ only in validity behavior:

- `always_emit`: every eligible computation is emitted.
- `conventional_acquisition_qc`: dynamic range, saturation, focus and residual
  noise only.
- `optical_sampling_only`: calibration, effective samples per scale and
  diffraction support only.
- `perturbation_stability_only`: mild-probe agreement only.
- full contract without acquisition QC.
- full contract without physical sampling.
- full contract without perturbation stability.
- full contract without cross-scale/estimator agreement.

Risk-coverage curves are generated by ranking endpoint-level scores. Point
comparisons use the exact number of accepted reference-field clusters selected
by the complete contract; ties are resolved by the stable pair identifier, not
by outcome. Always-emit risk is reported at coverage one and as the horizontal
nonselective baseline.

## Primary analysis and frozen success gates

The primary estimand is macro-average area under the field-cluster
risk-coverage curve (AURC) across eligible structure-by-endpoint strata in the
three BioSR confirmation archives. Each stratum contributes equal weight.
Uncertainty is obtained from 10,000 stratified reference-field bootstrap draws
using seed 26082801. All technical conditions and endpoints remain nested in
their reference field.

The complete contract supports the confirmatory claim only if every gate passes:

1. Overall confirmation coverage is at least 0.80.
2. Coverage is at least 0.70 in every eligible structure-by-endpoint stratum.
3. Point silent-invalid risk is at most 0.10 and its field-bootstrap upper 95%
   bound is at most 0.15.
4. Macro AURC is at least 20% lower than the strongest prespecified comparator
   or leave-one-component-out ablation.
5. The paired bootstrap 95% interval for that AURC reduction excludes zero.
6. The complete contract has no higher matched-coverage risk than the strongest
   comparator in any endpoint family.
7. Risk is nondecreasing across ordered support-score quintiles in at least 80%
   of eligible strata.
8. All source, pairing, exclusion, measurement and bootstrap receipts reproduce
   in a clean environment from one documented command.

No gate is dropped because a reference structure is difficult. A stratum with
fewer than 20 reference-field clusters is reported as underpowered and makes
the full primary claim fail rather than silently disappearing.

## Secondary analyses

Secondary analyses report performance by photon level, upscaling factor,
endpoint and structure; continuous LR-versus-reference errors; accepted-case
calibration; runtime; reference-eligibility rate; and named abstention reasons.
These analyses cannot rescue a failed primary result.

After the BioSR threshold is locked, SR-CACO-2 may test unchanged transfer to a
real multiresolution confocal acquisition family. Wells and experiments, not
patches, are the resampling units whenever identifiers are available. This
external confirmation is separately labeled because it is not part of BioSR and
uses a CC BY-NC-SA license.

## Claims prohibited regardless of result

This protocol cannot establish diagnostic accuracy, treatment benefit,
mechanical competence, intraoperative utility, universal biological meaning,
segmentation validity, image-restoration quality or that GT-SIM is perfect
biological truth. Passing would support a calibrated measurement-support
contract for the tested structural coordinates and acquisition families.

