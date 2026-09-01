# NOSTOS BioSR tensor v8 controlled-degradation pilot

## Purpose

The untouched v7/v7.1 F-actin confirmation established safe paired-acquisition transfer but contained no invalid emissions from conventional acquisition QC. It therefore could not test whether the complete validity contract adds selective value. This v8 study is a small engineering stress pilot, not a publication-level confirmation.

The frozen question is whether the unchanged tensor-coherence contract reduces silently invalid estimates relative to conventional acquisition QC when previously unseen BioSR inputs are subjected to fixed, coordinate-preserving degradations.

## Independence boundary

Three linear and three nonlinear F-actin cells are selected from central-directory identifiers after excluding all v7 confirmation cells. Selection uses a declared SHA-256 salt. Only the first and last available signal levels are included. Before the v8 lock is written, selected-cell image payloads and endpoint outcomes may not be decoded. Archive names and MRC headers are permitted for layout and physical-calibration verification.

The source estimators remain governed by the v7 linear and v7.1 nonlinear configurations. Physical scales, endpoint definitions, invalidity tolerances, support components, the acceptance boundary, reference choice and comparators cannot change.

## Frozen challenge

Each mean raw-SIM image is evaluated unchanged and after two monotonic gamma controls, four isotropic Gaussian blurs, two directional Gaussian blurs, two downsample/restore operations and three additive-noise levels. All transformations retain the original array size and specimen coordinate system. Noise seeds are derived from the base seed, source pair identifier and degradation identifier by SHA-256.

Registration is audited once on the undegraded source pair and reused for its transformed copies. This is deliberate: the transformations preserve coordinates, and allowing registration success to act as a hidden degradation detector would confound the validity-policy comparison.

The primary endpoint family is tensor coherence. Orientation-distribution behavior is reported as a prespecified secondary analysis. Reference error remains withheld from the validity score and is used only to label silent invalidity after the lock.

## Frozen pilot decision

The pilot is assessable only if conventional QC emits at least ten invalid coherence cases distributed across at least four reference fields. A pass additionally requires:

- At least 80% coverage and at most 10% risk on clean/gamma negative controls.
- At least 30% full-contract coverage across the complete deliberately harsh challenge.
- At most 10% observed full-contract risk and at most 25% field-bootstrap upper 95% risk.
- At least 25% relative risk reduction versus conventional QC.
- At least 25% invalid cases among measurements accepted by QC but rejected by the full contract.
- Positive conventional-QC-minus-full AURC and at least 0.90 field-bootstrap probability that the full contract is better.
- No higher full-contract risk in either assessable acquisition family.

A pass authorizes a larger untouched confirmation without changing the contract. A failure identifies an engineering defect; repair must occur on development evidence and be retested on different cells under a new lock. A non-assessable result authorizes severity-envelope development, not the addition of more clean samples.

## Claim boundary

This pilot can validate or falsify selective behavior of one frozen tensor contract under specified synthetic acquisition degradations. It cannot establish biological ground truth, restoration accuracy, diagnosis, clinical validity, universal cross-tissue performance or publication-level independence.
