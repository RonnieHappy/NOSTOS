# NOSTOS-0 bone orientation v2 result

## Verdict

The preregistered development gate failed. No orientation-support threshold achieved both at least 70% coverage and a mouse-cluster upper 95% silent-invalid risk of at most 0.15. The locked evaluation mice were therefore not scored with a promoted threshold.

This is a useful falsification, not a software success. Mild perturbation stability and scale agreement are insufficient to establish that a local SHG tile contains biologically interpretable collagen orientation.

## Audit trail

- Dataset: Zenodo 3355937, DOI 10.5281/zenodo.3355937.
- Deposited SHG archive MD5 verified: `c290655d3dc73899d9db772f2cfbbce1`.
- Locked config SHA-256: `abc971daf86984e6a893d943cb387d03c97b1b994ad20fd600d3641933917b4c`.
- Development: Mouse20--Mouse23, 3,456 eligible sampled tiles.
- Internal evaluation held closed after development failure: Mouse24--Mouse27, 3,264 eligible sampled tiles.
- Annotation semantics were taken from the source repository: green = locally similar orientation, red = dissimilar orientation, blue = not of interest.

## Why the gate failed

The development sample contained 162 majority-green, 248 majority-red and 3,046 majority-blue tiles. At nominal 70% coverage, silent-invalid risk was 0.953. Even the most selective 10% of tiles had risk 0.934. The internal contract score did discriminate green from non-green tiles above chance (development ROC AUC 0.718), but nowhere near the level required for safe automatic support declaration.

Coherence alone was similarly inadequate (development ROC AUC 0.730) and transferred poorly across mice (locked-set descriptive AUC 0.536). These AUC values are descriptive failure diagnostics, not promoted inferential results.

## Consequence for NOSTOS

The orientation estimator and its validity contract must be distinct. The next architecture must include an explicit support/ROI contract that can abstain when the requested biological structure is absent or mixed. That support contract must itself be validated independently; an optional user or imported mask may define the measurement domain, but it must not be represented as autonomous detection.

The paper may state that the attempted perturbation-only validity contract was prospectively falsified. It may not state that NOSTOS automatically identifies valid local collagen orientation in unsegmented bone SHG.

