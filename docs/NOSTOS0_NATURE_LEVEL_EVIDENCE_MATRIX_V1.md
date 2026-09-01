# NOSTOS-0 Nature-level evidence matrix v1

**Audit date:** 2026-09-01  
**Purpose:** separate completed evidence from attractive but unsupported platform
claims before any high-impact submission.

## Current decision

NOSTOS-0 is a reproducible, submission-ready **Small Methods** validity-compiler
paper. It is not yet a defensible Nature Methods or Nature Biomedical
Engineering paper. The gap is scientific evidence, not document styling.

The strongest current claim is:

> Acquisition QC alone can silently certify invalid microscopy measurements.
> NOSTOS compiles measurement-specific, input-known support contracts that
> expose unsupported conditions and reduce silent invalidity on frozen public
> confirmation data.

The current evidence does not support a universal morphology representation,
optimal universal risk score, tissue competence prediction, clinical utility or
intraoperative deployment.

## Evidence matrix

| Requirement | State | Evidence | Nature-level disposition |
|---|---|---|---|
| Executable software and tests | Complete | 432 passed, 4 optional Torch-dependent skips and 0 failures after v2.6 integration; deterministic scripts and receipts | Necessary, not differentiating |
| Frozen development/confirmation partitions | Complete for five public validation domains | BioSR, FMD, PSHG-TISS, tendon pSHG-XRD, Heaton SHG | Strong retrospective practice |
| Independent-unit inference | Complete with caveats | Field, ROI, specimen or mouse bootstraps; nested rows retained | Tendon has only two specimens; FMD has four fields |
| Input-only validity logic | Complete | Label-complement fingerprints unchanged; reference values and errors excluded from features | Strong |
| Benefit over ordinary acquisition QC | Supported in several domains | FMD, PSHG-TISS and tendon have large AURC/risk improvements; BioSR modest; Heaton fails | Publishable methods result |
| Benefit over endpoint QC | Supported in PSHG-TISS and tendon; not Heaton | Frozen confirmation receipts | Domain-limited |
| Superiority over domain-trained learned risk | Rejected | Selective-risk baseline audit v1 passed 1/5 superiority domains | Claim blocked |
| Universal learned risk transfer | Rejected | Cross-domain transfer v1 never beat NOSTOS and approached local learning in 1/5 domains | Claim blocked |
| Interpretable zero-shot contract | Supported comparatively | NOSTOS AURC lower than better pooled transfer in 5/5 held-out domains | Retrospective support, not a formal guarantee |
| Formal risk guarantee | Tested and not supported | Retrospective fixed-policy PSHG audit reproduced 230/360 accepted rows and 7 row errors, but 7/24 independent ROIs contained at least one accepted error; the one-sided 95% exact upper bound was 0.479, above the 0.20 target | Major methods gap; do not call bootstrap risk control a guarantee |
| Unified response geometry adds value beyond feature concatenation | Rejected in current implementation | Response-geometry v2 AURC/balanced-accuracy benchmark failed; tensor ablation improved result | Claim blocked; redesign required |
| Synthetic physical ground truth across core analytic modules | Substantially complete for the released endpoints | v2.1 supports organization, controls, perturbations, thickness and corrected network; after five preserved failed confirmations, v2.6 passed all 14 disjoint Hessian/spatial/equivariance gates and a 15-check independent audit | Strong analytic evidence; not biological or instrument-transfer evidence |
| Cross-domain structural measurement with accepted reference standards | Partial | Orientation transfer and XRD-associated tendon organization exist; broad bone structural validation remains incomplete | Major application gap |
| External laboratory/acquisition confirmation | Partial | Multiple public acquisition resources, but no blinded independent implementer or unseen laboratory execution | Major venue gap |
| Biological or mechanical endpoint | Missing for general tool | Cartilage histology association is a separate application; no registered microscopy-to-mechanics validation | Blocks competence/clinical claims |
| Prospective or intraoperative evidence | Missing | No label-free operative acquisition, latency, contamination, device or decision study | Blocks NBE framing |
| Public archival release | Pending external action | Exact code/data snapshot and DOI still need publication; the working repository currently has no Git HEAD and contains uncommitted/untracked material, so an immutable release tree has not yet been established | Submission blocker, not scientific blocker |
| Journal production quality | Complete for v39 | Article, SI, 600-dpi TIFFs, PDF renders, style/accessibility/visual audits | Ready for Small Methods submission |

## Comparator result that must remain visible

The domain-trained comparator audit was a genuine negative result. Domain-local
logistic or boosted models using the same input-known diagnostics achieved lower
AURC than NOSTOS in PSHG-TISS, tendon and Heaton. The Heaton reduction was large
(approximately 0.645 to 0.330), although it is same-cohort experiment transfer.

The leave-one-domain-out experiment then showed that these gains did not transfer
through a shared four-channel learned geometry. The better zero-shot learned
model had higher AURC than NOSTOS in all five domains, while still beating
ordinary acquisition QC in four. This supports an explicit operating hierarchy:

1. use the interpretable contract when no target-domain invalidity labels exist;
2. use frozen local calibration when adequate independent target-domain
   development labels exist;
3. do not claim universal learned calibration.

## Nature-level blockers, ordered by scientific leverage

1. **A formal selective-risk method.** The retrospective PSHG audit failed the
   stronger independent-ROI bound, so a future method must predeclare
   independent-unit calibration, exact finite-sample control and an abstain
   outcome when calibration support is insufficient.
2. **Independent extension of the physical truth registry.** The core analytic
   registry now passes, but curvature, richer 3-D topology, anisotropic-voxel
   comparators and an independently implemented phantom generator would make
   the result harder to dismiss as self-consistency.
3. **One compelling cross-domain measurement result.** On an external public
   label-free bone or fibrous dataset, recover a reference-standard structural
   endpoint without tissue-specific feature engineering and show calibrated
   failure rather than silent output.
4. **Independent reproduction.** An unaided external user or clean environment
   must execute the archived release and produce a signed/hashed receipt.
5. **For Nature Biomedical Engineering specifically:** registered mechanics or
   clinical decision evidence is still mandatory. A computation-only public-data
   paper cannot honestly claim intraoperative utility without such ground truth.

## Submission boundary

The v39 Small Methods package should not absorb the two new negative experiments
before editorial submission unless the paper's scope is deliberately expanded.
They are essential to the platform development record and to future high-impact
work, but adding them to the current concise paper would shift its thesis from a
concrete validity compiler to a broader and partly failed universal-calibration
program.

For any high-impact platform manuscript, both failed experiments must be
reported. Omitting them would make the novelty claim materially misleading.

The v2.0–v2.5 synthetic failures must likewise remain visible. The successful
v2.6 receipt is a repaired disjoint confirmation, not permission to delete the
failed lineage.
