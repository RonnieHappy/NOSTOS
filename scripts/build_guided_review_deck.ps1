param(
  [string]$OutputPath = "<PROJECT_ROOT>\docs\NOSTOS0_guided_external_review_136_slides.pptx"
)

$ErrorActionPreference = 'Stop'
$root = '<PROJECT_ROOT>'
$fig = Join-Path $root 'figures\nostos0'
$navy = 0x2A2115
$teal = 0x8D6B10
$orange = 0x238CEB
$red = 0x4040C0
$gray = 0x6B6660
$light = 0xF7F5F1
$white = 0xFFFFFF

function Add-Text($slide,$text,$x,$y,$w,$h,$size,$color,$bold=$false,$font='Arial') {
  $s=$slide.Shapes.AddTextbox(1,$x,$y,$w,$h)
  $s.TextFrame.TextRange.Text=$text
  $s.TextFrame.MarginLeft=0; $s.TextFrame.MarginRight=0; $s.TextFrame.MarginTop=0; $s.TextFrame.MarginBottom=0
  $s.TextFrame.WordWrap=-1
  $s.TextFrame.TextRange.Font.Name=$font
  $s.TextFrame.TextRange.Font.Size=$size
  $s.TextFrame.TextRange.Font.Color.RGB=$color
  if($bold){ $s.TextFrame.TextRange.Font.Name='Arial'; $s.TextFrame.TextRange.Font.Size=$size }
  return $s
}

function Add-Base($pres,$title,$section,$number,$accent=$teal) {
  $slide=$pres.Slides.Add($pres.Slides.Count+1,12)
  $slide.FollowMasterBackground=0
  $slide.Background.Fill.ForeColor.RGB=$light
  $bar=$slide.Shapes.AddShape(1,0,0,16,540); $bar.Fill.ForeColor.RGB=$accent; $bar.Line.Visible=0
  Add-Text $slide $section 44 24 700 18 10 $accent $true | Out-Null
  Add-Text $slide $title 44 52 850 66 26 $navy $true | Out-Null
  $rule=$slide.Shapes.AddShape(1,44,126,850,1); $rule.Fill.ForeColor.RGB=0xD8D3CC; $rule.Line.Visible=0
  Add-Text $slide ("NOSTOS guided review  •  {0}/136" -f $number) 44 512 850 16 9 $gray | Out-Null
  return $slide
}

function Add-Bullets($slide,$items,$x=62,$y=158,$w=800,$h=320,$size=20) {
  $text=($items | ForEach-Object { "•  $_" }) -join "`r`n"
  $s=Add-Text $slide $text $x $y $w $h $size $navy $false
  $s.TextFrame.TextRange.ParagraphFormat.SpaceAfter=10
  return $s
}

function Add-PictureFit($slide,$path,$x,$y,$w,$h) {
  $p=$slide.Shapes.AddPicture($path,0,-1,$x,$y,-1,-1)
  $p.LockAspectRatio=-1
  $ratio=$p.Width/$p.Height; $boxRatio=$w/$h
  if($ratio -ge $boxRatio){ $p.Width=$w } else { $p.Height=$h }
  $p.Left=$x+($w-$p.Width)/2; $p.Top=$y+($h-$p.Height)/2
  $frame=$slide.Shapes.AddShape(1,$x,$y,$w,$h); $frame.Fill.Visible=0; $frame.Line.ForeColor.RGB=0xCFC9C0; $frame.Line.Weight=0.75
  $frame.ZOrder(1)
}

function Add-Callout($slide,$label,$text,$color=$teal) {
  $line=$slide.Shapes.AddShape(1,62,410,5,58); $line.Fill.ForeColor.RGB=$color; $line.Line.Visible=0
  Add-Text $slide $label 82 406 180 20 12 $color $true | Out-Null
  Add-Text $slide $text 82 429 780 44 17 $navy $true | Out-Null
}

function Add-ImageSlide($pres,$title,$section,$number,$path,$caption,$path2) {
  $s=Add-Base $pres $title $section $number
  Add-PictureFit $s $path 54 145 418 300
  Add-PictureFit $s $path2 488 145 418 300
  Add-Text $s $caption 54 458 852 34 13 $gray $false | Out-Null
}

function Add-TeachingSlide($pres,$title,$section,$number,$items,$callout,$path1,$path2,$accent=$teal) {
  $s=Add-Base $pres $title $section $number $accent
  Add-Bullets $s $items 54 150 348 238 16 | Out-Null
  Add-PictureFit $s $path1 430 150 222 238
  Add-PictureFit $s $path2 674 150 222 238
  Add-Callout $s 'THE DECISION TO MAKE' $callout $accent
}

$slides = New-Object System.Collections.Generic.List[object]
function Queue($section,$title,$items,$callout,$accent=$teal) {
  $slides.Add([pscustomobject]@{Type='text';Section=$section;Title=$title;Items=$items;Callout=$callout;Accent=$accent})
}
function QueueImage($section,$title,$path,$caption) {
  $slides.Add([pscustomobject]@{Type='image';Section=$section;Title=$title;Path=$path;Caption=$caption})
}

Queue 'START HERE' 'This deck turns NOSTOS into a sequence of reviewable decisions' @('One idea appears on each slide.','Every result is separated from its interpretation.','Failures are shown because they define the present boundary of the tool.') 'At the end, you should know exactly what NOSTOS measures, what evidence supports it, and what remains unfinished.'
Queue 'START HERE' 'The current answer is encouraging, but it is not “Nature-ready”' @('The software and reproducibility layer are substantial.','Several public-data demonstrations work.','Cross-domain universality and clinical utility are not yet established.') 'Review the platform as a strong methods prototype—not as a finished clinical device.' $orange
Queue 'START HERE' 'Use three labels throughout the deck' @('SUPPORTED: the planned test passed with traceable evidence.','LIMITED: the result is useful but narrow or underpowered.','FAILED OR PENDING: the claim must not be made yet.') 'Do not let visual polish upgrade a limited result into a supported claim.'
Queue 'START HERE' 'NOSTOS began with a clinically motivated question' @('Can microscopy reveal structural organization rapidly enough to guide intra-operative interpretation?','The first available evidence was public cartilage histology.','That evidence motivated a broader measurement engine.') 'Clinical motivation is not clinical validation.'
Queue 'START HERE' 'The project contains four distinct products' @('NOSTOS-0: general calibrated microscopy measurement engine.','NOSTOS-Cartilage/OA: cartilage application paper.','NOSTOS-1: tissue structure–function validation.','NOSTOS-2: intra-operative optical-mechanical system.') 'Never combine evidence from these stages as though one study completed all four.'
Queue 'START HERE' 'The safest present claim is deliberately narrow' @('NOSTOS computes calibrated multiscale structural response fields.','It records uncertainty, perturbation stability, provenance and abstention.','The same implementation can be applied to several public image domains.') 'The tool measures consistently; biological meaning still requires domain-specific validation.'
Queue 'START HERE' 'The strongest unsupported claim would be “universal phenotype engine”' @('Different tissues may share image geometry but not biology.','A feature can be technically comparable without being biologically equivalent.','Current retrieval experiments do not prove a universal latent space.') 'Use “sample-agnostic measurement” rather than “universal biological interpretation.”' $red
Queue 'START HERE' 'The evidence hierarchy prevents accidental overclaiming' @('Ground-truth phantoms test measurement accuracy.','Perturbations test technical stability.','Public datasets test external behavior.','Clinical cohorts test patient-level utility.','Prospective studies test decision impact.') 'Evidence from a lower rung cannot substitute for evidence from a higher rung.'
Queue 'START HERE' 'The unit of inference matters before any calculation' @('Pixels are not patients.','Tiles from one specimen are correlated.','Serial sections are repeated measurements, not independent subjects.','Patient-level claims require patient-level inference.') 'Reject analyses that inflate sample size by treating patches as independent participants.'
Queue 'START HERE' 'A beautiful figure is not an experiment' @('Maps can reveal spatial structure.','Three-dimensional terrains can make fields intuitive.','Neither provides validation unless linked to a prespecified quantitative test.') 'Ask what hypothesis each visual tests and where its numerical result is recorded.'
Queue 'START HERE' 'The review will move from pixels to claims' @('First: what an image contains.','Second: what each NOSTOS module calculates.','Third: how calculations are validated.','Fourth: what public data show.','Finally: what must happen before publication.') 'Pause whenever a step does not follow from the preceding one.'
Queue 'START HERE' 'Checkpoint 1: the project is understandable only after its boundaries are explicit' @('Tool engineering is not clinical validation.','Cross-domain execution is not cross-domain biological equivalence.','A public-data demonstration is not prospective utility.') 'Proceed only if these distinctions remain visible in the manuscript and software.'

$fund = @(
@('A digital micrograph is a calibrated array','Each pixel stores intensity or color.','Pixel spacing converts index distances into micrometres.','Without spacing, scale-dependent measurements cannot be compared.','Require physical spacing or label outputs uncalibrated.'),
@('Calibration is part of the measurement—not metadata decoration','A 5-pixel fiber can be 2.5 µm or 50 µm wide.','Resampling changes apparent texture.','NOSTOS therefore carries spacing through every scale.','Verify that every receipt records pixel or voxel spacing.'),
@('A mask states where measurement is allowed','The mask may be supplied, classically segmented, or imported.','Errors at boundaries can dominate texture and geometry.','Mask quality must be validated independently.','Do not infer ROI validity from downstream feature stability alone.'),
@('Two-dimensional images, volumes and time series pose different problems','2D measures planar appearance.','3D requires voxel anisotropy and volumetric topology.','Time series require registration before dynamics.','Confirm that each claim names the supported dimensionality.'),
@('Intensity is not structure','Brightness can reflect stain, illumination or acquisition.','Geometry concerns arrangement, scale and connectivity.','Some algorithms remain intensity-sensitive.','Demand contrast and illumination perturbation tests.'),
@('Scale determines what structure is visible','Fine scales detect edges and small fibers.','Coarse scales detect bundles, sheets and regional heterogeneity.','Collapsing scales early can hide failure.','Preserve response curves before reporting summary scalars.'),
@('Direction is circular data','Zero and 180 degrees may represent the same fiber axis.','Ordinary averages can be wrong near wraparound.','Orientation error needs circular statistics.','Check that axial rather than linear angular distance is used.'),
@('A response field keeps location','Each position receives a local measurement.','Fields expose heterogeneity that a global mean hides.','Summary statistics are derived later.','Inspect fields before accepting participant-level summaries.'),
@('A response curve keeps scale or threshold','The x-axis is physical scale, erosion, confidence or distance.','The y-axis is module response.','Curve shape can be more informative than a single optimum.','Require the full response geometry in machine-readable output.'),
@('Uncertainty describes sensitivity to plausible changes','Perturb the image, mask, scale or acquisition.','Recompute the measurement.','Summarize spread and failure frequency.','Uncertainty must follow the output, not appear only in a supplement.'),
@('Abstention is a valid scientific output','Blur may erase the requested structure.','An ROI may be too small for the chosen scale.','Anisotropic voxels may invalidate a 3D estimate.','The software should explain why it refused to measure.'),
@('A provenance receipt makes a result traceable','Record input hash, software version and parameters.','Record calibration, mask identity and validity flags.','Record output hashes and runtime.','A reviewer should reconstruct every reported result.'),
@('Technical repeatability is not biological validity','Two sections can produce similar values.','That does not prove the feature measures the intended biology.','Validity needs reference annotations or orthogonal measurements.','Keep repeatability and validity as separate claims.'),
@('Association is not mechanism','A feature may correlate with disease grade.','Several lesion structures may generate the same spectral signal.','Ablations are needed to identify contributors.','Use “correlate” until causal structure is isolated.'),
@('Prediction is not necessarily useful','Cross-validated R² can be positive but modest.','Confidence intervals and baseline comparisons matter.','Clinical usefulness requires a decision context.','Do not market exploratory prediction as diagnosis.'),
@('Checkpoint 2: every output needs units, scope and a failure rule','What was measured?','In what physical units?','Over what region and scale?','When should the value be ignored?','Reject any output lacking one of these answers.')
)
foreach($x in $fund){ Queue 'FOUNDATIONS' $x[0] $x[1..($x.Count-2)] $x[-1] }

$modules = @(
@('SPECTRAL ORGANIZATION','FFT and angular spectra',@('The Fourier transform rewrites an image as spatial frequencies.','Radius corresponds to scale; angle corresponds to direction.','Power describes how strongly a frequency is represented.','Interpret spectra only after calibration and windowing.'),@('A local FFT turns global texture into a map','Divide the ROI into calibrated windows.','Compute power spectra per window.','Summarize angular entropy, anisotropy and characteristic scale.','Confirm that window size is expressed in physical units.'),@('Angular entropy measures directional disorder','Concentrated angular power gives low entropy.','Uniform angular power gives high entropy.','Edges, fissures and surfaces can all affect it.','Treat entropy as organization-sensitive, not collagen-specific.'),@('Radial power describes characteristic spacing','Peaks can reflect repeated spacing or periodic texture.','Power-law slope describes scale distribution.','Resolution limits truncate the useful band.','Validate programmed wavelength recovery on phantoms.'),@('Windowing and boundaries can manufacture spectral power','Hard crop edges create strong frequencies.','Tapering reduces leakage.','Surface bands may dominate cartilage tiles.','Require surface and boundary-exclusion ablations.'),@('Rotation should rotate direction without changing disorder','Orientation should track programmed rotation.','Entropy should remain stable under pure rotation.','Interpolation can introduce small bias.','Set a prespecified circular-error gate.'),@('Resolution transfer is a core test','Downsample, then compare at matched physical scales.','Do not compare the same pixel-scale setting.','Flag scales unsupported by the coarser image.','Accept only calibrated overlap regions.'),@('Spectral checkpoint','Is the scale band supported by resolution?','Were boundary artifacts controlled?','Did phantoms recover angle and wavelength?','Approve spectral claims only when all three are answered.')),
@('LOCAL ORIENTATION','Structure tensor and coherence',@('Local gradients reveal dominant orientation.','The tensor aggregates gradients within a neighborhood.','Eigenvectors give direction; eigenvalue contrast gives coherence.','Choose neighborhoods in physical units.'),@('Coherence distinguishes aligned from isotropic texture','High coherence means one direction dominates.','Low coherence may mean disorder, junctions or low signal.','Noise can create unstable angles.','Report confidence or abstain where coherence is insufficient.'),@('Tensor and FFT orientation are complementary','Tensor methods are local and edge-driven.','FFT summarizes directional frequency content.','Agreement strengthens interpretation; disagreement is informative.','Do not force both methods into one score prematurely.'),@('Orientation needs specimen coordinates','Image rotation changes image-coordinate angles.','Anatomical axes allow interpretable comparisons.','Missing specimen axes limit biological claims.','Store image and specimen-coordinate directions separately.'),@('Junctions are legitimate failure locations','One angle cannot represent crossing fibers.','Low coherence can signal multimodality.','Multidirectional spectra may be preferable.','Abstain rather than invent a single orientation.'),@('Noise and blur have different signatures','Noise destabilizes gradients.','Blur removes fine-scale direction.','Perturbations should reproduce these expected effects.','Failure behavior must be monotonic and explainable.'),@('Local maps should precede global summaries','Inspect whether direction follows visible structure.','Check boundary and background leakage.','Then aggregate within the valid ROI.','Require blinded visual spot checks alongside metrics.'),@('Orientation checkpoint','Does direction rotate correctly?','Does confidence fall at crossings and low signal?','Are physical scales and coordinate systems declared?','Approve only calibrated, confidence-aware orientation.')),
@('MORPHOLOGY','Hessian blob, tube and sheet responses',@('Second derivatives describe local curvature of intensity.','Hessian eigenvalues encode blob-, tube- or sheet-like patterns.','The same response can arise from different tissue structures.','Interpret morphology labels geometrically, not biologically.'),@('Scale selection estimates object size','Apply filters across calibrated scales.','The strongest response suggests a characteristic radius or thickness.','Discrete scale sampling introduces quantization.','Validate scale recovery against analytic phantoms.'),@('Tubeness is not a vessel detector by definition','Collagen bundles, hyphae and trabeculae may appear tubular.','Intensity polarity also matters.','Domain meaning requires biological annotation.','Call the output tubeness response, not vessel burden.'),@('Sheetness is dimension-dependent','A sheet in 3D may look like a line in 2D.','Slice orientation changes appearance.','True 3D validation needs volumetric phantoms.','Limit 2D claims to planar morphology.'),@('Blobness is sensitive to segmentation and contrast','Cell nuclei may be bright or dark.','Background correction alters curvature.','Scale and polarity must be explicit.','Test both intensity polarity and contrast perturbation.'),@('Hessian features require comparator methods','Compare with Frangi or Sato implementations.','Use identical scale grids and phantoms.','Measure accuracy, stability and runtime.','Novelty must come from the unified framework, not renaming filters.'),@('Response curves reveal ambiguous morphology','A structure may respond at several scales.','Peak width expresses scale certainty.','Competing module responses can reveal mixed form.','Retain curves and validity flags.'),@('Morphology checkpoint','Was ground-truth class recovered?','Was radius or thickness recovered in physical units?','Were polarity and blur failures detected?','Approve only within the validated scale domain.')),
@('GEOMETRY','Thickness, curvature and roughness',@('Distance transforms measure distance to boundaries.','Local thickness fits maximal inscribed objects.','Results depend directly on mask quality.','Validate masks before interpreting geometry.'),@('Thickness must use anisotropic spacing correctly','A voxel can have different x, y and z dimensions.','Ignoring anisotropy biases 3D thickness.','Resampling may introduce partial volume.','Test analytic objects under anisotropic voxels.'),@('Curvature describes how a boundary bends','Curvature depends on smoothing scale.','Pixelated boundaries create artificial spikes.','Report the smoothing and uncertainty.','Validate known circles, sinusoids and surfaces.'),@('Roughness is scale-dependent','Fine roughness can be noise.','Coarse roughness can represent lesions or waviness.','A single roughness number hides the spectrum.','Preserve roughness-versus-scale response.'),@('Geometry baselines can explain complex features','Surface roughness may explain spectral entropy.','Fissure burden may explain anisotropy.','Tissue area may explain topology.','Test incremental value beyond simple geometry.'),@('Boundary perturbation tests sensitivity, not accuracy','Erode and dilate the mask.','Measure feature stability.','A consistently wrong mask can still look stable.','Pair perturbation with independent manual validation.'),@('Geometry maps should match visible anatomy','Thickness maxima should lie centrally.','Curvature peaks should follow bends or defects.','Unexpected maps often reveal implementation errors.','Perform visual sanity checks on every domain.'),@('Geometry checkpoint','Is the mask valid?','Are spacing and smoothing explicit?','Were analytic ground truths recovered?','Approve geometry only after all three checks.')),
@('NETWORKS','Skeletons, graphs and topology',@('Skeletonization reduces a mask to a centerline.','Nodes, branches and cycles form a graph.','Small segmentation errors can create spurious branches.','Prune using declared physical rules.'),@('Connectivity is threshold-dependent','Confidence or erosion thresholds remove weak links.','A response curve shows when the network fragments.','One threshold can hide instability.','Report survival across thresholds.'),@('Percolation asks whether paths span the specimen','Define the spanning direction in specimen coordinates.','Cropping can change the answer.','ROI geometry must be controlled.','Validate with programmed graph phantoms.'),@('Persistent homology tracks features across thresholds','Components and loops are born and die.','Long persistence suggests stability.','Persistence is descriptive unless linked to a hypothesis.','Keep topology out of the main claim without inferential validation.'),@('Graph metrics depend on skeleton conventions','Junction definitions vary.','Diagonal connectivity changes branch counts.','Endpoint pruning changes length distributions.','Freeze conventions and benchmark against truth.'),@('Networks require explicit object definition','A collagen texture is not automatically a binary network.','Thresholding determines the graph.','Imported segmentations carry their own uncertainty.','Separate segmentation validity from graph computation.'),@('Topological visuals can overpersuade','Complex graphs and barcodes look sophisticated.','They may add no predictive or mechanistic value.','Main figures should show validated findings.','Move exploratory topology to supplements or the interface.'),@('Network checkpoint','Was the network object validly segmented?','Did the graph recover programmed branches and cycles?','Is the threshold response stable?','Approve only prespecified network claims.')),
@('SPATIAL AND DYNAMIC','Heterogeneity, registration and motion',@('Spatial statistics ask how values vary with distance.','Variograms estimate correlation length.','Moran-type statistics estimate spatial autocorrelation.','Distances must be physical and sampling must be adequate.'),@('A variogram separates local variation from regional structure','The nugget captures near-scale variability.','The sill captures total structured variance.','The range estimates correlation length.','Validate parameters on programmed random fields.'),@('Zonal gradients require a meaningful anatomical axis','Superficial-to-deep claims need a valid surface.','Normalized depth may aid cross-specimen comparison.','Uncertain boundaries propagate into zones.','Report zonal uncertainty and formal contrasts.'),@('Registration is the first dynamic measurement','Align frames before measuring change.','Rigid, affine and deformable models answer different questions.','Registration can erase true motion.','Validate displacement on programmed sequences.'),@('Phase correlation estimates translation efficiently','Fourier phase isolates shifts.','Large deformations violate the model.','Periodic boundaries can create ambiguity.','Abstain outside the validated motion range.'),@('Optical flow estimates local motion','Brightness constancy is an assumption.','Photobleaching and contrast change can mimic motion.','Smoothness can erase discontinuities.','Use synthetic motion plus photometric perturbations.'),@('Dynamics require time calibration and uncertainty','Frame interval converts displacement into velocity.','Missing or irregular frames affect fitting.','Relaxation models need enough time points.','Report temporal support and model adequacy.'),@('Spatial–dynamic checkpoint','Was registration independently validated?','Are distance and time calibrated?','Were photometric confounds tested?','Approve dynamics only inside validated motion and time ranges.'))
)
foreach($m in $modules){ foreach($item in $m[2..($m.Count-1)]){ Queue $m[0] $item[0] $item[1..($item.Count-2)] $item[-1] } }

$validation = @(
@('Synthetic truth is the cleanest place to test correctness','Program orientation, wavelength, radius, thickness and topology.','Generate exact reference values.','Measure error directly.','Require a frozen truth registry before biological tuning.'),
@('A phantom generator must cover both easy and adversarial cases','Include clean single structures.','Add crossings, mixtures and edge truncation.','Vary scale near resolution limits.','Do not validate only on ideal examples.'),
@('Perturbations test expected invariances','Rotate, resample, crop, blur and add noise.','Alter contrast, PSF and voxel anisotropy.','Perturb masks and partial volume.','Specify whether each output should remain stable or abstain.'),
@('Pass/fail gates must be frozen before the final run','Choose error tolerances from scientific requirements.','Separate development data from confirmation data.','Version the gate specification.','Do not move thresholds after seeing failures.'),
@('Comparators determine whether NOSTOS adds value','Use established orientation, Hessian, thickness and radiomics tools.','Match calibration and parameter ranges.','Compare accuracy, robustness, runtime and coverage.','A suite is novel only if unification improves something measurable.'),
@('Naïve concatenation is an essential baseline','Concatenate all conventional scalar features.','Compare with retained response geometry.','Use the same train/test partitions.','Show that curves and validity structure add information.'),
@('Module ablations locate the source of performance','Remove one module at a time.','Remove normalization, uncertainty or abstention.','Measure the loss in ground-truth recovery or transfer.','Avoid claiming synergy without paired comparisons.'),
@('Calibration laws need their own experiment','Resample the same object at several resolutions.','Evaluate absolute physical and dimensionless scales.','Identify the overlapping support region.','Report where scale transfer fails.'),
@('Reliability needs confidence intervals','Point estimates can be unstable.','Bootstrap at the independent specimen level.','For repeated measures, preserve clustering.','Report uncertainty for errors, ICCs and performance differences.'),
@('Repeated cross-validation reduces split luck','Use nested selection when parameters are tuned.','Repeat outer splits.','Keep all data from one participant together.','Report out-of-fold predictions and interval estimates.'),
@('Dependent correlations need direct contrasts','Two correlations sharing an outcome are not independent.','A significant versus nonsignificant pair is not a difference.','Bootstrap the paired difference.','Use formal contrasts for structure versus staining claims.'),
@('Segmentation validation is an independent study component','Sample sections across severity and source conditions.','Obtain blinded manual review.','Measure Dice, IoU, boundary and feature agreement.','Do not substitute boundary erosion for correctness.'),
@('Failure cases belong in the main scientific record','Show blur, low signal, tiny ROI and ambiguous orientation.','State the triggered validity flag.','Confirm the software abstains predictably.','A defensible tool explains where it does not work.'),
@('Runtime matters only after correctness','Measure CPU and GPU separately.','Include I/O and preprocessing.','Report image size and hardware.','Do not trade validation for impressive throughput.'),
@('Reproducibility requires a clean-room run','Start from the release archive.','Use documented installation commands.','Recreate evidence without developer state.','Hash the resulting reports and figures.'),
@('Checkpoint 3: validation is a chain, not a single score','Ground truth tests correctness.','Perturbations test stability.','Comparators test added value.','External data test transport.','Approve only claims supported by the complete relevant chain.')
)
foreach($x in $validation){ Queue 'VALIDATION LOGIC' $x[0] $x[1..($x.Count-2)] $x[-1] }

QueueImage 'CURRENT EVIDENCE' 'Figure 1 shows the intended response geometry' (Join-Path $fig 'figure_1_response_geometry_reference.png') 'Public microscopy sources and derived NOSTOS fields; source identities are recorded in the figure manifest.'
QueueImage 'CURRENT EVIDENCE' 'Figure 2 tests synthetic ground-truth recovery' (Join-Path $fig 'figure_2_synthetic_validation.png') 'Synthetic validation is the strongest evidence for algorithmic correctness, provided the gates were frozen prospectively.'
QueueImage 'CURRENT EVIDENCE' 'Figure 3 connects NOSTOS with established bone morphometry' (Join-Path $fig 'figure_3_bone_validation.png') 'The bone analysis demonstrates domain execution and comparison; inspect exact sample counts and independence in the evidence receipt.'
QueueImage 'CURRENT EVIDENCE' 'Figure 4 defines the cross-domain boundary honestly' (Join-Path $fig 'figure_4_cross_domain_boundaries.png') 'Successful measurement across domains does not establish one universal biological latent space.'
Queue 'CURRENT EVIDENCE' 'The synthetic benchmark supports selected measurement claims' @('Orientation and scale can be compared with programmed truth.','Perturbation curves expose resolution and noise limits.','Passing modules can be claimed within their tested domain.') 'Trace each plotted value to a machine-readable benchmark receipt.'
Queue 'CURRENT EVIDENCE' 'Failed representation experiments are scientifically useful' @('A unified representation may not retrieve equivalent phenotypes across domains.','Failure prevents an inflated universality claim.','The result guides redesign of normalization and distance metrics.') 'Keep the failure visible; do not quietly replace the endpoint.' $red
Queue 'CURRENT EVIDENCE' 'Public cartilage supports a narrow application claim' @('The cohort contains independent participants and paired tissue information.','Angular spectral entropy associates with structural histopathology.','Repeatability is strong across adjacent sections.','Mechanism and clinical utility remain unproven.') 'Present cartilage as an application, not as validation of the entire platform.' $orange
Queue 'CURRENT EVIDENCE' 'Cartilage segmentation is the largest application-level vulnerability' @('Feature perturbation does not establish mask correctness.','A blinded 40-case review packet exists.','Independent evaluation must quantify mask and feature agreement.') 'Do not submit the cartilage paper until manual validation is completed.' $red
Queue 'CURRENT EVIDENCE' 'Bone provides an orthogonal structural domain' @('Established measurements offer interpretable comparators.','Volumetric spacing and anisotropy are central tests.','Sample independence and dataset licensing must be explicit.') 'Use bone to validate geometry, not to imply cartilage biology transfers.'
Queue 'CURRENT EVIDENCE' 'Filamentous datasets test orientation and network behavior' @('Hyphae, collagen or vessels provide elongated structures.','The same geometric measurement can apply without retraining.','Biological interpretation remains domain-specific.') 'Claim common measurement semantics, not common biological meaning.'
Queue 'CURRENT EVIDENCE' 'Nuclei provide a contrasting blob-like domain' @('Blobness and scale can be compared with annotated objects.','Crowding and overlap test abstention.','Segmentation quality remains a separate dependency.') 'Show where one-object geometry breaks down in dense fields.'
Queue 'CURRENT EVIDENCE' 'Dynamic phantoms test registration and tracking cleanly' @('Program displacement, deformation and photometric change.','Compare recovered motion with truth.','Map the validated operating envelope.') 'Biological movies are a demonstration only until ground-truth or orthogonal validation exists.'
Queue 'CURRENT EVIDENCE' 'The software evidence layer is unusually mature for a prototype' @('A versioned command-line interface exists.','Receipts record provenance and validity.','Tests and clean-room workflows are documented.','Release archives are hashed.') 'Verify the current release—not a development checkout.'
Queue 'CURRENT EVIDENCE' 'Passing tests do not prove the scientific claim' @('Unit tests detect implementation regressions.','Benchmark gates test measurement behavior.','Dataset analyses test external validity.','Each layer answers a different question.') 'Never cite the test count as evidence of biological validity.'
Queue 'CURRENT EVIDENCE' 'Sample size must be evaluated per claim' @('Phantom n concerns coverage of programmed conditions.','Image n concerns acquisition diversity.','Specimen n concerns biological variability.','Patient n concerns clinical inference.') 'There is no single NOSTOS sample size.'
Queue 'CURRENT EVIDENCE' 'Checkpoint 4: the public-data build is a platform demonstration' @('Several modules have tractable evidence.','Some transfer and representation claims failed.','Cartilage segmentation awaits independent validation.','Clinical usefulness is outside the current evidence.') 'A high-impact methods paper requires a sharper primary invention and stronger external use.' $orange

$review = @(
@('Begin external review with the claim ledger','Read one claim at a time.','Open the linked evidence file.','Confirm the unit, sample and test.','Mark supported, limited or unsupported.'),
@('Then inspect the source table for every figure','Confirm each image is public, synthetic or computed.','Confirm derived panels name their generating command.','Reject any untraceable or AI-generated scientific panel.','The figure manifest should be sufficient to rebuild the asset.'),
@('Review Figure 1 as a pipeline, not a result','Identify the source image.','Identify the ROI and calibration.','Identify each response field.','Ask which panels are demonstrations versus validated outputs.'),
@('Review Figure 2 against the frozen gates','Find the programmed truth.','Find the predicted value.','Find the prespecified tolerance.','Confirm failures were not removed.'),
@('Review Figure 3 for sample independence','Count specimens, not slices or patches.','Check whether train and test units overlap.','Verify spacing and volume handling.','Compare against established bone measurements.'),
@('Review Figure 4 for honest negative evidence','Identify the intended universality test.','Confirm the endpoint and comparator.','Check whether the result passed.','Ensure the title and abstract reflect the failure.'),
@('Review cartilage outcomes site by site','Match medial features with medial outcomes.','Match lateral features with lateral outcomes.','Treat cross-site measures as convergence, not replication.','Keep participant-level inference.'),
@('Review cartilage mechanism with ablations','Exclude the free surface.','Exclude fissures and voids.','Exclude lacunae and cell clusters.','Compare simple roughness, staining and geometry baselines.'),
@('Review prediction with paired uncertainty','Use repeated nested cross-validation.','Report out-of-fold MAE and R² intervals.','Compare FFT with conventional texture using paired differences.','Move sparse binary analyses to the supplement.'),
@('Review segmentation independently','Use the blinded review packet.','Include severity and acquisition strata.','Measure Dice, IoU, boundary and tile agreement.','Measure downstream feature agreement.'),
@('Review software from the release archive','Verify the SHA-256 hash.','Install in a clean environment.','Run doctor, measurement and benchmark commands.','Compare produced evidence hashes.'),
@('Review abstention deliberately','Feed blurred, undersampled and tiny-ROI inputs.','Confirm the tool refuses invalid measurements.','Check the reason is specific and machine-readable.','Document unexpected silent outputs as defects.'),
@('Review novelty against the correct baselines','Compare individual conventional methods.','Compare naïve feature concatenation.','Compare radiomics and scattering.','Compare the unified response geometry with ablations.'),
@('Review venue fit after scientific review','A cartilage association paper fits a disease journal.','A multi-domain method needs a clear technical invention.','A clinical engineering paper needs prospective utility.','Choose venue by completed evidence, not aspiration.'),
@('The present submission decision is “not yet”','The software can be shared and externally tested.','The public-data study can be strengthened.','The high-impact platform claim still needs independent use and decisive benchmarks.','Do not submit an overbroad manuscript.'),
@('The fastest defensible path has four gates','Complete independent cartilage-mask validation.','Freeze and rerun the decisive comparator/ablation study.','Obtain one external clean-room replication.','Archive the frozen release and evidence with a DOI.'),
@('A larger venue requires a larger scientific contribution','Demonstrate why response geometry outperforms feature bundles.','Show calibrated transfer across genuinely different modalities.','Show external users can obtain valid results.','Show failure-aware behavior competitors lack.'),
@('Clinical readiness has additional gates','Use prospectively acquired intra-operative images.','Compare against reference pathology or mechanics.','Measure latency and failure rate.','Test whether output changes a decision or outcome.'),
@('What you can approve now','The conceptual separation of measurement and interpretation.','The provenance-first software architecture.','Selected phantom-validated modules.','Continued public release for external evaluation.'),
@('What you should not approve now','Universal biological phenotype claims.','Clinical or intra-operative utility claims.','Mechanistic cartilage claims without ablations.','Submission to a top methods or engineering journal as currently evidenced.'),
@('Your 30-minute review route','Slides 1–12: scope and claim boundaries.','Slides 77–92: validation logic.','Slides 93–108: current evidence.','Slides 109–124: audit and decision.'),
@('Your full review route','Read in order and stop at each checkpoint.','Open the linked audit and evidence files.','Record disagreements by claim identifier.','Rerun only the analyses relevant to disputed claims.'),
@('A good external reviewer can disagree constructively','Disagreement should name the claim.','It should identify missing or contradictory evidence.','It should propose a decisive test.','Aesthetic preference alone does not settle validity.'),
@('The manuscript should be rebuilt after the evidence freezes','Write the question and prespecified tests first.','Report passed and failed results symmetrically.','Keep exploratory visualizations supplementary.','Match every sentence to the claim ledger.'),
@('The final tool paper should make one central contribution','A calibrated response geometry retains scale, direction, threshold and validity.','It should beat scalar feature bundles on prespecified transfer or robustness tests.','All other modules support that central test.','Do not submit a catalogue of algorithms.'),
@('Final checkpoint: can a skeptical lab reproduce and falsify NOSTOS?','Can they install it?','Can they trace every input?','Can they reproduce each figure?','Can they observe a documented failure?','Can they run a new sample without tissue-specific retraining?'),
@('The honest verdict','NOSTOS is a serious, technically promising open measurement framework.','It is more mature as software than as a universal biological claim.','The remaining work is identifiable and testable.','Proceed through the four gates before high-impact submission.'),
@('The immediate next action','Give this deck and the release archive to one computational reviewer.','Give the blinded mask packet to one tissue expert.','Collect their signed outputs without changing the frozen code.','Then make the submission decision from evidence, not momentum.')
)
foreach($x in $review){ Queue 'HOW TO REVIEW IT' $x[0] $x[1..($x.Count-2)] $x[-1] }

if($slides.Count -ne 136){ throw "Expected 136 slides, queued $($slides.Count)" }

$ppt=New-Object -ComObject PowerPoint.Application
$ppt.Visible=-1
$pres=$ppt.Presentations.Add()
$pres.PageSetup.SlideWidth=960
$pres.PageSetup.SlideHeight=540
$coreVisuals=Get-ChildItem -LiteralPath (Join-Path $root 'tmp\guided_review_visual_crops') -Filter '*.png' | Sort-Object Name | Select-Object -ExpandProperty FullName
for($i=0;$i -lt $slides.Count;$i++){
  $d=$slides[$i]; $n=$i+1
  $v1=$coreVisuals[($i*2)%$coreVisuals.Count]; $v2=$coreVisuals[(($i*2)+1)%$coreVisuals.Count]
  if($d.Type -eq 'image') { Add-ImageSlide $pres $d.Title $d.Section $n $d.Path $d.Caption $v2 | Out-Null }
  else { Add-TeachingSlide $pres $d.Title $d.Section $n $d.Items $d.Callout $v1 $v2 $d.Accent | Out-Null }
}
$pres.SaveAs($OutputPath,24)
$pres.Close(); $ppt.Quit()
[Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
[Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
Write-Output $OutputPath
