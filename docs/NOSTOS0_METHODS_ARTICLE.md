# NOSTOS represents multiscale structure across biological images in physical coordinates

**Article type:** Article  
**Target:** Nature Methods (reach submission after the red validation gates close)  
**Version:** evidence-locked development draft, 26 August 2026  
**Status:** not for submission; human cartilage-mask validation, independent acquisition and archival DOI remain outstanding

## Abstract

Biological image-analysis methods commonly report tissue-specific scalar features, making it difficult to determine whether measurements transfer across resolution, dimensionality or specimen class. We developed NOSTOS, a CPU-first framework that represents image structure as calibrated response curves indexed by physical scale, direction, spatial separation and segmentation threshold. The same typed representation accommodates spectral organization, structure-tensor coherence, scale-normalized Hessian morphology, local thickness, network erosion survival and directional spatial covariance, while retaining stability estimates, validity flags and reasons for abstention. In analytic phantoms, all 24 prespecified module-perturbation tests passed across rotation, sampling, blur, noise, contrast, point-spread-function and partial-volume challenges; two mask-error experiments were retained as sensitivity tests rather than invariance claims. On a frozen synthetic construct benchmark, response curves achieved balanced accuracy 1.00, compared with 0.94 for conventional scalars, 0.88 for Kymatio scattering and 1.00 for PyRadiomics. In eight public trabecular-bone micro-CT volumes, NOSTOS local thickness showed 8.05% mean absolute relative bias and median voxelwise Spearman correlation 0.927 against archived reference maps. A frozen implementation also extracted structural information from 30 filamentous-microscopy images and from public human cartilage histology, although acquisition confounding, unvalidated cartilage masks and structure-sensitive ablations limit biological interpretation. NOSTOS therefore provides a common measurement grammar and prospective failure testing across biological images, not a universal tissue classifier. The implementation, tests and machine-readable evidence receipts are released openly.

## Main

Microscopy exposes structure over several orders of magnitude, but analysis pipelines often erase that geometry. A filter-bank response is reduced to its maximum, orientation becomes a single dominant angle, thickness becomes an average and topology becomes a feature count. Those summaries can be useful within a study, yet they obscure the scale at which a measurement arose and make changes in sampling, resolution or segmentation difficult to distinguish from biological differences. Large radiomic feature tables compound the problem: they increase coverage, but do not by themselves provide a coherent coordinate system or a prospective rule for when a measurement should not be reported.

NOSTOS was designed around a narrower proposition. A structural measurement should preserve the physical coordinate over which it was evaluated, retain its response rather than only its extremum, quantify its sensitivity to plausible perturbations and abstain when the image cannot support the requested inference. The framework applies the same measurement grammar across sample classes; it does not assume that the same response has the same biological meaning in every tissue. Tubeness may describe collagen bundles, hyphae, vessels or trabecular struts. NOSTOS makes those responses comparable as measurements, whereas biological studies establish their interpretation.

### A calibrated response geometry

For an image or volume \(I\), optional mask \(M\) and spatial calibration \(\Delta\), NOSTOS returns a set of typed responses

\[
\Phi(I,M,\Delta)=\{\Phi_m(\ell,\theta,\tau,r)\}_{m=1}^{M},
\]

where \(m\) denotes the measurement module, \(\ell\) physical scale, \(\theta\) direction, \(\tau\) a segmentation, confidence or erosion threshold and \(r\) spatial separation. Every response stores absolute physical coordinates, optional specimen-relative coordinates, values, units, stability metadata, validity flags, provenance and explicit reasons for abstention. Scalar descriptors are derived views of this object rather than the primary representation.

Six modules span distinct structural axes. Angular and radial Fourier responses measure directional energy, entropy, anisotropy and characteristic wavelength. Structure tensors provide a local, independently estimated orientation and coherence field. Scale-normalized Hessian eigenvalues resolve blob-, tube- and sheet-like responses. Maximal-inscribed-sphere geometry estimates local thickness in two- or three-dimensional masks. Skeleton and erosion-survival responses quantify network fragmentation over a declared filtration. Directional variograms describe spatial covariance and its anisotropy. Modules declare their dimensionality, calibration requirements and eligibility; a network response, for example, is inapplicable to an unsegmented intensity image rather than silently replaced by a surrogate.

The implementation is deterministic and CPU-first. It operates on calibrated two-dimensional images and three-dimensional volumes without tissue-specific retraining. A learned segmentation may supply a mask, but segmentation is an upstream measurement with its own validity requirement and is never allowed to validate itself through downstream feature stability.

**[Figure 1 near here: calibrated inputs, response geometry, perturbation/abstention and structural outputs.]**

### Prospective phantom tests define measurement limits

We froze the synthetic generator and truth registry before evaluating biological datasets. Analytic constructs encode orientation and angular dispersion, spectral wavelength, blob/tube/sheet class and size, local thickness, surface roughness, graph connectivity and anisotropic correlation length. Perturbations rotate, resample and crop the construct; alter contrast, blur and noise; modify isotropic or anisotropic point-spread functions; introduce partial-volume effects; and perturb masks.

All 24 prespecified module tests passed. The tests evaluate the quantity a perturbation should preserve or alter: circular orientation error after rotation, physical scale error after adequate resampling, morphology class and selected scale, thickness error in calibrated units, branch or survival behavior after deletion and variogram range and anisotropy. Mask errors were not counted as invariances. Two mask experiments instead quantify how far the resulting measurement moves, preserving the distinction between a stable calculation and a correct region of interest.

The response geometry classified 16 held-out perturbed constructs with balanced accuracy 1.00. Conventional scalar features and naive summaries of the same response families each reached 0.94. Removing the Hessian family reduced balanced accuracy to 0.88, whereas several other single-module removals did not change performance. These numbers are descriptive because the held-out set is small; they demonstrate executable discrimination and expose redundancy, not general superiority.

Official comparators were executed in isolated, pinned environments. Kymatio 0.3.0 scattering reached balanced accuracy 0.875. PyRadiomics reached 1.00, equal to NOSTOS. Its installation reproduced all 14 evaluated first-order values from the IBSI digital phantom at the published three-significant-digit precision after the documented kurtosis convention was reconciled. A separate read-only audit against the official IBSI benchmark workbook tested the 3-D texture aggregation conventions emitted by PyRadiomics: all 75 definitionally matched GLCM, GLRLM, GLSZM, GLDM and NGTDM features agreed at three significant digits, with four unsupported or non-equivalent workbook features retained as not comparable. This is mapped-feature conformance, not a claim that every IBSI feature or aggregation is implemented. The synthetic tie is important: the novelty claim rests on calibrated response geometry, perturbation accounting and abstention, not on defeating every feature library on a small classification task.

**[Figure 2 near here: ground-truth atlas, perturbation trajectories, error fields and comparator/ablation matrix.]**

### Local thickness transfers to public three-dimensional bone data

We next tested a module for which a spatially resolved external reference was available. Eight public trabecular-bone micro-CT volumes from Zenodo record 11061947 were analyzed with 32 frozen logarithmic radius levels. NOSTOS maximal-inscribed-sphere thickness was compared voxelwise with the archived IPL thickness maps. Across volumes, mean absolute relative bias was 8.05% (95% bootstrap interval, 6.83–9.25%), median voxelwise Spearman correlation was 0.927 and mean absolute error was 0.0189 mm. A twice-nearest-boundary approximation produced mean absolute error 0.0930 mm; the paired reduction was 0.0741 mm (exact one-sided Wilcoxon \(P=0.00391\)).

This experiment verifies physical-unit agreement for one measurement on one public archive. It does not establish equivalence with all BoneJ implementations or transport across scanners, segmentation protocols and disease states. Those restrictions are encoded in the result receipt as part of the reported result rather than left to narrative qualification.

**[Figure 3 near here: three-dimensional bone cutaway, reference and NOSTOS thickness fields, voxelwise residual terrain and casewise paired errors.]**

### One implementation operates across distinct biological domains

The frozen framework was then applied without tissue-specific feature retraining to a filamentous-microscopy collection and to public human cartilage histology. Thirty MyceliumSeg images carried no physical pixel calibration, so NOSTOS reported only dimensionless image-relative coordinates and marked physical-scale outputs unavailable. The full representation classified species with balanced accuracy 0.680 in participant/image-level evaluation (permutation \(P=0.00498\)), compared with 0.668 for conventional scalars and 0.553 for naive response summaries. Several module ablations exceeded the full model. Species and acquisition conditions are confounded in this collection; the result supports the presence of transferable structural information, not biological generalization or optimality of the combined representation.

In cartilage, participant-level medial and lateral Safranin-O features were paired with site-matched HHGS and OARSI outcomes; medial features were also compared with medial polarized-light scores. The full response representation did not outperform the focused Fourier phenotype. Angular spectral entropy remained associated with structural scores after strict tile purity and 100–250-µm boundary and external-surface exclusions. However, exclusion of pixels within 25 µm of the darkest 1% of proposed-cartilage luminance attenuated the medial HHGS association from Spearman \(\rho=-0.381\) to \(-0.274\); the paired correlation difference was \(-0.106\) with a participant-bootstrap interval excluding zero (\(-0.215\) to \(-0.003\)). Nested prediction also fell from \(R^2=0.073\) to 0.017. The lateral association was less affected. Proposal-defined void and internal-hole exclusions were identical to baseline and therefore non-informative.

These ablations rule out a matrix-specific or cell-independent interpretation. They support a more limited conclusion: the entropy phenotype is robust to the tested boundary exclusions, while dark structures contribute at least medially. Cartilage proposals have not yet been compared with human reference masks. The cartilage analysis therefore remains exploratory and cannot validate segmentation, matrix organization or clinical utility.

**[Figure 4 near here: cross-domain atlas using identical module glyphs, filament response fields, cartilage boundary/dark-object counterfactuals and domain-of-validity map.]**

### Reproducibility is part of the measurement

Every validation writes a machine-readable receipt containing the protocol version, input identity, numerical results, validity status and interpretive boundary. A separate evidence index checks receipt availability and hashes. The release builder constructs a deterministic data-free archive, replaces private development roots with portable placeholders, scans for credentials and absolute paths and records the SHA-256 of every included file. The archive installed in a fresh Windows Python 3.13 environment and passed 114 tests, with two optional-comparator tests skipped. The public repository subsequently passed the same core suite and release audit on clean Linux runners under Python 3.12 and 3.13.

The release also exposes a one-command, data-free replication challenge. It regenerates the synthetic truth validation, representation benchmark and module perturbation matrix, evaluates eight frozen semantic gates and records the interpreter, operating system, source revision and SHA-256 of each receipt. The author-operated reference run passed all gates. This verifies the challenge mechanism, not external replication; an independently operated receipt remains required.

This infrastructure improves auditability but is not independent scientific replication. The evidence index explicitly reports NOSTOS-0 as not ready for a flagship methods claim while blinded cartilage-mask validation, independent acquisition, complete comparator checks, external-user replication and an archival DOI remain open.

## Discussion

NOSTOS formalizes a common structural response geometry across spectral, directional, morphological, geometric, network and spatial measurements. Its main contribution is not a new Fourier transform, vesselness filter or thickness algorithm. It is the decision to preserve physically indexed response curves, attach perturbation behavior and failure semantics to each measurement, and expose the same typed object across distinct image classes. This organization makes familiar algorithms more falsifiable: the scale at which a response arises remains visible, resampling can be tested in physical units and segmentation uncertainty cannot be mistaken for invariance.

The present evidence also defines the limits of the framework. PyRadiomics tied NOSTOS on the synthetic classification split. Several filament ablations exceeded the full representation. The full representation did not outperform focused Fourier features in cartilage. These findings reject a universal-superiority claim and argue against indiscriminate feature concatenation. The benefit of the shared geometry must instead be judged through measurement coverage, calibration, perturbation stability, interpretable failure and prospective utility in each domain.

Three validation gaps remain decisive. First, independent acquisition is required to separate structural transfer from repository-specific preparation and imaging. Second, downstream biological claims require independently reviewed masks and object annotations; stable measurements within an incorrect region remain incorrect. Third, external users must reproduce at least one complete result from the archived release. Until those gates close, NOSTOS is an openly testable platform with promising cross-domain evidence, not a completed Nature Methods claim.

## Methods

### Response object and coordinate conventions

The response schema stores module, measurement, axes, axis units, optional direction, values, stability statistics, validity state, abstention reasons and provenance. Spatial scale is expressed in micrometres or millimetres when pixel or voxel spacing is supplied. When physical calibration is absent, physical-scale measurements abstain or are reported only in explicitly declared specimen-relative coordinates. Directions are stored in image coordinates and may additionally be transformed to specimen coordinates when a transformation is supplied.

### Synthetic constructs and perturbations

Synthetic images and volumes were produced deterministically from stored seeds and analytic parameters. Ground truth included programmed orientation, angular dispersion, wavelength, radius or thickness, surface spectrum, graph structure and covariance range. Rotation, resampling, crop, blur, additive noise, contrast, anisotropic point-spread function, partial volume and mask perturbations were applied using frozen parameter grids. Module-specific acceptance tests were declared before execution. Mask perturbations were reported as sensitivity experiments.

### Structural modules

Spectral responses used windowed Fourier power summarized over angular and radial coordinates. Structure-tensor responses were computed across declared derivative and integration scales. Hessian eigenvalue responses were scale normalized and converted to blob, tube and sheet signatures while retaining their scale curves. Local thickness used a discretized maximal-inscribed-sphere construction with physical spacing. Network responses summarized skeleton structure and component survival during calibrated erosion. Spatial responses used directional empirical variograms over declared separation bins. Exact parameters and eligibility rules are stored in the versioned configuration and source code.

### Synthetic representation benchmark

Four construct classes were separated into frozen development perturbations and disjoint held-out perturbation types or magnitudes. Conventional scalars, naive response summaries, full response curves and six leave-one-module-out representations used the same linear support-vector classifier and identical samples. Kymatio and PyRadiomics used isolated environments because their dependency ranges conflict with the core environment. This benchmark was descriptive and no inferential superiority claim was assigned to its 16 held-out observations.

### External bone validation

Eight matched segmentation and IPL thickness volumes were drawn from Zenodo record 11061947 under CC BY 4.0. The declared three-case pilot preceded freezing of 32 logarithmic radius levels. Voxelwise Spearman correlation, mean absolute error and volume-level relative bias were calculated against the archived maps. Uncertainty for the mean absolute relative bias used volume-level bootstrap resampling. The nearest-boundary comparator was evaluated on the same volumes; paired error was tested with an exact one-sided Wilcoxon signed-rank test.

### Filament and cartilage analyses

Thirty annotated MyceliumSeg images were processed with the frozen implementation. Species prediction operated at the image level with permutation inference; absent physical calibration was recorded as a validity restriction. Cartilage analyses used participant-level summaries. Medial and lateral features were paired only with same-site HHGS and OARSI outcomes, and PLM was evaluated medially. Correlation uncertainty used 2,000 participant bootstrap samples. Prediction used ten repeats of five-fold participant-grouped outer cross-validation with inner ridge regularization. Boundary, surface, purity, void, hole and extreme-dark-object variants were computed from identical inputs and paired by participant. Proposal masks were not treated as reference annotations.

### Software and reproducibility

NOSTOS 0.3.0 requires Python 3.12 or newer. The core environment is locked in `uv.lock`; comparator environments are specified separately. Tests, configurations, input manifests, output receipts and the evidence index are versioned with the source. Release candidates are generated by `nostos-build-release`, which allowlists code and small evidence artifacts, excludes source microscopy and scans staged text for secrets and private paths. The public `v0.3.0-rc5` tag identifies the clean-room-tested research candidate containing the mapped IBSI texture-conformance audit.

### Data and code availability

Source data remain in their originating public repositories and are not redistributed. NOSTOS source, tests, configurations and compact validation receipts are available at https://github.com/RonnieHappy/NOSTOS under the BSD 3-Clause License. The current release is a tagged candidate and does not yet have an archival DOI. Dataset DOIs, source commits and input hashes are recorded in the manifests and receipts.

## Reporting summary and administrative statements

The work is secondary computational analysis of public de-identified datasets and synthetic data. Institutional secondary-analysis determination, author name and affiliation, author contributions, funding, acknowledgements and competing-interest statements require author confirmation before submission. No clinical use is claimed.

## Figure legends

**Figure 1 | A common response geometry for calibrated biological images.** Calibrated two-dimensional images and three-dimensional volumes enter the same typed measurement system. Spectral, tensor, Hessian, thickness, network and spatial modules retain their responses over physical scale, direction, threshold or separation. Prospective perturbations quantify stability. Measurements either produce a response with provenance or abstain with a stated reason.

**Figure 2 | Analytic recovery and perturbation limits.** Synthetic constructs encode exact directional, morphological, geometric, network and spatial ground truth. Error trajectories show the effect of rotation, sampling, blur, noise, point-spread-function and partial-volume perturbations. The held-out construct matrix compares NOSTOS response curves, conventional scalars, naive summaries, Kymatio, PyRadiomics and leave-one-module-out representations. Classification is descriptive at the stated sample size.

**Figure 3 | External validation of local thickness in public trabecular-bone micro-CT.** Registered cutaways show the archived IPL map, NOSTOS maximal-inscribed-sphere thickness and their residual field. Voxelwise agreement and case-level mean absolute errors are shown for all eight volumes. Paired lines compare NOSTOS with the nearest-boundary approximation.

**Figure 4 | Frozen cross-domain measurement and its validity boundaries.** The same module implementation is applied to filamentous microscopy and cartilage histology. Response fields and compact fingerprints are displayed in a shared visual grammar. Cartilage counterfactual masks isolate surface, boundary and extreme-dark-object sensitivity. A domain-of-validity panel distinguishes supported measurements, exploratory biological associations and abstentions.

## References

1. Frangi, A. F. et al. Multiscale vessel enhancement filtering. *Medical Image Computing and Computer-Assisted Intervention* (1998). https://doi.org/10.1007/BFb0056195
2. Sato, Y. et al. Three-dimensional multi-scale line filter for segmentation and visualization of curvilinear structures in medical images. *Medical Image Analysis* **2**, 143–168 (1998). https://doi.org/10.1016/S1361-8415(98)80009-1
3. Hildebrand, T. & Rüegsegger, P. A new method for the model-independent assessment of thickness in three-dimensional images. *Journal of Microscopy* **185**, 67–75 (1997).
4. Mallat, S. Group invariant scattering. *Communications on Pure and Applied Mathematics* **65**, 1331–1398 (2012).
5. Zwanenburg, A. et al. The Image Biomarker Standardization Initiative: standardized quantitative radiomics for high-throughput image-based phenotyping. *Radiology* **295**, 328–338 (2020). https://doi.org/10.1148/radiol.2020191145
6. Carpenter, A. E. et al. CellProfiler: image analysis software for identifying and quantifying cell phenotypes. *Genome Biology* **7**, R100 (2006).
7. Dougherty, R. & Kunzelmann, K.-H. Computing local thickness of 3D structures with ImageJ. *Microscopy and Microanalysis* **13**, 1678–1679 (2007).
8. Plotnick, R. E., Gardner, R. H., Hargrove, W. W., Prestegaard, K. & Perlmutter, M. Lacunarity analysis: a general technique for the analysis of spatial patterns. *Physical Review E* **53**, 5461–5468 (1996). https://doi.org/10.1103/PhysRevE.53.5461
9. Bubenik, P. Statistical topological data analysis using persistence landscapes. *Journal of Machine Learning Research* **16**, 77–102 (2015).
10. Roberts, B. C. et al. Application of digital volume correlation for the measurement of displacement and strain fields in bone: a literature review. *Journal of Biomechanics* **47**, 923–934 (2014). https://doi.org/10.1016/j.jbiomech.2014.01.001
