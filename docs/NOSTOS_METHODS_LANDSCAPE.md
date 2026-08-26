# NOSTOS methods landscape and selection record

## Decision

NOSTOS should not become a bag of image features. Its defensible methodological contribution is a **physically calibrated, multiscale response representation** that applies the same frozen measurement grammar to calibrated 2D images, 3D volumes, and—when paired observations exist—time or load series.

The core representation should preserve response curves instead of collapsing every method to one scalar:

\[
\Phi(I,M,\Delta)=\{q_k(s,\tau,r)\}_{k=1}^{K},
\]

where image or volume \(I\), optional mask \(M\), and spatial/temporal calibration \(\Delta\) generate responses over physical scale \(s\), threshold or filtration \(\tau\), and spatial separation \(r\). Scalars are secondary summaries. Cross-specimen comparison can use curve distances, distributional optimal transport, or prespecified summary contrasts.

This design is sample-agnostic within a precise boundary: biological and biomaterial images having known physical spacing, supported dimensionality, and adequate signal. It is not modality-independent by assertion; every modality and domain requires QC and validation.

## Selection criteria

Every candidate method is scored against six questions:

1. Can synthetic ground truth be generated for it?
2. Can its scale be expressed in micrometres rather than pixels?
3. Does it have a direct structural interpretation?
4. Is its stability measurable under blur, noise, sampling, rotation, masking, and intensity perturbations?
5. Does it add information beyond angular FFT and simple geometry?
6. Is there an established implementation or comparator against which NOSTOS can be checked?

No method enters the core because it produces an attractive visualization.

## Evidence-based disposition

| Family | Dimensionality | What it measures | Main validity risk | Comparator / ground truth | Disposition |
|---|---:|---|---|---|---|
| Angular and radial FFT | 2D/3D | global or tiled orientation distribution, entropy, anisotropy, dominant wavelength, radial slope | edges, fissures, masks, and acquisition transfer functions can dominate power | analytic sinusoidal/fibre phantoms; current cartilage results | **Core** |
| Structure tensor | 2D/3D | local orientation, coherency, orientation dispersion | window scale and low-SNR gradients; not fibre-specific | OrientationJ; rotated line/fibre phantoms | **Core** and independent orientation estimator |
| Scale-normalized Hessian eigensystem | 2D/3D | blob-, line/tube-, and sheet-like response across physical scale | polarity, contrast, junction suppression, scale-selection bias | Frangi/Sato; tubes, sheets, spheres with known radii | **Core**, retain full scale curves |
| Local thickness / distance transform | 2D/3D masks | maximally inscribed diameter and thickness distributions | segmentation and anisotropic voxel sensitivity | BoneJ and analytic shapes | **Core when a validated mask exists** |
| Surface curvature and roughness | 2D contours / 3D surfaces | boundary damage, waviness, fissure geometry | strongly dependent on smoothing and boundary quality | analytic surfaces; roughness/fissure annotations | **Core geometry**, with scale-space reporting |
| Skeleton graph and erosion survival | 2D/3D masks | branch length, connectivity, fragmentation and percolation threshold | skeleton instability and threshold dependence | graph phantoms; BoneJ/network tools | **Core for network-like masks**, otherwise inapplicable |
| Minkowski functionals/tensors | 2D/3D masks | area/volume, boundary, Euler characteristic, anisotropy across threshold | binarization and threshold sweep can manufacture effects | analytic bodies; established morphological functionals | **Optional core extension**; valuable for porous/bone domains |
| Persistent homology | 2D/3D grayscale or masks | components, loops, cavities and their survival over filtration | filtration choice, interpretability, compute cost, decorative overuse | topology phantoms; bottleneck/Wasserstein stability | **Conditional module**, not a universal headline |
| Lacunarity | 2D/3D masks | scale-dependent gap/occupancy heterogeneity | redundant with density and variograms; sensitive to windowing | generated porous/fractal patterns | **Optional**, retain only if incremental validity is shown |
| Variogram / spatial covariance | tiled 2D/3D fields | heterogeneity length, directional spatial dependence | nonstationarity, ROI geometry, sparse tile fields | Gaussian random fields with known covariance | **Core spatial module** |
| Moran's I / local indicators | tiled fields or objects | global/local clustering relative to an explicit neighbor graph | arbitrary spatial weights and boundary effects | permutation nulls; simulated fields | **Optional summary**, not the primary curve |
| Ripley's K / pair correlation | point patterns | clustering or inhibition of cells, lacunae, branches | edge correction, intensity inhomogeneity, segmentation error | Poisson/cluster/inhibition simulations | **Domain adapter**, only for validated objects |
| Wavelet scattering | 2D; extensible to 3D | deformation-stable multiscale texture representation | less interpretable; dimensional expansion; scale configuration | Kymatio/reference scattering; texture phantoms | **Robustness benchmark / secondary representation** |
| Gabor/steerable/Riesz filters | 2D/3D | localized oriented energy and phase | overlaps FFT/tensor information and requires filter-bank choices | standard filter implementations | **Benchmark**, promote only after ablation |
| IBSI radiomics | 2D/3D ROI | standardized intensity, histogram, co-occurrence and run-length features | feature multiplicity, acquisition dependence, weak mechanistic meaning | IBSI digital phantom/reference values | **Mandatory comparator**, not novelty |
| CellProfiler measurements | mostly object-centric 2D/3D | established morphology and intensity measurements | segmentation-dependent and assay-specific | CellProfiler reference workflows | **Software/feature benchmark** |
| Deep embeddings / foundation models | 2D/3D depending model | high-dimensional learned similarity | hidden training data, domain shift, poor interpretation, GPU burden | frozen public models with participant-level evaluation | **Defer from core**; optional comparator only |
| Phase correlation | paired 2D/3D | rigid translation | cannot represent local deformation; periodicity/edge artifacts | known translated phantoms | **Core registration primitive** |
| Optical flow / deformable registration | time/load 2D | dense apparent displacement | brightness constancy, aperture problem, nonphysical warps | known deformation phantoms and landmarks | **Conditional dynamics module** |
| Digital volume correlation | paired/load 3D | volumetric displacement and strain | texture, subset size, interpolation, noise and strain differentiation | zero-strain repeats and realistic virtual deformation | **Separate mechanics tier**, never inferred from static images |
| PCA/UMAP/t-SNE | feature tables | exploratory projection | unstable, cohort-relative, often decorative | trustworthiness/stability analyses | **Exploratory display only** |

## Recommended frozen NOSTOS-0 core

The first cross-domain engine should implement only the smallest set that spans distinct structural dimensions:

1. **Calibration and QC:** spacing-aware resampling, channel/intensity metadata, blur/noise/saturation/coverage measures, eligibility and abstention.
2. **Spectral organization:** local angular FFT, radial spectrum, entropy, anisotropy, characteristic scale, and the complete scale response.
3. **Local directional organization:** structure-tensor orientation/coherency curves, independently benchmarked against FFT.
4. **Morphology spectrum:** scale-normalized Hessian eigenvalue signatures for blob, tube, and sheet responses.
5. **Geometry:** mask-conditioned distance, local thickness, boundary curvature, roughness, and object-size distributions.
6. **Network integrity:** skeleton graph measures and erosion/percolation survival only for eligible binary networks.
7. **Spatial heterogeneity:** directional variograms of feature fields; point-pattern statistics only through domain adapters.
8. **Reproducibility:** deterministic provenance plus rotation, resolution, blur, noise, intensity, mask, and parameter perturbation receipts.

Persistent homology, Minkowski tensors, scattering, radiomics, and learned embeddings should be plug-ins or benchmarks. This prevents the platform paper from claiming novelty for a collection of established algorithms.

## Novelty that must be tested, not merely stated

The proposed contribution is the common response geometry and its validation across domains. The paper must test four hypotheses:

- **Ground-truth recovery:** NOSTOS estimates known orientation, radius, thickness, roughness, connectivity, and heterogeneity scale from synthetic 2D and 3D phantoms.
- **Physical-scale transfer:** response maxima and curve shapes remain comparable after sampling changes when adequate resolution is retained.
- **Cross-domain phenotype recovery:** the same frozen modules recover established phenotypes in cartilage, trabecular bone, and a filamentous/fibrous domain without tissue-specific feature engineering.
- **Incremental coverage:** the combined representation captures independent structural axes beyond FFT, IBSI radiomics, and single-purpose reference tools.

Failure on one axis should be reported as a domain-of-validity boundary, not hidden by feature selection.

## Benchmark design

### Synthetic suite

Generate phantoms with exact parameters and factorial perturbations:

- oriented sinusoids and fibre fields with controlled angular dispersion;
- tubes, sheets, and blobs with known physical radii and contrast polarity;
- slabs and porous solids with known thickness distributions;
- surfaces with known wavelength/amplitude roughness and explicit fissures;
- graphs with known branches, loops, disconnections, and erosion thresholds;
- Gaussian random fields with known isotropic and anisotropic covariance;
- paired translations and non-rigid deformations with known displacement/strain.

Evaluate bias, absolute error, calibration slope, repeatability, failure rate, and runtime. Do not rely only on correlations.

### Real-domain suite

- **Cartilage:** structural histopathology, PLM, validated cartilage masks, boundary/lesion ablations, serial-section repeatability.
- **Bone micro-CT:** BV/TV, trabecular thickness/separation, connectivity and anisotropy versus BoneJ-style reference morphometry.
- **Filamentous/fibrous microscopy:** orientation, width, branch/connectivity, and perturbation recovery versus validated traces or synthetic mixtures.

Use specimen-level splits and inference. Images, tiles, serial sections, or repeated volumes from one specimen must never cross validation folds.

### Statistical tests

- repeated nested cross-validation only for prediction;
- bootstrap confidence intervals at the independent-specimen level;
- paired method-difference intervals, not comparisons of significance labels;
- multiple-testing control within prespecified feature families;
- equivalence or non-inferiority margins for resolution transfer where justified;
- variance decomposition across specimen, acquisition, section, and perturbation when repeats exist.

## Methods deliberately rejected from the first build

- Large unfiltered radiomics libraries: standardized comparators are useful; hundreds of selected features are not a coherent invention.
- UMAP/t-SNE phenospaces as evidence: they are cohort-relative illustrations.
- Generic deep segmentation without expert masks: it cannot validate its own ROI.
- Persistent-homology barcodes in the main figures without a prespecified topology hypothesis.
- Optical flow or strain maps from unpaired/static sections.
- Any claim that one universal parameter set is optimal across microscopy modalities before empirical transfer testing.

## Implementation order and release gates

1. Freeze data model, physical units, response-curve schema, provenance, and failure semantics.
2. Build synthetic ground-truth generator and tests before adding new real-data modules.
3. Implement tensor, Hessian, geometry, and variogram modules with CPU reference paths.
4. Verify against OrientationJ/Frangi/Sato, BoneJ/local thickness, IBSI reference features, and analytic phantoms.
5. Add topology and scattering only after core incremental-value ablations.
6. Add paired-image dynamics as a separately versioned capability with its own validation report.

A module is publishable only when it has reference parity, perturbation limits, runtime/memory reporting, known failure modes, and at least one real-domain validation. A module can be visually complete and still fail this gate.

## Primary evidence base

- Frangi AF et al. *Multiscale vessel enhancement filtering*. MICCAI (1998). DOI: 10.1007/BFb0056195.
- Sato Y et al. *Three-dimensional multi-scale line filter for segmentation and visualization of curvilinear structures in medical images*. Medical Image Analysis (1998). DOI: 10.1016/S1361-8415(98)80009-1.
- Rezakhaniha R et al. *Experimental investigation of collagen waviness and orientation in the arterial adventitia using confocal laser scanning microscopy*. Biomechanics and Modeling in Mechanobiology (2012), underlying OrientationJ validation.
- Hildebrand T, Rüegsegger P. *A new method for the model-independent assessment of thickness in three-dimensional images*. Journal of Microscopy (1997).
- Michielsen K, De Raedt H. *Integral-geometry morphological image analysis*. Physics Reports (2001), with the earlier image-analysis implementation in Computer Physics Communications.
- Mallat S. *Group invariant scattering*. Communications on Pure and Applied Mathematics (2012).
- Zwanenburg A et al. *The Image Biomarker Standardization Initiative: standardized quantitative radiomics for high-throughput image-based phenotyping*. Radiology (2020). DOI: 10.1148/radiol.2020191145.
- Carpenter AE et al. *CellProfiler: image analysis software for identifying and quantifying cell phenotypes*. Genome Biology (2006).
- Dougherty R, Kunzelmann K-H. *Computing local thickness of 3D structures with ImageJ*. Microscopy and Microanalysis (2007), and BoneJ/BoneJ2 reference implementations.
- Plotnick RE et al. *Lacunarity analysis: a general technique for the analysis of spatial patterns*. Physical Review E (1996). DOI: 10.1103/PhysRevE.53.5461.
- Bubenik P. *Statistical topological data analysis using persistence landscapes*. JMLR (2015).
- Skraba P, Turner K. *Wasserstein stability for persistence diagrams* (2020/2021).
- Lucas BD, Kanade T. *An iterative image registration technique with an application to stereo vision* (1981).
- Roberts BC et al. *Application of digital volume correlation for the measurement of displacement and strain fields in bone: a literature review*. Journal of Biomechanics (2014). DOI: 10.1016/j.jbiomech.2014.01.001.

## Bottom line

The research supports adding methods, but not adding them equally. NOSTOS-0 should combine FFT, structure tensors, scale-normalized Hessians, geometry, network survival, and variograms under one calibrated response-curve and reproducibility framework. Topology, Minkowski tensors, scattering, radiomics, object point patterns, and dynamics have defined roles and admission tests. This is a stronger and more falsifiable platform than either an FFT-only cartilage paper or an indiscriminate universal toolkit.
