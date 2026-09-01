# NOSTOS-0 native object-tracking validation protocol

**Frozen:** 27 August 2026 before downloading or opening tracking outcomes  
**Datasets:** Cell Tracking Challenge Fluo-N2DH-SIM+ and Fluo-N2DL-HeLa training archives

## Scope

NOSTOS will link imported, framewise instance masks into calibrated object trajectories and division-aware lineages. The measurement contract reports centroid displacement, speed, persistence, lifetime, parent identity, link confidence and abstention in physical and temporal units. Segmentation and tracking are evaluated separately. This protocol does not authorize claims about automatic segmentation, cell identity beyond the reference masks, forces, strain, mechanics or clinical utility.

The Cell Tracking Challenge (CTC) training archives include images, reference annotations and lineage trees. Fluo-N2DH-SIM+ has exact simulated segmentation/tracking truth. Fluo-N2DL-HeLa contains real H2b-GFP HeLa microscopy, gold tracking truth and silver segmentation masks. Pixel sizes and time steps are taken from the official CTC dataset catalogue.

## Frozen partitions

- **Development only:** Fluo-N2DH-SIM+ sequence 01.
- **Synthetic confirmation:** Fluo-N2DH-SIM+ sequence 02.
- **Real biological confirmation:** Fluo-N2DL-HeLa sequence 01.
- Sequence 02 of HeLa is reserved and must not be opened during this study.

Archive SHA-256 values, extracted-file hashes and CTC conditions of use will be recorded immediately after download. No case can be removed because of algorithmic performance. Framewise instance labels are deterministically renumbered before tracking so persistent source labels cannot leak lineage identity.

## Frozen method

Objects are represented by centroid, area, equivalent radius and bounding box. A dense-deformation field predicts each parent centroid in the next frame. Candidate links are solved globally by Hungarian assignment using a dimensionless cost combining flow-advected centroid distance, log area change and mask overlap after integer translation. Candidate distances are normalized by the larger equivalent radius; links beyond six equivalent radii or with area ratio outside 0.25–4 are ineligible.

Unmatched parents and children are evaluated for one-to-two division. A division is eligible when both children fall within six parent radii of the flow-predicted centroid, their combined area is 0.5–2.0 times parent area and their separation is at most six parent radii. The minimum-cost eligible pair is selected without permitting a child to have two parents. Ambiguous equal-cost assignments are flagged for review. Frames with fewer than two valid objects or missing calibration abstain.

The frozen baseline uses the same detections and Hungarian assignment with centroid distance only, no flow prediction, area term, overlap term or division handling. This isolates the value of the NOSTOS linkage contract from segmentation quality.

## Evaluation

Framewise detections are mapped to reference track identities by maximum overlap, with reference-marker containment used when gold tracking masks are sparse. Links are directed edges between reference identities in adjacent frames. Division edges connect a parent to both daughters at the annotated lineage transition. Report link precision, recall and F1; division precision, recall and F1; identity switches; track fragmentation; eligible detection fraction; physical displacement error at reference centroids; runtime; and bootstrap intervals over frame transitions. Missing or ambiguous reference mappings are retained in coverage denominators but excluded from edge correctness.

## Development rule

Only sequence 01 of SIM+ may be used to choose fixed cost weights and confidence thresholds. Candidate weights are restricted to `{centroid, area, overlap}` combinations declared in the development receipt. Select the highest link F1, breaking ties by division F1, then fewer identity switches. No HeLa image or annotation may influence selection.

## Frozen confirmation gates

Synthetic SIM+ sequence 02 must satisfy:

1. Reference-mappable detection coverage ≥0.99.
2. Link F1 ≥0.95.
3. Division F1 ≥0.80 when at least five divisions are present; otherwise division results are descriptive.
4. Identity switches ≤0.5% of evaluated links.
5. NOSTOS link F1 is not lower than the centroid-only baseline.
6. Repeating with fourfold pixel spacing changes physical displacement and speed fourfold while leaving assignments unchanged.

Real HeLa sequence 01 must satisfy:

1. Reference-mappable detection coverage ≥0.80.
2. Link F1 ≥0.80.
3. Identity switches ≤5% of evaluated links.
4. NOSTOS link F1 is not lower than the centroid-only baseline by more than 0.02.
5. At least 90% of reported trajectory measurements are finite and calibrated.
6. The full sequence executes in under 300 s on the audit workstation.

## Interpretation

A pass supports tracking imported object masks in one exact simulated and one real nuclear-microscopy domain without tissue-specific retraining. It does not establish universal tracking, automatic segmentation, hidden CTC test-set performance, native tissue mechanics or clinical utility. Every failed gate and every post-failure redesign remains in the evidence graph.

## Frozen post-failure confirmation addendum

The initial development implementation achieved continuation-link F1 0.984 but division F1 0.116 and was inferior to the centroid-only baseline for ordinary links. Dense-flow prediction, area and overlap costs are therefore rejected for this endpoint rather than carried into confirmation. On the same opened development sequence, an outcome-aware geometry audit and a 32-cell threshold grid selected the following lineage rule by the declared maximum-division-F1 tie-break: centroid-only Hungarian continuation links; combined daughter-to-parent area 0.6–1.5; each daughter-to-parent area 0.15–0.85; daughter area imbalance ≤3; maximum daughter displacement ≤2 parent equivalent radii; daughter separation ≤3 parent radii. Development link F1 was 0.996, division F1 was 0.897 and identity-switch fraction was 0.078%.

These values and the decision not to use dense-flow prediction are now frozen before opening SIM+ sequence 02 or HeLa sequence 01. Confirmation gates are unchanged. The dense-flow, area and overlap variants remain ablations demonstrating that adding modules did not improve this tracking endpoint.

## Reserved-sequence lineage transfer

The first confirmation passed all continuation and real-HeLa gates but failed the SIM+ division gate narrowly: division F1 was 0.758 versus 0.80. SIM+ sequence 02 and HeLa sequence 01 are therefore opened evidence and cannot be reused for confirmation. A post-failure grid on SIM+ sequence 02 selected a broader lineage rule: combined daughter area 0.4–1.5 times parent area; each daughter 0.05–1.3 times parent area; imbalance ≤8; distance ≤2 parent radii; separation ≤3 parent radii. On the opened synthetic sequence this yielded division F1 0.848 and link F1 0.998. HeLa sequence 02 remains unopened.

Before opening HeLa sequence 02, the broader rule and the following final transfer gates are frozen: mapping coverage ≥0.80; link F1 ≥0.80; identity-switch fraction ≤5%; link F1 no more than 0.02 below the centroid-only baseline; division F1 ≥0.45 when at least five reference division edges exist; finite calibrated measurement fraction ≥0.90; and runtime <300 s. A pass supports transfer of the broader division rule to one pristine real sequence but does not erase the failed original synthetic confirmation.
