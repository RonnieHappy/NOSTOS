# NOSTOS cartilage mechanism-ablation report

## Scope

This analysis asks whether participant-level angular spectral entropy is robust
to cartilage-tile purity, boundary proximity, external-surface proximity,
proposal-defined voids, enclosed holes and extreme dark structures. It also
benchmarks FFT prediction against tissue geometry, optical density and
luminance. All compartments derive from unreviewed semantic proposals; this is
therefore an exploratory sensitivity analysis, not biological attribution.

The frozen Safranin-O cohort contains 90 medial and 87 lateral sections. All
sections processed successfully. Site-specific HHGS and OARSI outcomes were
used; PLM was evaluated medially only.

## Eligibility robustness

| Variant | Medial sections with tiles | Lateral sections with tiles | Median tiles, medial | Median tiles, lateral |
|---|---:|---:|---:|---:|
| Baseline, ≥72% cartilage | 90/90 | 87/87 | 138.5 | 130.0 |
| Strict, ≥95% cartilage | 90/90 | 87/87 | 110.0 | 103.0 |
| All-boundary erosion, 100 µm | 90/90 | 87/87 | 110.5 | 104.0 |
| All-boundary erosion, 250 µm | 89/90 | 84/87 | 80.5 | 74.0 |
| External-surface exclusion, 100 µm | 90/90 | 87/87 | 118.5 | 108.0 |
| External-surface exclusion, 250 µm | 90/90 | 85/87 | 96.0 | 79.0 |
| Extreme-dark-object exclusion, 25 µm | 90/90 | 87/87 | 77.5 | 68.0 |

Entropy–HHGS associations survive the strict-purity, erosion and external-
surface exclusions. For lateral HHGS, baseline entropy was ρ = −0.466 and the
100 µm external-surface result was ρ = −0.464. For medial HHGS, baseline was
ρ = −0.381 and the 250 µm external-surface result was ρ = −0.397. Paired
bootstrap intervals for baseline-versus-surface differences included zero.
Thus the association is not explained solely by tiles immediately adjacent to
the proposal-defined external surface.

## Dark-object sensitivity

The extreme-dark-object proxy removes cartilage eligibility within 25 µm of
the darkest 1% of proposal-class-1 pixels. It is an image-domain sensitivity
test, not a validated cell-cluster or lacunar segmentation.

For medial HHGS, entropy weakened from ρ = −0.381 to −0.274. The paired
baseline-minus-proxy difference was Δρ = −0.106 (bootstrap 95% CI −0.215 to
−0.003). Mean repeated nested-CV R² fell from 0.073 to 0.017. For lateral HHGS,
entropy remained associated (ρ = −0.429) and the paired difference interval
included zero. The site difference prevents a universal claim that the signal
is independent of dark cellular or lesion-related structures.

Proposal-class-4 and enclosed-hole exclusions were numerically identical to
baseline at the tile level. They are non-informative negative controls, not
evidence that fissures or voids are irrelevant.

## Conventional and incremental prediction

For medial HHGS, mean repeated nested-CV R² was 0.073 for FFT, 0.169 for the
geometry/optical-density family and 0.216 for their combination. For lateral
HHGS the corresponding values were 0.096, −0.048 and 0.160. For lateral OARSI
they were 0.048, −0.037 and 0.158. These results support complementary
information in the combined representation, but they do not show that FFT is
the dominant predictor or that improvement will transport to another cohort.

## Claim decision

Supported narrowly:

- entropy associations are robust to tile-purity and proposal-defined surface
  exclusions in this cohort;
- geometry/optical-density and FFT information can be complementary in nested
  participant-level prediction.

Not supported:

- matrix-specificity;
- independence from nuclei, clusters, fissures or lesion boundaries;
- superiority of FFT over conventional structural measurements;
- clinical, diagnostic or intraoperative validity.

Reviewed masks and direct lesion/cell annotations remain required.
