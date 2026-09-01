# Frozen structure-tensor upstream comparator protocol

**Protocol:** `nostos-structure-tensor-comparator/1.0`  
**Frozen:** 27 August 2026, before comparator outcome computation  
**Data:** previously opened PSHG-TISS unstained-breast confirmation cohort, 48 ROIs

This is a post-confirmation cross-software audit, not a new biological confirmation. The NOSTOS sigma-2 local ridge-orientation field is compared with scikit-image 0.25.2 `structure_tensor` and `structure_tensor_eigenvalues` at sigma 2 on the identical mean FSHG images. Eligibility remains frozen at polarization-fit R² ≥0.90, SNR ≥3, positive intensity and an eight-pixel border exclusion. The independently archived polarization direction plus the previously frozen 90° instrument-to-raster offset is the reference.

Both implementations are converted to the same axial ridge convention before error calculation. No sign or 90° correction may be selected from the comparator outcome.

## Gates

1. All 48 ROIs and at least one million eligible pixels are retained.
2. Both implementations return finite orientation at every eligible pixel.
3. NOSTOS median axial error is no more than 2° worse than scikit-image.
4. Median NOSTOS-versus-scikit-image axial disagreement is at most 10°.
5. ROI-median errors across implementations have Spearman correlation at least 0.75.
6. The upstream version and input manifest hash are recorded.

A pass establishes cross-software consistency of the frozen orientation field. It does not establish universal superiority or replace the pristine PSHG biological confirmation.
