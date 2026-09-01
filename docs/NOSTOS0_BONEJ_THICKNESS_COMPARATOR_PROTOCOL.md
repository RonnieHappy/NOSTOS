# Frozen BoneJ thickness comparator protocol

**Protocol:** `nostos-bonej-thickness/1.0`  
**Frozen:** 27 August 2026, before installing or executing BoneJ  
**Data:** eight public 100³ trabecular-bone masks from Zenodo record 11061947

## Rationale

The archived IPL maps are an external reference but do not establish cross-software reproducibility. This protocol compares NOSTOS with the independently maintained BoneJ/ImageJ implementation. BoneJ defines local thickness as the diameter of the largest sphere that fits within the object and contains the evaluated point.

## Frozen execution

The exact eight binary NIfTI masks already used by `nostos-external-bone/1.0` are converted losslessly to 8-bit TIFF stacks with foreground 255. BoneJ 1.4.3 is executed in a checksum-recorded Fiji distribution using its `Thickness` command with trabecular thickness enabled, spacing disabled and masking enabled. The masks have effectively isotropic spacing; the mean of the three NIfTI spacings is assigned as the ImageJ pixel width, height and depth. Maximum relative axis deviation is recorded and must remain below 0.1% because BoneJ Thickness does not support anisotropic voxels.

For each case, the BoneJ foreground mean thickness is compared with the NOSTOS mean and the archived IPL reference mean. No case or option may be changed after execution.

## Gates

1. All eight checksum-matched masks execute without loss.
2. Maximum spacing anisotropy is below 0.1%.
3. NOSTOS-versus-BoneJ casewise concordance correlation coefficient is at least 0.85.
4. Median absolute relative NOSTOS-versus-BoneJ difference is at most 15%.
5. NOSTOS is not materially farther from BoneJ than the archived IPL reference: the mean absolute-error difference is at most 0.02 mm.
6. Fiji, Java, ImageJ and BoneJ versions and binary hashes are recorded.

The comparator can validate numerical concordance for this definition and archive. It cannot establish scanner transfer, segmentation validity, biological accuracy or universal equivalence among all thickness implementations.
