# NOSTOS-0 bone orientation contract: prospective v2 amendment

Status: frozen before opening the SHG image archive. The annotation archive and repository documentation were inspected only to establish label semantics and specimen identifiers.

## Reason for amendment

The compact paired SHG/TPF v1 experiment used the same perturbation disagreement both inside the acceptance rule and as the definition of invalidity. That makes zero residual perturbation failures among accepted cases partly circular. The result is retained as a diagnostic failure because full-contract coverage was 0.358, below the preregistered 0.70 gate. No v1 threshold will be retuned.

## Independent v2 design

The estimator returns an axial orientation and coherence. Contract acceptance may use only:

- dynamic range;
- structure-tensor coherence;
- agreement across two physical-image scales;
- mild internal probes: isotropic blur, monotone gamma change and integer translation.

The following are withheld from acceptance and used only to adjudicate silent invalidity:

- coarse annotation compatibility (green, locally similar orientation; red, dissimilar; blue, not of interest);
- anisotropic downsampling and restoration;
- crop-and-reposition disagreement;
- adjacent-section disagreement where a matched adjacent section exists and remains annotation-compatible.

An emitted orientation is silently invalid if it is emitted in a red/blue majority tile, or if an eligible withheld perturbation produces axial disagreement above 10 degrees. Adjacent-section disagreement is reported separately because biological change through depth can be real.

## Specimen split and threshold rule

- Development mice: Mouse20, Mouse21, Mouse22 and Mouse23.
- Locked internal evaluation mice: Mouse24, Mouse25, Mouse26 and Mouse27.
- Sampling and all bootstrap resampling are clustered by mouse; slices and tiles are never treated as independent biological units.
- The development threshold is the least restrictive observed score threshold whose mouse-cluster upper 95% confidence bound for silent-invalid risk is at most 0.15 and whose coverage is at least 0.70. If no threshold satisfies both, the development gate fails and no threshold is promoted.
- The promoted threshold, if any, is evaluated once on Mouse24--Mouse27 without modification.

## Claims permitted

This dataset can test selective support for a local 2D orientation measurement in label-free bone SHG. It cannot establish exact angular accuracy, disease diagnosis, human transfer, mechanics or clinical utility.

