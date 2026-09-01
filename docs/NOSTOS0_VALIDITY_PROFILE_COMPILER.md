# NOSTOS validity-profile compiler

## Purpose

The validity-profile compiler turns paired acquisition/reference measurements into a frozen, auditable rule for deciding when a structural endpoint is supported. It is a computational calibration tool. It does not restore images, infer tissue identity, learn biological labels, or establish clinical utility.

The workflow deliberately uses two commands:

```powershell
nostos compile-validity-profile development_rows.jsonl `
  --config protocol.locked.json `
  --output compiled-profile

nostos audit-validity-profile confirmation_rows.jsonl `
  --profile compiled-profile\validity_profile.json `
  --output confirmation-audit
```

Compilation and confirmation are separate file operations. A confirmation command refuses a profile with a missing or invalid content hash, no development operating point, an unsupported schema, or any overlapping independent group.

## Evidence-row contract

Each JSONL row is one endpoint-level comparison from a paired acquisition and reference. Required fields are:

| Field | Meaning |
| --- | --- |
| `case_id` | Unique endpoint-level identifier |
| `reference_group_id` | Independent field, specimen, or acquisition group used for all splitting and bootstrap resampling |
| `endpoint_family` | Measurement family with its own monotone risk map |
| `pair_registration_eligible` | Whether acquisition and reference can support paired evaluation |
| `reference_eligible` | Whether the reference itself supports the endpoint |
| `invalid` | Reference-only indicator that endpoint error exceeds the frozen tolerance |
| `scores` | One or more deployment-available, input-only support scores |
| `hard_abstention_reasons` | Input-only reasons an estimator must not emit a value |

Rows may also retain endpoint error, tolerance, input and reference measurements, perturbation evidence, and acquisition metadata for audit. Reference-derived fields are never permitted inside a deployment score.

## Statistical safeguards

- Cross-fitting is grouped by `reference_group_id`; no patch, scale, endpoint, or repeated acquisition crosses folds independently of its group.
- Sparse endpoint families use the largest feasible fold count up to the protocol maximum, with at least two independent groups required.
- Candidate scores use identical family-specific folds.
- Each endpoint family receives a separate quantile-binned Jeffreys-smoothed isotonic risk map.
- The operating point is selected from out-of-group predictions only.
- Selection maximizes coverage subject to predeclared observed-risk, clustered upper-risk, and minimum-coverage gates.
- Confirmation applies serialized maps without fitting or threshold changes.
- Risk-coverage uncertainty and method contrasts resample the independent group, not endpoint rows.
- Ordinary acquisition QC and leave-one-component-out ablations receive only their own hard gates; they do not inherit NOSTOS gates.

## Output files

Compilation writes:

- `validity_profile.json`: serialized risk maps, operating point, group receipt, gates, and content hash;
- `development_audit.json`: cross-fitted metrics and every evaluated operating threshold;
- `development_scored.jsonl`: row-level out-of-group risks and fold assignments.

Confirmation writes:

- `confirmation_audit.json`: primary operating-point performance, matched-count acquisition-QC comparison, risk-coverage AUC contrast, group bootstrap interval, and every frozen gate;
- `confirmation_scored.jsonl`: row-level risks from every frozen score and ablation.

Hierarchical support is a separate composable layer:

```powershell
nostos compile-conditional-support development_rows.jsonl `
  --config conditional_protocol.locked.json `
  --base-profile compiled-profile\validity_profile.json `
  --output conditional-profile

nostos audit-conditional-support confirmation_rows.jsonl `
  --config conditional_protocol.locked.json `
  --base-profile compiled-profile\validity_profile.json `
  --conditional-profile conditional-profile\conditional_support_profile.json `
  --output conditional-confirmation
```

The conditional compiler learns support only from declared, input-known cell
coordinates. Typical dimensions are acquisition family, capture level,
endpoint family and requested measurement scale. Every cell must pass its own
minimum accepted-row, independent-group, observed-risk and clustered-risk
requirements. Missing, unseen, underrepresented or unsafe cells hard-abstain.
The base profile is not refit.

`audit-conditional-support` additionally writes
`finite_sample_uncertainty.json`. This file reports an exact interval across
emitted rows and a separate exact interval for the proportion of independent
groups with any emitted failure. The row interval is descriptive when rows are
nested. A zero-width percentile cluster bootstrap after zero observed events is
never described as a population upper confidence limit.

All JSON is deterministic and rejects NaN. File receipts contain SHA-256 hashes rather than relying on local paths.

## Calibration and abstention

A profile must state its calibration domain. If pixel or voxel spacing is absent, physical-unit endpoints are ineligible. If an input-only score requires acquisition metadata such as independent capture count, that metadata becomes a deployment precondition. Missing preconditions cause abstention; the compiler must not impute them from a tissue label or reference outcome.

## Extending to another dataset

An adapter for another paired public dataset needs to do only four things:

1. checksum-lock the source and assign complete independent groups before confirmation decoding;
2. apply the same estimator to acquisition and reference while keeping the reference out of support scoring;
3. emit the evidence-row contract with explicit calibration and validity flags;
4. call the generic compile and audit commands without dataset-specific changes to the compiler.

The FMD adapter is the worked hierarchical example. Its widefield v1.3 profile
passed pooled confirmation while every accepted error concentrated in one
average-of-8 by 8-pixel cell. The frozen v1.4 conditional layer excluded that
cell and passed one-shot confirmation on four new FOVs. BioSR remains an
independent evidence family; its historical result can be migrated to the same
row contract without changing the locked scientific result.
