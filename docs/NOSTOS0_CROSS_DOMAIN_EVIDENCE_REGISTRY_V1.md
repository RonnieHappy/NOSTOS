# NOSTOS-0 cross-domain evidence registry v1

**Registry status:** pass  
A registry pass means that every listed source was found and its actual positive, mixed or negative decision was preserved. It is not a claim that every scientific experiment passed.

| Domain / endpoint | Independent evidence | Frozen result | Defensible decision |
|---|---|---|---|
| analytic 2-D morphology and random fields — Hessian class/scale and gradient anisotropy/axis | 36 morphology, 270 spatial and 24 equivariance cases | pass | supported_analytic_only |
| public 3-D bone volumes — local thickness | 8 volumes | pass | supported_external_comparator |
| public retinal vessel reference masks — network survival and skeleton length under sampling | 20 images | pass | supported_external_reference_masks |
| public fluorescence microscopy with programmed translation — bulk registration | public image series with disjoint programmed shifts | pass | supported_programmed_motion |
| unstained PSHG-TISS breast microscopy — local axial orientation under computational acquisition shifts | 24 ROIs; 360 nested conditions | pass_row_level_with_failed_independent_unit_bound | supported_bounded_row_comparison_not_formal_roi_control |
| public widefield fluorescence microscopy — acquisition-by-scale conditional validity | 4 FOVs; 240 nested cases | pass | supported_small_external_confirmation |
| unstained tendon pSHG with XRD-associated organization — orientation validity and organization recovery | 2 specimens; 37 fields | fail | mixed_overall_gate_failed |
| in-vivo collagen SHG — multi-endpoint structure and selective validity | 8 mice; 45 clean fields | fail | rejected_overall |
| PSHG orientation — cross-software orientation consistency | 48 ROIs; 1367747 nested pixels | pass | supported_noninferiority_not_superiority |
| small synthetic construct benchmark — four-class structural discrimination | 16 held-out synthetic cases | mixed | universal_superiority_rejected |
| five held-out validity domains — zero-shot invalidity-risk transfer | leave-one-domain-out transfer | fail | universal_learned_risk_rejected |

## What the evidence supports

- Calibrated analytic recovery with explicit abstention for the released Hessian and spatial-gradient responses.
- External reference agreement for local thickness, imported-mask network sampling and cross-software orientation.
- Bounded row-level validity improvements in PSHG and a small FMD confirmation.
- Deterministic, data-free software packaging and clean-room execution.

## What it rejects or leaves open

- Universal feature-family superiority: PyRadiomics tied the small synthetic benchmark.
- Universal learned risk transfer: the frozen leave-one-domain-out study failed.
- A 20% independent-ROI PSHG risk guarantee: the exact upper bound was 47.9%.
- Broad collagen deployment: the tendon and in-vivo SHG confirmations failed at least one frozen master gate.
- Mechanics, diagnosis, patient benefit and intraoperative use: no relevant ground truth exists in NOSTOS-0.

## Submission use

The methods manuscript may claim a calibrated measurement framework with explicit validity contracts and bounded public-data demonstrations. It must not describe the response geometry as universally superior, the risk score as distribution-free control, or the system as clinically or intraoperatively validated.

Machine-readable registry: `outputs/nostos0-cross-domain-evidence-registry-v1/registry.json`.
