# Synthetic physical-truth repair lineage: v2.0 to v2.6

## Purpose

This lineage prevents the successful v2.6 confirmation from concealing the
failed frozen experiments that produced it. Every failed receipt remains part
of the evidence record. Thresholds or estimators selected after a failure were
developed only on opened cases and then tested on a new disjoint confirmation.

| Version | Decision | Frozen failure | Consequence |
|---|---|---|---|
| v2.0 | fail | Hessian, network, spatial and tensor gates | Exposed scale-support, network-discretization and directional-response defects; no claim promoted |
| v2.1 | fail | Hessian classification and spatial gates | Corrected network, organization, controls, perturbations and thickness passed; unresolved endpoints remained blocked |
| v2.2 | fail | Hessian classification and rotation equivariance | Simple support restrictions did not solve the spatial boundary effect |
| v2.3 | fail | Gradient-ratio accuracy and isotropic behavior | Raw gradient moment was not safe as an always-emitted estimator |
| v2.4 | fail | One supported Hessian error and rotation equivariance | Stability gating improved spatial risk but did not fully address scale and boundary support |
| v2.5 | fail | Gradient-ratio accuracy and rotation equivariance | Hessian passed after a 5-sample scale floor; spatial p95 error and accepted risk remained just outside the frozen gates |
| v2.6 | **pass** | None of 14 gates | Boundary-robust axis estimation plus a physical characteristic-span floor passed disjoint confirmation and independent audit |

## Immutable receipt identities

| Version | Receipt | Content SHA-256 |
|---|---|---|
| v2.0 | `outputs/nostos0-synthetic-physical-truth-v2/validation.json` | `3ff64e61b88139d9a750bdb58f1a8d917915a375792572129b66fc8e5fc90657` |
| v2.1 | `outputs/nostos0-synthetic-physical-truth-v2-1-confirmation/validation.json` | `8377fd7f29bf31c65a787624d43d9ec4c82be78ece5993da54ae45b9e39e79e2` |
| v2.2 | `outputs/nostos0-synthetic-physical-truth-v2-2-confirmation/validation.json` | `f376aa91016f8c93a19b1a9dcf2eef7bf4e78669e8293ba93f4836e04ce5dae2` |
| v2.3 | `outputs/nostos0-synthetic-physical-truth-v2-3-confirmation/validation.json` | `1e87bbb52a310c42e7b50a711735cd058581d6a4d68949c271275622afd89138` |
| v2.4 | `outputs/nostos0-synthetic-physical-truth-v2-4-confirmation/validation.json` | `e43f26d1618ece21c9dc621dc5a6f36fd1b19fe6de11b81404b084df505a8a6d` |
| v2.5 | `outputs/nostos0-synthetic-physical-truth-v2-5-confirmation/validation.json` | `d5d5feb16dbcd37ba92ca4dc12b68781f11af7107936c0c7bda7c5f993b5e3a8` |
| v2.6 | `outputs/nostos0-synthetic-physical-truth-v2-6-confirmation/validation.json` | `572f237e2ca7133597f2362d61390f17e2a401e2e1ef3c967ff2e73e64187cde` |

## What changed at v2.6

The decisive repair was estimator-level, not a cosmetic threshold relaxation.
Long-correlation random fields contain too few independent structures in small
fields for stable anisotropy recovery. v2.6 therefore:

1. computes covariance from physical gradients;
2. preserves the full-field ratio as the reported anisotropy magnitude;
3. uses a Hann-tapered covariance for the axial direction;
4. requires full-field and tapered ratios of at least 1.65 before emitting an
   axis;
5. preserves the v2.4 stability ceiling of 0.20; and
6. requires at least 2.25 measured characteristic spans before emitting the
   spatial response.

The development artifact is
`outputs/nostos0-spatial-estimator-development-v2-6/development.json` with
SHA-256
`9f425626e7f86a9e86ef1bbcbaab5b4ef814d31a9aa729b218d4b9dac26e7893`.
The disjoint confirmation was not used to choose these rules.

## Release integration

The validated v2.6 responses are wired into the public universal analyzer. A
calibrated 2-D input now receives conditional v2.6 Hessian and spatial values,
stability and characteristic-span diagnostics, and explicit abstention reasons
when support is insufficient. Conditional endpoints were deliberately excluded
from legacy fixed-width comparator fingerprints; they are never silently
zero-filled or imputed.

The post-integration suite completed with **432 passed, 4 skipped, 0 failed**.
The four skips require Torch and concern optional segmentation tests. The
machine-readable integration receipt is
`outputs/nostos0-v2-6-integration-audit/integration_audit.json`, and the JUnit
record is `outputs/nostos0-v2-6-integration-audit/pytest.xml`.

## Interpretation

This sequence is evidence of failure-driven method development, not seven
independent positive validations. Only v2.6 is the positive frozen confirmation
for the repaired Hessian/spatial contract. The earlier positive v2.1 modules
and the v2.6 repaired endpoints together close most of the advertised analytic
physical-truth registry, but biological reference standards and external
acquisition transfer remain separate validation requirements.
