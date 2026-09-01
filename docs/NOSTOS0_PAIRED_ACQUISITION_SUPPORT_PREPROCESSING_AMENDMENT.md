# NOSTOS-0 paired-acquisition preprocessing amendment

**Amendment:** `nostos-paired-acquisition-support-preprocessing/1.0`  
**Parent protocol:** `nostos-paired-acquisition-support/1.0`  
**Timing:** written after listing the CCP archive central directory and reading
MRC headers, before decoding any biological pixel array

## Reason for the amendment

The parent protocol correctly froze archive-level data roles, physical scales,
endpoints, invalidity tolerances and confirmatory gates. The official record did
not document the exact member layout needed to turn a deposited raw SIM stack
into a single lower-resolution image. The development archive was therefore
listed without extracting or decoding pixels.

The CCP archive contains 54 folders (`Cell_001` through `Cell_054`). Each folder
contains:

- `SIM_gt.mrc`: one 1004 × 1004 unsigned-16-bit reconstructed GT-SIM image;
- `RawSIMData_level_01.mrc` through `RawSIMData_level_09.mrc`: nine 502 × 502 × 9
  unsigned-16-bit raw SIM stacks representing the declared signal levels; and
- `RawSIMData_gt.mrc`: one additional 502 × 502 × 9 high-signal raw stack.

The archive also contains `GT_all.mrc`, a 54-section concatenation. Per-cell
`SIM_gt.mrc` files are used so pairing and provenance remain explicit.

## Frozen preprocessing decision

For each `RawSIMData_level_XX.mrc`, the NOSTOS lower-resolution input is the
pixelwise arithmetic mean of its nine raw illumination frames, calculated in
float64 and retained without deconvolution, learned restoration, clipping or
histogram matching. Averaging a complete SIM phase/orientation cycle removes
the illumination modulation while preserving a conventional widefield-like
observation. This construction is applied identically to every signal level and
structure.

`RawSIMData_gt.mrc` is excluded from the paired benchmark. It may contribute to
the deposited reference reconstruction and would therefore create avoidable
dependence between input and reference. `GT_all.mrc` is used only as an optional
byte/pixel consistency audit against the per-cell references.

One technical pair is:

`Cell_ID × signal-level_01..09: mean(RawSIMData_level_XX, axis=frame) → SIM_gt`

The cell folder is the reference-field cluster. Signal levels and endpoints are
nested technical cases. The signal number is retained as an ordinal label; no
photon count is inferred unless an official mapping is located and separately
recorded.

## Calibration and registration

The 502-to-1004 dimension ratio exactly matches the declared twofold upscaling
factor. The input grid and effective sampling are therefore both 0.1252 μm, and
the reference grid is 0.0626 μm. Measurements are made on each native grid in
physical coordinates. Resizing occurs only inside the registration eligibility
audit and never supplies measurement information or changes the declared input
support.

## Confirmation rule

No conclusion about the CCP member layout is projected onto a confirmation
archive without checking its headers after the development threshold is locked.
If confirmation layout requires a different preprocessing choice, that archive
is ineligible for the primary analysis rather than prompting a post hoc change.

