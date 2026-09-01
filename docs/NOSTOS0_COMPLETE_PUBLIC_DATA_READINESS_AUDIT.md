# NOSTOS-0 complete public-data readiness audit

**Audit state:** evidence locked, 30 August 2026  
**Decision:** not ready for a Nature-family methods submission  
**Current defensible category:** public research-software platform with validated components and explicit failed claims

## Executive decision

NOSTOS is now a real sample-agnostic measurement tool, not merely an FFT cartilage analysis. It accepts calibrated 2-D images and 3-D volumes, emits a typed response geometry, preserves physical scale and direction, records provenance, and abstains when a requested measurement is unsupported. Its public evidence base includes analytic phantoms, cartilage histology, bone micro-CT, nuclear fluorescence, fungal networks, SHG collagen and PSHG microscopy.

The public-data implementation and author-operated validation program is complete for the deliberately bounded NOSTOS-0 measurement contract. The strongest broad hypothesis—that the combined response geometry is a universally robust biological fingerprint—failed prospective synthetic and biological confirmation and has been removed from the admissible claims. A subsequent five-record bone program further rejected perturbation stability as a substitute for structural support, rejected the scalar 3-D directional endpoint, and found that scale-aware and network contracts improved selective risk but failed their frozen coverage gates. The UV-PAM control confirmed only the narrow ability to abstain when both calibration and requested biological semantics are absent. These negative results are retained in the evidence graph. A new hash-separated PSHG acquisition-shift confirmation now supplies the missing focused advantage experiment for one unstained local-orientation endpoint: the full input-only contract reduced invalid outputs from 47 to 7 versus acquisition QC and from 24 to 7 versus endpoint QC at matched 63.9% coverage. A separate implementation reproduced every decision and all 5,000 ROI bootstraps while verifying all 312 confirmation source files.

The admissible central claim today is:

> NOSTOS provides a physically indexed, auditable interface for applying a common set of structural measurements to heterogeneous biological images without tissue-specific retraining, while exposing module-specific validity, perturbation stability and abstention rather than a universal diagnostic score.

This is credible and useful. It is not yet the novelty-and-utility package expected by *Nature Methods* or *Nature Biomedical Engineering*.

## Claim-by-claim audit

| Proposed claim | Evidence | Audit outcome | Allowed wording |
|---|---|---|---|
| One frozen interface measures heterogeneous 2-D and 3-D samples | Generic CLI, typed schema and public BBBC007 smoke execution | Supported as software functionality | “accepts calibrated 2-D images and 3-D volumes” |
| The response geometry is a superior universal representation | Prospective response-geometry and biological-retrieval gates failed | Rejected | Do not claim superiority or universal specimen identity |
| Spectral responses recover programmed scale and orientation | Analytic phantoms and perturbation matrix | Supported in synthetic scope | “recovers programmed spectral properties in phantoms” |
| Local orientation transfers to biological collagen | Scale-declared SHG test and pristine PSHG breast confirmation passed | Supported for the frozen local endpoint | “measures local raster orientation after declared coordinate calibration” |
| The measurement contract reduces silently invalid orientation outputs under acquisition shift | Frozen 24-ROI PSHG confirmation; 360 cases; full-contract risk 3.04% versus 20.43% acquisition QC and 10.43% endpoint QC at matched coverage; independent code-path audit verified | Supported in one unstained PSHG acquisition family under programmed shifts | Do not imply another instrument, native clinical degradation or mechanics |
| Hessian morphology improves biological object localization | Strong localization but no prespecified superiority over LoG on BBBC007 or BBBC020 | Comparator superiority rejected | Retain as a morphology coordinate, not a best detector |
| Local thickness agrees with independent implementations | Eight public volumes agree with archived IPL maps; frozen BoneJ comparison passed all six gates with CCC 0.926 and 7.14% median relative difference | Supported for one effectively isotropic archive | Independent acquisition and anisotropic implementation remain open |
| Perturbation stability establishes valid bone-SHG orientation support | Mouse-separated annotated SHG development found no promotable threshold | Rejected | Add and independently validate an explicit support/ROI contract |
| A 3-D network validity contract prevents corrupted-mask outputs | Development stress test halved risk but accepted only 53.8% | Development only; coverage gate failed | Real error references and independent-acquisition confirmation |
| Human nanoCT directional response is robust across resolution | Scalar v1 failed; scale-indexed v2 reduced risk but accepted only 36.5–39.9% at supported scales | Not validated | New support rule and untouched scale-declared confirmation |
| Missing calibration and unsupported semantics trigger abstention | Full contract withheld all requested physical-collagen UV-PAM endpoints while allowing explicitly pixel-domain descriptors | Supported as governance behavior only | Does not demonstrate measurement accuracy |
| Network responses remain stable on manual biological networks | Initial HRF experiment exposed a center-distance sampling defect; corrected definition then passed all seven frozen gates on untouched STARE labels | Supported for reference-mask sampling stability | Do not extend to automatic segmentation or universal topology |
| Spatial responses are repeatable and focus-sensitive | Analytic variogram truth plus frozen 64-triplet BBBC006 confirmation passed all six gates | Supported for estimator repeatability/sensitivity | No claim of externally known biological correlation length |
| Dynamic registration recovers calibrated displacement fields | Bulk translation passed synthetic and BBBC035 tests; dense deformation passed disjoint analytic and eight-plane BBBC035 confirmations with frozen uncertainty bounds | Supported for bulk and dense image registration | Strain and mechanics remain unimplemented |
| Imported objects can be linked through native microscopy time series | Locked SIM+ and two real HeLa sequences yielded continuation-link F1 0.997, 0.988 and 0.977; a 92-frame application workflow passed | Supported for continuation tracking from imported masks | Automatic segmentation and hidden CTC test performance are not claimed |
| Geometric lineage inference resolves divisions | Synthetic and pristine real transfer both missed frozen division-F1 gates | Rejected for release default | Experimental only |
| Cartilage spectral entropy tracks OA histopathology | Site-matched public-cohort associations and technical perturbations | Exploratory biological support | Require independent mask review and formal contrasts before application-paper submission |
| Osteochondral interface is accurate to 16–27 µm | Reference masks are threshold-derived mineralized-tissue regions; extraction policy changes error and ranking | Withdrawn | Public masks can train tissue segmentation, not validate a unique continuous interface |
| NOSTOS is clinically or intraoperatively usable | No prospective clinical workflow, outcomes, human factors or regulatory validation | Unsupported | “research use only” |

## Module maturity

| Module | Implementation | Synthetic truth | Independent public reference | Comparator | Status |
|---|---:|---:|---:|---:|---|
| Calibration and QC | Yes for declared spacing and acquisition diagnostics | Synthetic failure controls pass | Identity-disjoint BBBC006 focus confirmation pass | Five-metric development comparison | Validated relative focus endpoint; no universal cutoff |
| Spectral organization | Yes | Pass | Local SHG/PSHG pass; global transfer failures retained | Focused FFT/scattering/radiomics | Endpoint validated, not universal |
| Structure tensor | Yes | Pass | Pristine PSHG local-orientation and hash-separated acquisition-shift confirmations | scikit-image 0.25.2 cross-software pass | Externally, selectively and cross-software validated in one PSHG acquisition family |
| Hessian morphology | Yes | Pass | BBBC039/007/020 tested | LoG included | Useful coordinate; superiority failed |
| Geometry/thickness | Yes | Pass | Eight bone volumes | Archived IPL and BoneJ 1.4.3 | Cross-software externally validated on one archive |
| Bone orientation support | Yes | Synthetic orientation truth passes | Annotated mouse SHG development failed | Always-emit and endpoint QC | Measurement estimator exists; autonomous support contract rejected |
| 3-D scale-indexed direction | Yes | Axis-equivariance tests pass | Human nanoCT development missed coverage | Scalar and Nyquist-only contracts | Development only |
| Network integrity | Yes | Pass | Untouched STARE reference-mask confirmation pass | scikit-image skeletonize 0.25.2 | Externally confirmed for sampling stability |
| Spatial heterogeneity | Yes | Pass | BBBC006 adjacent-focus/defocus confirmation pass | Direct empirical semivariogram definition | Externally confirmed for repeatability and focus sensitivity |
| Dynamics | Bulk translation, 2-D dense deformation and continuation object tracking | Pass for registration and continuation links | BBBC035 plus CTC SIM+/two HeLa sequences | Phase correlation, TV-L1, iLK and centroid-only tracking | Lineage/division inference failed |
| ROI adapters | Yes | Perturbation tested | Cartilage review pending; osteochondral reference inadequate | Otsu/classical baselines | Unvalidated for boundary claims |
| Reproducibility layer | Yes | Pass | Author-operated only | — | Independent receipt missing |

## Frozen completion program on public data

The following experiments are necessary before a high-impact methods submission. Their protocols and gates must be committed before outcome inspection.

### 1. Dynamic module

The separate time-series input contract prevents a three-dimensional spatial volume from being confused with a two-dimensional time series. Frozen bulk translations, blank-field abstention and a six-gate BBBC035 test passed. Dense deformation was then prospectively evaluated. The initial analytic run passed six of seven gates but rejected forward–backward inconsistency as an error-ranking uncertainty score. A post-failure development set selected estimator disagreement and froze a 95% conformal upper bound. Disjoint analytic confirmation passed all six gates, and eight untouched BBBC035 planes under programmed smooth warps passed all seven public-content gates: median error 0.270 pixels, casewise 95th-percentile error 0.595 pixels, uncertainty coverage 97.25%, eligibility 98.66% and lower median error than iLK. Native continuation tracking was then confirmed from imported masks on exact SIM+ and two real HeLa sequences, with F1 0.997, 0.988 and 0.977. Division inference missed both frozen transfer gates and is disabled by default. This supports calibrated registration fields and imported-mask continuation trajectories, not automatic segmentation, reliable lineage inference, strain or mechanics.

### 2. Network module

This gate is now materially closed for the reference-mask pathway. The initial 45-case HRF experiment failed because center-to-center Euclidean distance created a coarse-grid discontinuity. After a boundary-distance correction and an HRF-only occupancy-policy development step, the frozen method passed all seven gates on the untouched official STARE labels: survival-area Spearman correlation 0.988, skeleton-length correlation 0.995, median skeleton-length relative error 1.77%, and AH-versus-VK survival-area correlation 0.874. The pinned comparator was scikit-image 0.25.2 `skeletonize`. The HRF image-derived pathway had median Dice 0.265, so automatic vessel segmentation remains explicitly unvalidated and separate from measurement validity.

### 3. Spatial module

This gate is closed at the defensible estimator level. Correlation length and anisotropy pass analytic truth tests. A frozen external confirmation on 64 hash-selected BBBC006 DAPI triplets passed all six gates: adjacent in-focus range correlation 1.00, median normalized curve distance 0.012, defocus distance greater in every case, and paired median defocus-minus-adjacent distance 0.104 (bootstrap interval 0.100–0.107). The claim remains estimator repeatability and focus sensitivity because no independent biological correlation-length truth exists.

### 4. Geometry comparator

This comparator gate is closed for the declared isotropic scope. The identical eight masks were converted losslessly to calibrated TIFF stacks and run through checksum-locked BoneJ 1.4.3/ImageJ 1.53c. All six gates passed: NOSTOS–BoneJ CCC 0.926, median absolute relative difference 7.14%, and mean absolute difference 0.0157 mm. NOSTOS was closer to BoneJ than the archived IPL means were. The result is cross-software numerical concordance, not independent biological truth; anisotropic voxels remain outside BoneJ's documented capability.

### 5. Bone validity-contract stress program

The new bone validity-contract program does not close a flagship gate. The compact paired SHG/TPF run eliminated observed accepted-case instability at only 35.8% coverage and used a partly circular invalidity definition. An independent v2 design separated contract-visible probes from withheld annotation and perturbation tests, but no threshold met its development criterion. In rat confocal LCN masks, an escalated corruption series created a useful risk gradient and the nested-field contract reduced silent-invalid risk from 0.50 to 0.25, yet coverage was 53.8%. In human nanoCT, the scalar 3-D direction failed blur and resampling stress; a physical-scale-indexed redesign reduced risk at 0.4 and 0.8 micrometres but accepted only 36.5% and 39.9%. These results support the architecture's explicit scale and failure ledger, not a validated universal support rule. The UV-PAM experiment is a narrow positive control for missing-calibration and unsupported-semantics abstention.

### 5a. Focused PSHG measurement-contract advantage

This focused software-level novelty gate is closed within one deposited unstained PSHG acquisition family. A frozen SHA-256 split separated 24 development from 24 confirmation ROIs. Fifteen predeclared clean and shifted conditions generated 360 confirmation cases, 77 of which failed the withheld polarization-reference error criterion. At the full contract's 63.9% coverage, invalid outputs fell from 47 for acquisition QC and 24 for endpoint QC to 7 for NOSTOS. ROI-bootstrap intervals excluded zero for both matched-risk reductions and both risk–coverage-area advantages. Clean-input coverage was 91.7% with 7.29° median axial error. Removing scale consistency materially worsened risk–coverage area; removing split-stack consistency did not, and that negative ablation remains disclosed. A separate audit implementation verified all locked hashes, all 312 confirmation files, all 360 case decisions, all summaries, all 5,000 bootstraps and reference-label blindness. This is prospective evidence under programmed acquisition shifts, not a second instrument or native intraoperative series.

### 6. ROI validity

Complete the locked, outcome-free cartilage review packet with independent human masks and report Dice/IoU, boundary distance, tile-inclusion agreement and feature agreement. Create a manually traced continuous osteochondral interface set if that endpoint remains in scope. Threshold-derived hard-tissue masks are not an adequate substitute.

### 7. End-to-end tool study

The author-operated public workflow study is complete. Four frozen contracts—unmasked BBBC007 2-D fluorescence, expert-masked HRF vasculature, masked 3-D public bone and BBBC035 2-D+t registration—passed all seven schema, module, calibration and runtime gates. The full-resolution HRF workflow was slowest at 43.4 s; all others completed in 5.5 s or less. A separate clean-release execution remains required after the final rebuild, and an independent operator must still return the signed receipt without author assistance.

## Novelty audit

NOSTOS cannot defend novelty as the invention of FFT, structure tensors, Hessian filters, local thickness, skeletonization or variograms. It also cannot defend novelty as concatenating those methods: that hypothesis failed.

The potentially defensible methodological contribution is the **measurement contract**:

1. responses remain functions of physical scale, direction and threshold rather than being prematurely reduced to a feature vector;
2. each response carries calibration, coordinate convention, validity and abstention;
3. perturbation stability is an output attached to the requested measurement;
4. cross-domain execution does not require tissue-specific retraining;
5. biological interpretation and eligibility are declared per endpoint, preventing a common measurement from being misrepresented as a common biomarker;
6. negative prospective tests remain part of the released evidence graph.

The contract now produces a measurable advantage for one principal endpoint: fewer silently invalid local-orientation outputs under acquisition shift, with calibrated selective risk and matched-coverage advantages over focused acquisition and endpoint QC. Classification accuracy is not the platform-wide story and has already failed. The remaining novelty question is transfer: whether the same contract advantage persists on a second independently acquired instrument family and under external execution.

## Submission gates

NOSTOS-0 is **author-operated tool complete on public data** for the bounded endpoints reported here. Public-data completion comprises:

- dynamic bulk-registration input and response contract implemented and tested;
- every advertised core module has analytic truth validation and at least one public biological execution receipt;
- QC, tensor, network, geometry and dynamics have pinned or explicitly defined comparator receipts;
- generic CLI workflows pass author-operated public-data and clean-environment tests;
- all public datasets have source URL, accession/DOI, license, checksums and immutable inclusion manifests;
- all gates were frozen before confirmatory outcomes were opened;
- manuscript values are generated from receipts and no failed gate is converted into a positive claim;

The last two items—an independent operator receipt and an archival DOI—are external release gates and are not evidence that can be manufactured by the author-operated public-data pipeline.

Nature-family submission should additionally require:

- at least two independently acquired confirmations for the principal endpoint;
- a second independently acquired confirmation of the now-passed PSHG validity advantage;
- credible external-user utility;
- complete Methods, data/code availability, reporting summaries and figure-source provenance;
- claims restricted to research measurement unless a separate prospective clinical study exists.

## Irreducible limits of public data

Public data can complete software functionality, analytic validity, comparator concordance and multi-domain research utility. It cannot by itself establish intraoperative performance, clinical decision impact, tissue mechanics when mechanics were not acquired, regulatory fitness, or independent usability by an external laboratory. Those are not coding tasks and must remain explicit future gates.

## Sample adequacy is endpoint-specific

NOSTOS does not pool pixels, tiles or object links to manufacture a single platform-wide sample size. The 90-participant cartilage cohort is adequate for a pilot participant-level association, but the biological interpretation remains provisional until the ROI masks are independently reviewed. The eight bone volumes support bounded numerical agreement with archived thickness maps and BoneJ, not population-level skeletal generalization. Twenty STARE reference masks support a prespecified sampling-stability endpoint; 48 breast SHG ROIs support ROI-resampled local-orientation error; and the CTC sequences support continuation-link performance within those sequences, not universal lineage tracking. Synthetic cohorts provide exact algorithmic truth but no biological prevalence estimate.

Accordingly, the present weakness is not a hidden pixel-level power defect. The principal focused claim now has a prospective public biological confirmation under frozen acquisition shifts, but only in one acquisition family. It still lacks second-instrument confirmation and an unaided external-user result. Enlarging the same archive would improve precision but would not close either independence gate.

## Final audit verdict

NOSTOS-0 is complete as an author-operated, public-data research tool for its bounded endpoints; it is not yet ready for a Nature-family submission. The public-data program now includes bulk and dense dynamic registration with calibrated uncertainty, externally confirmed network and spatial responses, BoneJ thickness concordance, cross-software tensor concordance, identity-disjoint focus confirmation, four end-to-end input contracts and a verified PSHG acquisition-shift advantage over acquisition and endpoint QC. The irreducible remaining gates are a second independently acquired confirmation of the principal validity advantage, an unaided external-user replication receipt, an archival release DOI, independent cartilage mask review if the OA application remains in the paper and—if clinical or intraoperative language is desired—new prospective clinical evidence. The platform-level novelty claim must remain calibrated validity and abstention under a shared physical measurement contract, not universal classification.
