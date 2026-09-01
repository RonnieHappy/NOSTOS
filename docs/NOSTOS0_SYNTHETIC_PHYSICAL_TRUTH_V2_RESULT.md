# NOSTOS-0 synthetic physical-truth benchmark v2: frozen result

**Status:** failed; independently audited  
**Protocol:** `docs/NOSTOS0_SYNTHETIC_PHYSICAL_TRUTH_V2_PROTOCOL.md`  
**Primary receipt:** `outputs/nostos0-synthetic-physical-truth-v2/validation.json`  
**Independent audit:** `outputs/nostos0-synthetic-physical-truth-v2-audit/audit.json`

## Decision

The comprehensive benchmark failed four of eleven scientific gates. This is a
material correction to the earlier single-case synthetic pass. The v1 receipt
remains valid for its narrow tested cases, but it cannot support general module
claims across physical scale and anisotropic sampling.

## Passed modules and behaviors

| Endpoint | Frozen result | Gate |
|---|---:|---|
| FFT orientation | median error 0.00004°, p95 0.867° | Pass |
| FFT wavelength | median relative error 0.0077, p95 0.0733 | Pass |
| Hessian winning scale | median relative error 0.000, p95 0.500 | Pass |
| Local thickness | median relative error 0.000, p95 0.1019; anisotropic p95 0.1007 | Pass |
| Orientation perturbations | 8/8 within frozen error limits or abstained | Pass |
| Mask-error directionality | 6/6 erosion/dilation tests behaved in the expected direction | Pass |
| Explicit abstention semantics | 4/4 support-boundary challenges correct | Pass |
| Independent repeat | byte-identical; SHA-256 `3ff64d1ffc71527c68475b76a9e034ab420bbe5448048f7f21068a67ec74a0e9` | Pass |

## Failed gates

### Tensor orientation at the sampling boundary

Median maximum case error was 0.168°, but p95 was 2.921° against the frozen
2.5° limit. All four cases above 2.5° were 8-µm wavelengths sampled at
1.5 µm/pixel (5.33 pixels per cycle). Coherency remained near one, showing that
high coherence alone does not detect discretization-induced angular bias.

The FFT support wrapper also abstained on all five angles in this condition
because the residual-based SNR proxy interpreted the high-frequency programmed
signal as noise. This omission was not a numbered v2 gate, but it is a genuine
validity defect and must be repaired explicitly rather than ignored.

### Hessian morphology at small radius and coarse axial sampling

Balanced accuracy was 0.833 and anisotropic accuracy 0.778. Blob recall was
0.50, while tube and sheet recall were 1.00. Three analytic blobs were called
tubes:

- radius 4 µm at 1 × 1 × 1 µm spacing;
- radius 4 µm at 1 × 1 × 2 µm spacing;
- radius 6 µm at 1 × 1 × 2 µm spacing.

This exposes a scale-support boundary and/or eigenvalue-shape defect in the
current 3D classifier. These cases cannot be advertised as supported.

### Network truth definition and coarse sampling

All survival curves were monotone, but fragmentation-threshold p95 relative
error was 0.40 against the 0.35 gate. The protocol defined continuous failure
as the first threshold *above* the programmed half-width. For a continuous open
set, spanning support is already lost at the half-width. The truth registry
therefore encoded a conservative but physically incorrect 1.25× half-width
target. This is a protocol-ground-truth error, not evidence that the observed
2.4-, 4.0- and 6.0-µm fine-grid failures are wrong. A corrected protocol must
freeze half-width as the analytic target and retain a spacing-dependent error
gate for coarse grids.

### Spatial isotropy

Programmed-versus-recovered anisotropy ordering was strong (Spearman ρ=0.921)
and median relative ratio error was zero. The all-fields isotropy gate failed
because one finite stochastic field produced a discrete-lag range ratio of 1.5.
The current “first lag above sill fraction” estimator is too quantized for an
individual-field isotropy guarantee. A repair must improve the estimator or
predeclare replicate-aggregated inference on new seeds; it cannot merely widen
the interval after observing this field.

## Integrity controls

The audit independently reproduced protocol and repeat hashes, all 160 case
counts, case-ID uniqueness, angular and relative-error arithmetic, morphology
accuracy, thickness error, monotonic network survival, spatial anisotropy and
every stored summary metric. The audit passed while confirming that the
scientific benchmark status is `fail`.

## Repair boundary

The failed v2 identities are now development data. Any repair must be developed
only on these opened cases and tested on a newly frozen, disjoint set of angles,
wavelengths, radii, spacings and random-field seeds. The v2 result must remain in
the evidence ledger beside the repaired confirmation.
