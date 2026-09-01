# Frozen STARE network confirmation protocol

**Protocol:** `nostos-stare-network-confirmation/1.0`  
**Frozen:** 27 August 2026, before downloading or inspecting STARE images or labels  
**Confirmation dataset:** official STARE vessel subset, 20 retinal images with AH and VK hand labels

## Locked method

The endpoint is the corrected network implementation developed after the failed HRF experiment. Euclidean distance to background-voxel centers is reduced by half the minimum sample spacing to approximate distance from the sampled foreground boundary. Twofold resampling uses the HRF-selected occupancy cutoff 0.25. No STARE result may change this definition.

The AH label is the primary reference. NOSTOS surviving-fraction and component-count curves are evaluated at relative physical thresholds 0, 2, 4 and 8 native pixels on the native mask and the twofold resampling. The pinned scikit-image 0.25.2 `skeletonize` comparator supplies skeleton length. VK labels provide a second-observer sensitivity analysis; observer disagreement is not treated as algorithm error.

## Gates

1. All 20 AH cases are processed without loss and all declared outputs are finite and monotone where required.
2. Median absolute native-versus-twofold surviving-fraction difference is at most 0.05 at every nonzero threshold.
3. Native-versus-twofold survival-area Spearman correlation is at least 0.85.
4. Native-versus-twofold skeleton-length Spearman correlation is at least 0.90.
5. Median absolute relative skeleton-length difference is at most 0.15.
6. AH-versus-VK native survival-area Spearman correlation is at least 0.80.
7. Source archive hashes, case identities, implementation versions and every case-level result are retained.

All gates must pass. The experiment supports reference-mask network stability only. It does not validate automatic vessel segmentation, diagnose retinal disease or establish universal topology invariance.
