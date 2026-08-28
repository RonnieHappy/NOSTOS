# NOSTOS blinded reference-mask review

## Purpose

This review converts algorithmic proposals into human reference masks for validation. Proposal masks are never accepted by default. The reviewer must inspect and correct every boundary and export both the indexed mask and signed audit JSON.

## Priority order

1. Complete the 40 images from the eight `validation` participants before reviewing any training image.
2. Review Safranin-O and H&E before PLM if time is limited; the flagship manuscript's primary mask endpoint is Safranin-O articular cartilage.
3. A second qualified reviewer independently reviews at least 10 validation images spanning stain, site, and severity. Disagreements are adjudicated without access to NOSTOS feature values or outcome predictions.

## Blinding

The reviewer may see stain and site because they are required for interpretation. Do not provide participant outcome scores, FFT results, model predictions, or disease-class assignments. Proposal masks may be loaded as editable starting points but must remain visually distinguishable from the source image through the opacity control.

## Required inspection

- Trace uncalcified articular cartilage from the articular surface to the tidemark/calcified transition.
- Separate calcified cartilage from subchondral bone when resolvable.
- Exclude folds, tears, dust, chatter, detached fragments, saturated regions, and ambiguous tissue as artifact/unusable.
- Exclude marrow, fat, void, and trabecular lumina from cartilage.
- Inspect the articular surface and cartilage-bone interface at native resolution.
- Confirm that disconnected fragments are intentionally included or excluded.

## Files and exports

- Prepared sources: `<DATA_ROOT>\data\annotations\images\`
- Editable proposals: `<DATA_ROOT>\data\annotations\proposals\`
- Required reviewed-mask destination: `<DATA_ROOT>\data\annotations\masks\`
- Manifest: `<DATA_ROOT>\data\annotations\annotation_manifest.csv`

For every source image, export `<stem>_reviewed.png` and `<stem>_review.json`. The audit must contain the exact source checksum, dimensions, reviewer identifier, timestamp, ontology, and completed-review statement. The validation command rejects missing or mismatched audits.

## Acceptance analysis

The locked validation participants remain excluded from training. Primary endpoints are articular-cartilage Dice, IoU, 95th-percentile surface distance, physical surface/tidemark error, and complete-section failure rate. Metrics will be stratified by stain, site, severity, and artifact burden. The predefined gate remains cartilage Dice ≥0.90, IoU ≥0.82, median boundary error ≤100 µm, and valid masks in ≥85% of eligible sections without a concentrated subgroup failure.

After every case is marked `complete` or `adjudicated`, run:

```powershell
uv run nostos-review-evaluate <review-packet> --output <review-results>
```

The evaluator verifies the locked source and proposal hashes, computes Dice, IoU, symmetric HD95, articular-surface and tidemark error in micrometres, tile-inclusion agreement and angular-entropy feature drift, then emits case-level metrics and a gate receipt. Missing cases or changed inputs cause a hard failure.
