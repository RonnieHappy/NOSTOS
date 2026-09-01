# NOSTOS-0 external trabecular-bone validation

## Status

**Preliminary external validation; not yet a generalization claim.**

NOSTOS-0 was evaluated on all eight public segmented human trabecular-bone micro-CT volumes in Zenodo record 11061947 having matched IPL thickness maps. Seven volumes are 100 × 100 × 100 voxels and one is 50 × 50 × 50 voxels, with approximately 17.4–17.6 µm isotropic spacing. These images were not acquired or annotated by the NOSTOS investigators.

## Frozen method

The NOSTOS measurement is the diameter of the largest supported sphere containing each foreground voxel. It is approximated over 32 logarithmically spaced physical-radius levels. At each level, centers supported by the calibrated Euclidean distance transform define a union of admissible spheres; previously unassigned foreground voxels receive the largest containing diameter.

The number and spacing of radius levels were frozen before examining the three-case aggregate results. The original twice-nearest-boundary distance was retained as a declared baseline. It is not local thickness because a voxel's largest containing sphere need not be centered at that voxel.

## Results

| Quantity | NOSTOS maximal-sphere result |
|---|---:|
| Volumes | 8 |
| Mean absolute bias / reference mean | 8.05% |
| Specimen-bootstrap 95% CI | 6.83–9.25% |
| Median voxelwise Spearman correlation | 0.927 |
| Mean voxelwise MAE | 0.0189 mm |
| Nearest-boundary baseline MAE | 0.0930 mm |
| Paired MAE reduction | 0.0741 mm |
| Exact one-sided Wilcoxon P | 0.00391 |

The earlier nearest-boundary proxy produced approximately 48% mean absolute relative bias, median voxelwise Spearman correlation of 0.65, and MAE of 0.092 mm. The external test therefore falsified the original proxy and justified replacing it with the maximal-sphere response.

## Interpretation limits

- Eight volumes from one archive do not establish external generalization.
- The archived map is a workflow reference, not error-free biological truth.
- Voxelwise observations are spatially dependent and are not treated as independent replicates.
- Eight independent volumes permit descriptive specimen-level uncertainty but remain underpowered for a broad equivalence claim.
- Broader validation requires the complete archive, a second acquisition source, and comparison with BoneJ/ORMIR-XCT under matched boundary conventions.
- Thickness agreement does not validate the spectral, tensor, topology, or spatial modules.

## Reproduction

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_bone_reference_subset.ps1
uv run nostos validate-bone --data <DATA_ROOT>\data\public\trabecular-bone-zenodo-11061947 --output outputs/external-bone-v1
```

The selection rule, file sizes and MD5 checksums are stored in `manifests/external_bone_subset.json`. The machine-readable results and SHA-256 hashes of analyzed inputs are stored in `outputs/external-bone-v1/external_bone_validation.json`.

## Source

Kuczynski M. *MicroCT Trabecular Bone Samples for Trabecular Thickness and Separation Measures*. Zenodo, 2024. DOI: 10.5281/zenodo.11061947. CC BY 4.0.
