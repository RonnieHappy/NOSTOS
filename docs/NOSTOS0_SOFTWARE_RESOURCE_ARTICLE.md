# NOSTOS: a calibrated and auditable measurement contract for heterogeneous biological images

**Article type:** Software Resource / Methods Resource  
**Author:** Yany Lin, Project NOSTOS  
**Version:** submission candidate, 28 August 2026  
**Status:** scientifically bounded; archival DOI and unaided external execution required before submission

## Abstract

Biological image-analysis pipelines often emit measurements without recording whether image sampling, calibration or segmentation can support them. We developed NOSTOS, an open CPU-first framework that applies established structural estimators through a common measurement contract. Every output retains physical coordinates, scale- or threshold-resolved responses, uncertainty metadata, validity flags, provenance and explicit reasons for abstention. We tested the implementation using analytic phantoms and public microscopy or micro-computed-tomography archives. All 24 prespecified module-perturbation tests passed in the registered phantom operating envelopes. Three endpoint case studies then assessed bounded external behavior. In an untouched polarization-resolved second-harmonic-generation breast cohort, a declared sigma-2 structure-tensor field achieved median axial error 7.59 degrees across 48 regions of interest after a frozen instrument-to-raster transform. On 20 STARE reference vessel masks, corrected network erosion-survival and skeleton-length responses agreed with independently processed labels (Spearman correlations 0.988 and 0.995). Across eight public trabecular-bone volumes, local thickness showed median voxelwise Spearman correlation 0.927 and concordance correlation coefficient 0.926 against archived BoneJ reference maps. Programmed microscopy deformation provided an additional uncertainty case study but is not interpreted as tissue motion or mechanics. Larger prospective experiments rejected raw response concatenation, canonical rotation quotienting, biological identity retrieval and transfer of a global Fourier reliability rule as universal platform claims. A five-record bone stress program further rejected perturbation stability as a substitute for structural support and showed that scale-aware contracts reduced selective risk without meeting frozen coverage gates. NOSTOS is therefore not a universal phenotype representation or a validated universal support detector. It is a calibrated, failure-aware interface for heterogeneous structural measurements whose biological validity remains endpoint specific.

## Introduction

Microscopy measurements are inseparable from image formation. A five-pixel structure can represent different physical sizes, a global direction can be undefined in a branching network, and a stable feature can still arise from an incorrect mask. Yet many pipelines reduce images to scalar tables without preserving the coordinates, operating limits or failures that produced those values. This makes numerical reproducibility easier than scientific interpretation: software can return the same number even when the requested measurement is unsupported.

NOSTOS addresses this problem as an interface and validation resource. Its contribution is not a new Fourier transform, structure tensor, Hessian filter, thickness algorithm, skeleton or variogram. Instead, these estimators are exposed through one typed contract that records where a response was measured, the physical or dimensionless scale used, how the response changed under declared perturbations and why the system emitted or withheld a result. The framework deliberately separates technical measurement semantics from biological meaning. Tubeness can be computed consistently in collagen, vessels, hyphae or bone; what that response means must be established independently in each domain.

We evaluated two questions. First, can the software recover registered analytic truths and behave predictably under acquisition perturbations? Second, can selected mature endpoints reproduce bounded reference measurements in public external archives? We also retained prospective failures that constrain the platform claim. The resulting paper presents NOSTOS as a transparent measurement resource, not as a universal classifier, biological foundation model, diagnostic system or intraoperative device.

## Results

### A common contract preserves measurement context

For image or volume I, optional mask M and spatial calibration Δ, NOSTOS returns typed responses Φm(ℓ, θ, τ, r), where m identifies the module, ℓ is physical scale, θ is direction, τ is a confidence, segmentation or erosion threshold and r is spatial separation. Each response stores coordinates, values, units, dimensionality, validity, stability metadata, software and input provenance and an abstention reason when the requested endpoint is unsupported. Scalar summaries are derived views rather than the primary record.

The current core includes spectral organization, local structure-tensor orientation, scale-normalized Hessian morphology, local thickness, reference-mask network responses and directional spatial covariance. A dynamic extension records programmed image deformation and continuation links but is not used to claim object motion, strain, mechanics or lineage. Segmentation can be supplied by the user or an external model; downstream stability never validates the mask that defines the region.

**[Figure 1 near here: calibrated inputs, typed response geometry, perturbation behavior and explicit abstention.]**

### Registered phantoms define bounded operating envelopes

The synthetic truth registry contains programmed orientation and dispersion, spatial wavelength, blob/tube/sheet morphology and scale, local thickness, network connectivity and spatial correlation. Perturbations alter rotation, sampling, blur, noise, contrast, point-spread function, partial volume, crop and mask boundaries. Each test declares whether a measurement should remain invariant, change in a predictable direction or abstain.

All 24 required module-perturbation tests passed. Two mask experiments were retained as sensitivity analyses rather than invariance claims. The small historical representation benchmark classified 16 held-out constructs with balanced accuracy 1.00 for response curves and 0.94 for conventional or naïve summaries. These values are preserved for provenance but are not superiority endpoints and are no longer gates in the external replication challenge.

More informative prospective tests rejected a universal representation. Under 480 compound acquisition shifts, raw curve concatenation reached balanced accuracy 0.721, below collapsed summaries and conformance-audited radiomics at 0.883. A separately frozen 600-image test of canonical rotation quotienting reached 0.700 versus 0.673 for raw curves, but the paired improvement interval crossed zero and four of seven gates failed. A four-domain biological identity test reached macro top-1 accuracy 0.100. These results define the framework as a measurement contract rather than a specimen-identity embedding.

**[Figure 2 near here: analytic truth recovery, perturbation matrix, retained platform failures and selective-risk boundaries.]**

### Local orientation transfers only after the endpoint and coordinate system are declared

A frozen global Fourier reliability rule performed well on analytic gratings but failed when transferred to manually annotated collagen SHG: accepted estimates had 33.3% selective risk, and abstention did not materially improve the always-emit baseline. Branching MyceliumSeg masks rarely supplied a defined global axis. These failures showed that global direction was the wrong biological endpoint.

We therefore evaluated a local field against manual or instrument-derived local references. Development on a separate skin cohort established a single 90-degree instrument-to-raster transform, which was frozen before opening the untouched breast cohort. The declared sigma-2 tensor field achieved median axial error 7.59 degrees and axial alignment 0.877 across 48 regions of interest and 1,367,747 eligible pixels. The result supports a calibrated local direction field under the tested acquisition and eligibility rules. Its uncertainty is presently ROI-level; donor or tissue-block hierarchy must replace ROI resampling if the archive contains clustered regions from the same independent specimen.

### Network responses are stable on supplied reference masks, not on automatic vessel segmentation

An initial 45-case network experiment failed after exposing a distance-definition defect. After correction and protocol refreezing, NOSTOS was applied to untouched STARE vessel labels. Across 20 images, survival-area correlation was 0.988, skeleton-length correlation was 0.995 and median relative difference was 1.77%. This supports sampling stability and numerical agreement for manually defined vascular networks.

The result does not validate automated vessel extraction. AH and VK are alternate annotations of the same images rather than independent cohorts, and image-derived HRF segmentation achieved Dice 0.265. NOSTOS therefore requires an imported or independently validated network object before it emits graph and survival measurements.

### Local thickness agrees with an established computational reference in one bone archive

Eight public trabecular-bone micro-CT volumes supplied matched segmentation and archived thickness maps. NOSTOS used 32 logarithmically spaced radii selected before the full comparison. Median voxelwise Spearman correlation with the archived maps was 0.927; comparison with BoneJ produced concordance correlation coefficient 0.926 and median relative difference 7.14%. NOSTOS outperformed a nearest-boundary approximation on the same masks.

This is cross-software numerical concordance rather than independent biological truth. The volumes are effectively isotropic, share one acquisition archive and use the same masks. Scanner transfer, segmentation transfer and anisotropic-voxel validation remain outside the claim.

**[Figure 3 near here: registered bone cutaways, residual maps and volume-level concordance.]**

### Programmed deformation illustrates case-level uncertainty without implying mechanics

Dense image deformation was tested on disjoint analytic sequences and eight BBBC035 planes subjected to controlled warps. Median endpoint errors were 0.107 and 0.270 pixels, with empirical coverage 99.97% and 97.25% for the frozen uncertainty bound. Coverage and efficiency are reported by independent image or deformation family, not by treating spatially dependent pixels as independent observations.

These tests validate programmed image deformation only. They do not establish cell motion, material strain, optical coherence elastography or tissue mechanics. Those claims require object correspondence or calibrated optical phase, loading geometry and constitutive validation.

### Failure-aware outputs are the platform boundary

The evidence index retains positive and negative experiments under one schema. The framework abstains when calibration is missing, the region is too small, a global direction is undefined, sampling cannot support the requested scale or an upstream mask is absent. Retained failures include global Fourier transfer, raw and canonical representation tests, biological identity retrieval, automated HRF network segmentation, division tracking and several nuclei polarity and osteochondral-adapter gates.

A prospectively staged bone program tested the contract more directly. Perturbation-only support selection could not distinguish coherent from non-informative regions in 4,736 annotated mouse-bone SHG sections. In 26 paired rat-confocal volumes, a calibrated imported-mask corruption stress test reduced silent-invalid risk from 0.50 to 0.25, but full-contract coverage was 0.538. A scalar human-nanoCT direction accepted blur and resampling failures; retaining response scale reduced risk at 0.8 micrometres from 0.0278 to 0.0087, but coverage remained 0.399. None passed the master coverage gate. Conversely, the complete contract withheld a requested physical collagen endpoint from 144 UV-PAM tiles lacking pixel calibration and semantic support while allowing 125 explicitly pixel-domain descriptors. The latter is a governance control, not an accuracy result.

**[Supplementary Figure 1 near here: source microscopy, computed fields, contract ablations and abstention.]**

**[Figure 4 near here: three supported endpoint examples beside retained failure and abstention cases.]**

## Discussion

NOSTOS provides a disciplined way to expose established structural estimators across heterogeneous images. The evidence supports implementation correctness inside registered phantom envelopes and bounded external behavior for local orientation, reference-mask network responses and local thickness. It also shows why a common interface must not be confused with universal biological meaning.

The strongest scientific contribution is explicit invalidity. Conventional pipelines commonly return a number whenever code executes. NOSTOS instead couples each emitted value to calibration, eligibility, perturbation stability and provenance. The bone contract-ablation program showed that the current implementation can rank some corrupted outputs and enforce obvious calibration or semantic abstentions, but it also showed that perturbation self-consistency cannot establish that the requested structure is present and that risk reduction can be purchased with unusably low coverage. This manuscript therefore does not claim a universal validity advantage. A decisive confirmation still requires a frozen support contract that lowers silent-invalid emissions at matched, practically useful coverage in unseen acquisition families.

Several limits are material. External endpoints use small or single-archive samples, and some reference maps share mathematical assumptions with NOSTOS. The PSHG hierarchy requires donor confirmation. Network analysis depends on valid imported masks. Bone thickness lacks scanner and anisotropic transfer. Programmed image deformation is not mechanics. Cartilage associations and unvalidated cartilage proposals are excluded from the central tool claim and belong in a separate application study after independent mask review.

The framework is intended for reproducible measurement development and audit. It is not cleared or validated for diagnosis, treatment planning or intraoperative use.

## Methods

### Software implementation and response schema

NOSTOS 0.3.0 is implemented in Python 3.12 using NumPy, SciPy, scikit-image and scikit-learn. Core dependencies are locked with uv. Comparator environments are isolated; the PyRadiomics environment includes an explicit platform package list with build strings and source URLs. Each run writes input hashes, calibration, parameters, environment metadata, validity results, output hashes and runtime.

Configuration values are project-relative or supplied through NOSTOS_DATA_ROOT and NOSTOS_ANNOTATION_ROOT. The release builder allowlists source and compact evidence, excludes microscopy data, scans staged text for credentials and workstation paths and writes a deterministic release manifest.

### Phantom and perturbation validation

Analytic constructs were generated from registered parameters and evaluated using module-specific physical errors. Orientation used axial circular error. Spectral scale used relative wavelength error inside the supported sampling band. Morphology used class and selected-scale error. Thickness used calibrated physical error. Network tests used branch, cycle and erosion-survival behavior. Spatial tests used programmed correlation range and anisotropy. Perturbation gates were frozen before confirmation data generation.

### External endpoint analyses

The PSHG experiment averaged polarization frames to form the intensity input. Reference orientation and eligibility were derived from archived fit maps. The 90-degree coordinate transform and sigma-2 endpoint were frozen before breast-cohort evaluation. The primary summary was median axial error by ROI, with complete pixels retained inside each resampled ROI.

STARE analyses operated on supplied vessel labels. The response curve measured survival and skeleton length over physical or normalized erosion thresholds. Image was the independent unit. Alternate labels on the same image were treated as repeated annotations, not independent samples.

Bone validation used eight matched segmentation and reference-thickness volumes from Zenodo record 11061947. Voxelwise agreement was summarized within volume and uncertainty resampled whole volumes. BoneJ and nearest-boundary calculations were comparators on the same masks.

The bone validity program used mouse-bone SHG from Zenodo 3355937, paired murine SHG/autofluorescence from Figshare 20765659, 26 rat-confocal LCN image/mask pairs from Zenodo 11061868, six publicly binned human synchrotron-nanoCT volumes from Zenodo 17909733 and UV-PAM tiles from Zenodo 6345772. Mouse, rat or deposited volume was the highest available unit; tiles, sections, locations and perturbations were nested technical cases. Contract-visible diagnostics were separated from withheld invalidity tests. Post-failure redesigns remained development evidence and were not promoted to confirmation. Public nanoCT spacing was inferred as 0.10 micrometres from the reported 50-nm acquisition and repository-declared twofold binning. UV-PAM PNGs lacked pixel calibration, so only pixel-domain descriptors were permitted.

Dense deformation used analytic displacement fields and controlled warps of BBBC035 microscopy. Error and uncertainty were summarized by independent plane or deformation family. Pixelwise coverage was retained as a descriptive diagnostic rather than a distribution-free guarantee.

### External conformance challenge

Protocol 2.0 regenerates the synthetic truth receipt, the 24 required perturbation tests and the historical representation benchmark, then hashes all artifacts. The challenge is passed only by an identified external operator using a fresh clone or release archive without the author's environment. Historical small-sample accuracies are reproduced as data but are not success gates. A passing receipt establishes unaided software execution only.

## Data and code availability

All biological images remain in their originating public repositories. Dataset identifiers, licenses, source commits and input hashes are recorded in the manifests and evidence receipts. Source code is available at https://github.com/RonnieHappy/NOSTOS under the BSD 3-Clause License. The frozen submission release must be archived with a DOI before submission; the DOI will replace this sentence in the final deposited version.

## Ethics, authorship and competing interests

This work is secondary computational analysis of public de-identified data and synthetic data; no new participants or specimens were recruited. The corresponding author's institutional requirements for secondary-analysis determination must be confirmed before submission. Yany Lin conceived the framework, implemented the software and analyses, curated the evidence record and drafted the manuscript. Funding, affiliation, acknowledgements and competing-interest statements require final author confirmation.

## Figure legends

**Figure 1 | Traceable cross-domain inputs and computed NOSTOS responses.** Public cartilage histology, polarization-resolved SHG and trabecular-bone micro-CT are shown beside scale-indexed response fields and the registered module-perturbation matrix. Source identities are recorded in the figure manifest; no generative scientific imagery is used.

**Figure 2 | Analytic recovery and the boundary of the platform claim.** Programmed ground truths and perturbation trajectories are shown with retained failures of raw response concatenation, canonical rotation quotienting, biological identity retrieval and global Fourier reliability transfer.

**Figure 3 | External local-thickness concordance in trabecular-bone micro-CT.** Registered reference and NOSTOS thickness maps, residuals, voxelwise correlations and case-level errors are shown for eight public volumes.

**Figure 4 | Endpoint-specific validity across heterogeneous images.** Local collagen direction, cartilage proposal sensitivity and nuclei polarity examples illustrate the distinction between technically supported measurements, exploratory applications and failed or abstained endpoints.

**Supplementary Figure 1 | Public-bone validity-contract stress program.** Real mouse-bone SHG, rat-confocal lacunar-canalicular imagery and imported labels, human synchrotron-nanoCT and UV-PAM are shown with deterministic orientation, terrain, isosurface, Fourier and risk-coverage computations. The full rat-network contract reduced observed silent-invalid risk from 0.50 to 0.25 at 0.538 coverage. Scale-indexed nanoCT responses lowered selective risk at supported scales but failed the frozen 0.80 coverage gate. The physical UV-PAM endpoint was withheld because pixel calibration and collagen semantics were absent. The figure manifest records source hashes and transformations; no generative scientific imagery is used.

## References

1. Frangi, A. F. et al. Multiscale vessel enhancement filtering. Medical Image Computing and Computer-Assisted Intervention (1998). https://doi.org/10.1007/BFb0056195
2. Sato, Y. et al. Three-dimensional multi-scale line filter for curvilinear structures. Medical Image Analysis 2, 143-168 (1998). https://doi.org/10.1016/S1361-8415(98)80009-1
3. Hildebrand, T. & Rüegsegger, P. Model-independent assessment of thickness in three-dimensional images. Journal of Microscopy 185, 67-75 (1997).
4. Mallat, S. Group invariant scattering. Communications on Pure and Applied Mathematics 65, 1331-1398 (2012).
5. Zwanenburg, A. et al. The Image Biomarker Standardization Initiative. Radiology 295, 328-338 (2020). https://doi.org/10.1148/radiol.2020191145
6. Carpenter, A. E. et al. CellProfiler. Genome Biology 7, R100 (2006).
7. Dougherty, R. & Kunzelmann, K.-H. Computing local thickness of 3D structures with ImageJ. Microscopy and Microanalysis 13, 1678-1679 (2007).
8. Ljosa, V., Sokolnicki, K. L. & Carpenter, A. E. Annotated microscopy image sets for validation. Nature Methods 9, 637 (2012). https://doi.org/10.1038/nmeth.2083
9. Andreux, M. et al. Kymatio: scattering transforms in Python. Journal of Machine Learning Research 21, 1-6 (2020).
10. van Griethuysen, J. J. M. et al. Computational radiomics system. Cancer Research 77, e104-e107 (2017). https://doi.org/10.1158/0008-5472.CAN-17-0339
11. Harris, C. R. et al. Array programming with NumPy. Nature 585, 357-362 (2020). https://doi.org/10.1038/s41586-020-2649-2
12. Virtanen, P. et al. SciPy 1.0. Nature Methods 17, 261-272 (2020). https://doi.org/10.1038/s41592-019-0686-2
13. van der Walt, S. et al. scikit-image. PeerJ 2, e453 (2014). https://doi.org/10.7717/peerj.453
14. Pedregosa, F. et al. Scikit-learn. Journal of Machine Learning Research 12, 2825-2830 (2011).
15. Doube, M. et al. BoneJ. Bone 47, 1076-1079 (2010). https://doi.org/10.1016/j.bone.2010.08.023
16. Maier-Hein, L. et al. Metrics reloaded. Nature Methods 21, 195-212 (2024). https://doi.org/10.1038/s41592-023-02151-z
17. Maška, M. et al. The Cell Tracking Challenge. Nature Methods 20, 1010-1020 (2023). https://doi.org/10.1038/s41592-023-01879-y
18. Schmarje, L., Zelenka, C., Geisen, U., Glüer, C.-C. & Koch, R. 2D and 3D segmentation of uncertain local collagen fiber orientations in SHG microscopy. Pattern Recognition, 374-386 (2019). https://doi.org/10.1007/978-3-030-33676-9_26
19. Pritchard, Y. et al. Persistent homology analysis distinguishes pathological bone microstructure in non-linear microscopy images. Scientific Reports 13, 2522 (2023). https://doi.org/10.1038/s41598-023-28985-3
20. Sieverts, M. & Acevedo, C. Confocal Lacunar Canalicular Network Segmentation Data. Zenodo (2024). https://doi.org/10.5281/zenodo.11061868
21. Anuth, S. et al. Nano-scale evidence for osteocyte network integration across bone remodeling interfaces in human bone revealed by synchrotron nanoCT. Materials Today Bio 37, 102813 (2026). https://doi.org/10.1016/j.mtbio.2026.102813
22. Cao, R. et al. Label-free intraoperative histology of bone tissue via deep-learning-assisted ultraviolet photoacoustic microscopy. Nature Biomedical Engineering 7, 124-134 (2023). https://doi.org/10.1038/s41551-022-00940-z
