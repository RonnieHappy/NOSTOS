# NOSTOS-0 BioSR tensor v7.1 nonlinear metadata amendment

The v7 nonlinear run stopped before pixel decoding because its frozen 0.0626 micrometre input spacing disagreed with every nonlinear MRC header. A complete header-only audit found one uniform nonlinear layout:

- 51 fields.
- 9 signal levels per field.
- 25 raw frames per level.
- 502 x 502 raw sampling grid.
- 1506 x 1506 `SIM_gt_a.mrc` reference grid.
- 0.0604000017 micrometres per raw pixel in every input header.
- 0.0201333333 micrometres per reference pixel in every primary-reference header.
- Exact 3x spacing and dimension ratios, with matching physical fields of view.

The BioSR record-level `imaging_conditions.xlsx` workbook states 0.0626 micrometres for nonlinear SIM. V7.1 does not hide this conflict. It uses the per-member MRC header calibration because it is acquisition-specific, uniform across all relevant files and internally consistent with both the declared 3x upscaling factor and physical field of view.

Only the nonlinear grid calibration changes. V7.1 carries forward unchanged:

- The eight cells selected under the v7 hash lock.
- All nine signal levels.
- `SIM_gt_a.mrc` as the sole claim-eligible reference.
- The five physical response scales.
- Tensor estimators and 36-bin axial distribution.
- Endpoint definitions and invalidity tolerances.
- Mild perturbations and coherence-only strong resolution margin.
- Every support threshold, comparator and decision gate.

The completed linear F-actin result remains under the original v7 lock and is not rerun. The v7.1 nonlinear result is combined with that linear result only after both receipts and their distinct lock lineages verify.

No nonlinear pixel array or endpoint outcome was decoded before this amendment and its lock were created.

