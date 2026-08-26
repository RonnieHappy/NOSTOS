# NOSTOS-0 cartilage-domain response validation

## Status

**Exploratory validation with unreviewed ROI proposals.** These results cannot replace independent cartilage-mask validation.

The frozen spectral, tensor, Hessian and spatial response modules were applied to the first lexicographically selected Safranin-O section from 90 medial and 87 lateral public specimens. All inference and prediction remained at the participant/specimen level. Medial features were tested against medial outcomes and lateral features against lateral outcomes. PLM was evaluated medially only.

## Processing

| Site | Available sections | Successful sections with outcomes |
|---|---:|---:|
| Medial | 90 | 90 |
| Lateral | 87 | 87 |

Cartilage-dominant tiles were selected with the existing deterministic stain-aware proposal. This proposal remains weak supervision rather than a reviewed reference mask. Hessian blob/tube/sheet responses were retained at 2-, 4- and 8-pixel physical scales. Directional variograms were retained at 2-, 4-, 8- and 16-pixel separations.

## Participant-level associations

After family-wise Benjamini–Hochberg correction, the strongest associations included:

| Site | Outcome | Response | Spearman ρ |
|---|---|---|---:|
| Lateral | HHGS | Angular entropy | −0.466 |
| Lateral | OARSI | Angular entropy | −0.394 |
| Medial | HHGS | Angular entropy | −0.381 |
| Lateral | HHGS | Characteristic frequency | −0.363 |
| Lateral | HHGS | FFT anisotropy | 0.347 |
| Medial | HHGS | Hessian tube response, 8 px | 0.317 |
| Lateral | OARSI | FFT anisotropy | 0.310 |
| Medial | HHGS | Vertical variogram, 16 px | 0.263 |

The Hessian and variogram findings are incremental structural correlates, not demonstrated tissue mechanisms. Fissures, boundaries, cell clusters and mask errors may contribute to these responses.

## Repeated nested prediction

Mean out-of-fold R² across ten repeated five-fold outer validations:

| Site/outcome | FFT | Complete response geometry | Best tested family |
|---|---:|---:|---:|
| Medial HHGS | 0.066 | 0.048 | 0.076, without Hessian |
| Lateral HHGS | 0.063 | 0.045 | 0.070, without spatial |
| Medial OARSI | −0.032 | −0.028 | 0.001, without spatial |
| Lateral OARSI | 0.022 | 0.005 | 0.022, FFT |
| Medial PLM | −0.001 | −0.043 | −0.001, FFT |

The complete concatenated geometry did not improve prediction over FFT. The data therefore reject any claim that concatenating every NOSTOS response creates a generally superior cartilage score. The valid platform claim is narrower: NOSTOS measures the same calibrated structural axes across domains, while each domain requires prespecified selection and biological validation of relevant responses.

## Interpretation

The cartilage application continues to support angular spectral entropy as its strongest repeatable channel. Hessian tube response and spatial heterogeneity provide additional candidate measurements, but neither currently establishes sufficient incremental prediction to replace or materially strengthen FFT.

This negative result changes platform development in three ways:

1. NOSTOS will preserve response curves without forcing them into one universal scalar.
2. Domain adapters must prespecify eligible modules and meanings.
3. Module inclusion will be justified by ground-truth recovery or incremental external validity, not by visual appeal or feature availability.

## Reproduction

```powershell
uv run nostos batch manifests/dataset_manifest.json --output outputs/universal_cartilage/safo_medial.csv --stain SafO --site Medial --workers 4
uv run nostos batch manifests/dataset_manifest.json --output outputs/universal_cartilage/safo_lateral.csv --stain SafO --site Lateral --workers 4
uv run nostos validate-cartilage --medial outputs/universal_cartilage/safo_medial.csv --lateral outputs/universal_cartilage/safo_lateral.csv --scores manifests/metadata.scores_raw.csv --output outputs/external-cartilage-v1
```

Machine-readable associations, bootstrap confidence intervals, FDR values, repeated prediction results and provenance are stored under `outputs/external-cartilage-v1/`.
