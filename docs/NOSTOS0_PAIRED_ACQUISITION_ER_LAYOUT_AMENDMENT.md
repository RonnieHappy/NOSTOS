# NOSTOS-0 ER archive-layout amendment

**Amendment:** `nostos-paired-acquisition-er-layout/1.0`  
**Parent protocol:** `nostos-paired-acquisition-support/1.0`  
**Timing:** written after listing ER member names and MRC headers, before decoding
any ER biological pixels

## Observed layout

The verified BioSR v9 `ER.zip` archive contains 68 cell folders. Each cell has
six matched entries in each of three subdirectories:

- `RawSIMData/RawSIMData_level_01..06.mrc`, each 502 × 502 × 9;
- `GTSIM/GTSIM_level_01..06.mrc`, each 1004 × 1004 × 1; and
- `RawGTSIMData/RawGTSIMData_level_01..06.mrc`, each 502 × 502 × 9.

This differs from CCPs, where nine lower-resolution conditions share one
per-cell `SIM_gt.mrc` reference.

## Official-code confirmation

The official authors' `DL-SR` repository was inspected at commit
`7f9c8865aea1e6a067d055d419b19a459e7102c1`. Both
`DataAugumentation_ForTest.m` and `DataAugumentation_ForTrain.m` sort ER
`RawSIMData_level_*` and `GTSIM*` files and pair them at the same list index.
They create the widefield input by averaging or summing the nine raw frames;
normalization makes those operations equivalent up to a constant factor. The
repository code does not use `RawGTSIMData` as the lower-resolution input.

## Frozen ER decision

For ER level `j`, the benchmark pair is:

`mean(RawSIMData/RawSIMData_level_j, axis=frame) → GTSIM/GTSIM_level_j`

The mean is calculated in float64. `RawGTSIMData` and `GT_all.mrc` are excluded
from measurement. The input grid and effective sampling are 0.1252 μm and the
reference grid is 0.0626 μm.

The six matched levels are nested in the cell folder. The cell is the bootstrap
cluster and highest available repository unit; the levels are not promoted to
independent biological replicates. They retain the neutral label
`repository_level_01..06` because no photon-count mapping was found in the
archive or official preprocessing script.

This amendment changes only archive parsing and pairing. It does not change the
frozen endpoints, errors, support components, tolerances, comparators or gates.

