# NOSTOS BioSR tensor v9 scale-conditioned confirmation

## Why v9 exists

The v8 stress pilot was assessable and failed. Conventional QC emitted 57 invalid coherence measurements across five fields, but the complete v7 contract accepted every eligible row. Its observed risk was therefore identical to QC at 0.0740, and its AURC was worse. Severe isotropic blur, directional blur and 4× resampling caused stable bias that was not exposed by applying another small perturbation to an already degraded image.

That failure is preserved under the v8 lock and receipt. It cannot be reclassified as success.

## Development repair

The repair treats acquisition support as a function of the requested physical scale. The unchanged v7 acquisition-QC risk is weighted by the square root of the minimum sampling demand divided by the actual samples spanning the requested scale:

\[
r_{\mathrm{scale}} = r_{\mathrm{acq}}
\left(\frac{4}{n_{\mathrm{samples/scale}}}\right)^{1/2}.
\]

The normalized support score is \(r_{\mathrm{scale}}/0.30\). The boundary 0.30 was the most permissive member of a declared 0.150–0.350 grid that passed every development gate at the physically selected square-root exponent. On the v8 development cells it retained 95.7% coverage, reduced observed risk from 7.40% to 4.48%, kept the field-bootstrap upper 95% risk at 6.38%, and achieved a bootstrap probability of 1.0 that its AURC was lower than conventional QC.

These values are outcome-informed development results. They do not confirm the repair.

The v7 strong-blur margin is retained in the record as a diagnostic but no longer governs coherence acceptance. It produced no rejection in the assessable v8 failure and ranked risk adversely. The v7 orientation-distribution contract is unchanged and remains a secondary safety analysis.

## Untouched confirmation

Four new linear and four new nonlinear F-actin cells are selected by hash after excluding all v7 and v8 cells. The first and last signal levels are analyzed. All fourteen v8 transformations are reused unchanged; only the stochastic seed changes. The estimators, physical scales, reference images, invalidity tolerances, registration rule and conventional-QC comparator are identical.

Before the v9 lock, only central-directory identifiers and MRC headers may be read. Selected-cell pixels and outcomes are forbidden. After locking, no parameter, cell, signal level, degradation or gate may change.

## Confirmation decision

The study is assessable only if conventional QC emits at least ten invalid coherence rows across at least four reference fields. A pass requires all of the following:

- At least 80% negative-control coverage and no more than 10% negative-control risk.
- At least 80% overall coverage.
- No more than 5% observed risk and no more than 10% field-bootstrap upper 95% risk.
- At least 25% relative risk reduction versus conventional QC.
- At least 25% invalid rows among measurements accepted by QC but rejected by v9.
- Positive QC-minus-v9 AURC, at least 0.95 bootstrap probability that v9 is better, and a bootstrap 95% interval excluding zero.
- No higher v9 risk in either acquisition family.

A pass supports selective tensor-coherence validity only within this paired-acquisition stress setting. It does not establish a universal contract across tissues or modalities. A failure prevents promotion and triggers a new development cycle on these cells, followed by any later test on different untouched cells.
