# NOSTOS-0 claim–evidence ledger

This ledger governs the sample-agnostic methods paper. It is separate from the
clinical NOSTOS-2 ledger. A software test, a synthetic recovery experiment and
an external biological validation are different levels of evidence and are not
interchangeable.

| Proposed claim | Current evidence | Decision | Missing gate |
|---|---|---|---|
| NOSTOS stores calibrated multiscale response geometry rather than only scalar summaries | Typed response schema; six implemented modules; physical and relative axes; deterministic data-free release candidate passes clean-room installation and 112 tests | Supported as an implementation claim | Immutable public tag, archive DOI and API reference |
| Core measurements survive declared acquisition perturbations | 24/24 prospective module tests pass; two mask perturbations retained as sensitivity experiments | Supported for the tested synthetic ranges only | Independent phantom implementation and broader PSF/voxel-anisotropy challenge |
| Thickness is physically accurate in external 3-D data | Eight public trabecular-bone volumes; mean absolute relative bias 8.05%; voxelwise median Spearman 0.927; exact one-sided Wilcoxon P=0.00391 versus nearest-boundary proxy | Supported for this public dataset and reference construction | BoneJ cross-software agreement and independent acquisition |
| One frozen representation transfers across tissue classes without retraining | Same response implementation run on cartilage, bone and 30 mycelium images | Supported as software transfer, not universal biological meaning | Fourth domain and independently acquired images |
| Compact response geometry is a universal specimen-identity fingerprint | Frozen confirmation on 60 disjoint identities across PSHG, nuclei, mycelium and collagen-SHG domains produced macro top-1 accuracy 0.100 (95% bootstrap interval 0.033–0.183); six substantive gates failed | Rejected | Claim must not appear; future validations must use fit-for-purpose physical or biological endpoints |
| A training-free classical adapter can recover the calcified-cartilage interface in PTA micro-CT | Patient-disjoint confirmation on 532 slices from ten patients: median error 537.2 µm (bootstrap 465.2–846.2), 0.39% within 30 µm, band IoU 0.005 and zero of six downstream measurements concordant | Rejected | Use an imported or learned adapter; validate it on a new untouched acquisition before promotion |
| A learned adapter can preserve interface-conditioned NOSTOS measurements in PTA micro-CT | Post-failure five-fold patient-grouped development across 19 patients and 35 samples: median Dice 0.912 and interface error 21.6 µm, but bootstrap upper error 67.2 µm, 57.8% of columns within 30 µm, band IoU 0.534, four slice abstentions and only one of six downstream features with CCC ≥0.85 | Not supported; segmentation improved but measurement preservation failed | Redesign the interface-aware objective and uncertainty rule, then freeze and test on a separately acquired untouched dataset |
| Full response geometry is universally superior to focused methods | Synthetic discrimination 1.00 versus 0.94 conventional; mycelium gain only 0.012; cartilage full model underperforms focused FFT | Rejected | Claim must not appear |
| Response geometry contains cross-species filament information | Mycelium balanced accuracy 0.680; permutation P=0.00498 | Supported narrowly; species and acquisition are confounded | Acquisition-balanced filament dataset and external test set |
| Cartilage angular entropy tracks site-matched OA structure | Participant-level medial/lateral associations in one public cohort; frozen outcome-free review packet now contains 40 sections from 8 locked validation participants | Exploratory support; review infrastructure complete | Human-corrected masks, Dice/IoU/boundary metrics; independent cohort; lesion/edge ablations |
| NOSTOS measures matrix organization specifically | Entropy survives purity, 100/250 µm erosion and external-surface exclusion, but extreme-dark-object exclusion significantly attenuates medial HHGS association and prediction; hole/void proxies were inert | Not supported; dark structures contribute at least medially | Reviewed masks, direct fissure/cell/cluster annotations and registered orthogonal microscopy |
| NOSTOS comparator superiority includes wavelet scattering | Official Kymatio 0.3.0, isolated Python 3.12/SciPy 1.14; frozen held-out synthetic balanced accuracy 0.875 versus NOSTOS response curves 1.000 | Supported only for the small synthetic construct benchmark | Biological-domain comparisons, uncertainty and independent test data |
| NOSTOS comparator superiority includes IBSI radiomics | Official conda PyRadiomics 3.1.0a2; 14/14 IBSI digital-phantom first-order values pass at the published three-significant-digit precision; synthetic balanced accuracy 1.000, equal to NOSTOS | Universal superiority rejected; upstream comparator execution supported | Full IBSI texture-matrix conformance and biological-domain comparisons |
| NOSTOS is clinically usable or intraoperative | No prospective acquisition, timing, surgeon, registered-mechanics or patient evidence | Prohibited | NOSTOS-2 prospective program |
| NOSTOS-0 is ready for Nature Methods/Nature Biomedical Engineering | Current work establishes an auditable platform core and clean-room release candidate but lacks independent acquisition and standard comparator completion | No | All red gates above plus external users and archival DOI |

## Current reproducibility receipts

- `outputs/nostos0-synthetic-v1/validation.json`
- `outputs/nostos0-module-perturbations-v1/module_perturbation_matrix.json`
- `outputs/nostos0-benchmark-v1/representation_benchmark.json`
- `outputs/nostos0-benchmark-v1/kymatio_benchmark.json`
- `outputs/nostos0-benchmark-v1/pyradiomics_benchmark.json`
- `outputs/external-bone-v1/external_bone_validation.json`
- `outputs/external-filament-v1/external_filament_validation.json`
- `outputs/external-cartilage-v1/external_cartilage_validation.json`
- `outputs/nostos0-comparator-conformance-v1/comparator_conformance.json`
- `outputs/nostos0-biological-retrieval-development-v1/biological_retrieval_development.json`
- `outputs/nostos0-biological-retrieval-confirmation-v1/biological_retrieval_confirmation.json`
- `outputs/nostos0-orbit-redesign-development-v1/orbit_redesign_development.json`
- `outputs/nostos0-osteochondral-interface-development-v1/osteochondral_interface_development.json`
- `outputs/nostos0-osteochondral-interface-confirmation-v1/osteochondral_interface_confirmation.json`
- `outputs/nostos0-osteochondral-learned-adapter-v1_1/osteochondral_learned_adapter_summary.json`
- `outputs/nostos0-evidence-bundle-v1/evidence_index.json`
- `manifests/cartilage_mask_review_packet.json` (pointer to the T7 review packet)
- `outputs/nostos0-release-candidate-v1/release_receipt.json`
- `outputs/nostos0-release-candidate-v1/release_manifest.json`

## Promotion rule

A claim can move from unsupported to supported only when the repository contains
the frozen protocol, immutable input manifest and checksums, executable code,
machine-readable result receipt, uncertainty analysis, failure accounting and a
figure-source table. A positive result generated while selecting parameters is
development evidence, not confirmation.
