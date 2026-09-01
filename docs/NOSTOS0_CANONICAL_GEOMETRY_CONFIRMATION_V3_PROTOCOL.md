# NOSTOS-0 canonical comparison-geometry confirmation v3

**Frozen before dataset generation:** 26 August 2026  
**Canonical implementation:** `nostos.features.canonical_geometry` as committed before generation

## Confirmatory question

Does a declared quotient of global axial rotation correct the failure of raw response
concatenation under a new acquisition-shift distribution, without sacrificing performance
relative to established representations?

Benchmark v2 is development evidence and is not reused. The v3 generator uses new seeds,
more cases and different compound perturbation families.

## Frozen dataset

The six registered construct classes are orientation, spectral scale, blob, roughness,
network and spatial heterogeneity. Each has 50 training and 50 test cases (600 total) at
104 × 104 pixels. Master randomness uses NumPy `PCG64` seed 308260. Physical construct
parameters vary within the v2 registered ranges but are redrawn from disjoint seeds.

Training images receive mild translation, gamma, illumination-gradient and shot-noise
changes. Test images receive compound unseen magnitudes of global rotation, anisotropic
blur, anisotropic resampling, translation, gamma, illumination gradient and shot noise.
Each final image is standardized by its own mean and standard deviation and clipped to
[−5, 5]. No representation receives a mask.

## Frozen representations and model

1. Raw NOSTOS response concatenation.
2. Canonical rotation-quotiented NOSTOS geometry. Raw measurements remain exported;
   only the comparison view removes absolute Fourier direction, makes tensor directions
   relative to their weighted axial mean, and converts the paired variograms to symmetric
   mean and unsigned-anisotropy coordinates.
3. Matched collapsed NOSTOS summaries.
4. Conventional intensity and gradient scalars.
5. Conformance-audited PyRadiomics first-order and texture families.
6. Kymatio scattering with `J=3`, `L=8`, `max_order=2`.

All representations use `StandardScaler` fitted on training data followed by a linear
SVM with `C=1`. There is no feature selection, tuning or test-set fitting.

## Inference and gates

The primary outcome is balanced accuracy on 300 test cases. Stratified case bootstrap
intervals use 10,000 resamples and seed 38260. The confirmation passes only if all gates
pass:

1. Canonical NOSTOS balanced-accuracy lower confidence limit exceeds 0.80.
2. The paired canonical-minus-raw accuracy interval has lower limit greater than zero.
3. Canonical NOSTOS is non-inferior to matched collapsed summaries, PyRadiomics and
   Kymatio at a −0.03 margin for each paired interval.
4. At least two canonical module ablations reduce balanced accuracy by 0.03 or more.
5. Median same-construct canonical distance under the test transformations is at least
   25% lower than raw response distance after training-derived coordinate standardization.

Every prediction, comparator receipt, interval and failed gate is retained. Success would
validate the declared nuisance quotient under analytic acquisition shifts, not biological
meaning, diagnostic performance or clinical utility.
