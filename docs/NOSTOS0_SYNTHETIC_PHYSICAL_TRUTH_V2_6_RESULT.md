# NOSTOS-0 synthetic physical-truth confirmation v2.6

**Decision:** pass  
**Confirmation receipt:** `outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json`  
**Receipt content SHA-256:** `572f237e2ca7133597f2362d61390f17e2a401e2e1ef3c967ff2e73e64187cde`  
**Independent audit:** `outputs/nostos0-synthetic-physical-truth-v2-6-audit/audit.json`  
**Audit file SHA-256:** `4bec5fb5ccebf233df61e34908493d1a53d6940ace0e0f9761bccf257ec9f501`

## What was tested

The frozen confirmation tested calibrated Hessian morphology and the v2.6
boundary-robust gradient response on analytic images not used to select the
v2.6 rules. The confirmation contained:

- 36 blob, tube and sheet cases using radii or thicknesses of 8, 10 and
  12 µm across four pixel spacings;
- 270 random-field cases spanning 192-, 288- and 384-pixel fields,
  correlation lengths of 20, 28 and 36 µm, five programmed anisotropy ratios
  and six random seeds; and
- 24 equivariance cases subjected to a 39° rotation and 0.82× resampling.

The v2.6 spatial response preserves the full-field physical-gradient
eigenvalue ratio, estimates direction from a Hann-tapered covariance, requires
both directional ratios to exceed the frozen axis floor and abstains when the
field contains fewer than 2.25 measured characteristic spans. The stability
threshold remained 0.20. These choices were locked in the development receipt
before the confirmation cases were evaluated.

## Frozen result

| Endpoint | Result | Gate |
|---|---:|---:|
| Hessian accepted coverage | 24/36 (66.7%) | pass |
| Hessian balanced accuracy among accepted cases | 1.000 | pass |
| Hessian accepted-invalid risk | 0/24 (0%) | pass |
| Hessian median / p95 scale error | 0.125 / 0.500 | pass |
| Spatial accepted coverage | 215/270 (79.6%) | pass |
| Spatial anisotropic coverage | 179/216 (82.9%) | pass |
| Spatial ratio Spearman correlation | 0.9436 | pass |
| Spatial median / p95 relative error | 0.0595 / 0.1781 | pass |
| Spatial accepted-invalid risk | 6/215 (2.79%) | pass |
| Isotropic median / p95 emitted ratio | 1.135 / 1.265 | pass |
| Isotropic axis abstention | 100% | pass |
| Programmed ratio ≥2 axis retention | 100% | pass |
| Low-span rejection | 32/32 (100%) | pass |
| Equivariance accepted coverage | 23/24 (95.8%) | pass |
| Rotation p95 ratio drift | 0.0629 | pass |
| Rotation p95 axial turn error | 0.277° | pass |
| Resampling p95 ratio drift | 0.00956 | pass |

All 14 frozen success gates passed. A second execution produced an identical
canonical payload. Complementing the invalidity labels left the computed
geometry hash unchanged, confirming that truth labels did not enter the
measurement path.

Coverage changed appropriately with finite field support: 48.9% at 192 pixels,
92.2% at 288 pixels and 97.8% at 384 pixels. This is a designed abstention
behavior, not missing data to be imputed.

## Independent audit

The independent auditor recomputed the receipt hash, source hashes, case
counts, every success gate, support logic, label-blindness check and repeat-run
identity. All 15 audit checks passed. The registered implementation SHA-256 is
`25b4237d0e896d770242fbfb088deaaa2d4089db8e75b56f2671ffe726f63b10`;
the evaluator SHA-256 is
`01f391f32b6568e741f85787f2e3f6adea17a46ec0d13e1127f4d011f87806e8`.

## Claim boundary

This experiment supports calibrated recovery and explicit finite-field
abstention for the tested analytic Hessian and two-dimensional spatial-gradient
responses. Earlier frozen synthetic programmes separately support the released
organization, thickness, corrected network and perturbation endpoints. It does
not validate segmentation, tissue identity, biological meaning, instrument
transfer, mechanics, diagnosis, clinical utility or intraoperative use. It is
also not a distribution-free risk guarantee: the 2.79% accepted-invalid rate is
an observed rate within this finite synthetic confirmation.

The v2.6 pass does not erase the failed v2.0–v2.5 receipts. Those failures and
the exact repair sequence are retained in
`docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_LINEAGE_V2_TO_V2_6.md`.
