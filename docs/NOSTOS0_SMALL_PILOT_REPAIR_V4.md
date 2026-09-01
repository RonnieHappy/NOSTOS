# NOSTOS-0 paired-acquisition small-pilot repair, version 4

Version 4 retains the version-3 common physical FFT band, scalar-scale boundary abstention, and complete implementation identity. It replaces single-estimator orientation gating with an explicit consensus contract.

An orientation is identifiable only when all of the following hold:

1. the global doubled-angle tensor resultant is at least 0.15;
2. Fourier anisotropy over the shared physical band is at least 0.15;
3. tensor and Fourier axial orientations agree within 20 degrees; and
4. the orientation is stable under the frozen mild perturbations.

The first two requirements establish directional strength using independent spatial- and frequency-domain estimators. The third prevents a confident but method-specific artifact from being emitted. The 0.15 strength boundary preserves the pre-existing numerical observability threshold; 20 degrees is the pre-existing tensor-Fourier agreement normalization. No tissue label or reference value enters the runtime decision.

The tensor resultant remains in the measurement provenance and support components. It is no longer scored as a separate structural endpoint in this paired-acquisition experiment.

Version 4 is developmental. It will first be tested on one CCP and one ER field, then—only if the semantic checks behave correctly—on the frozen balanced 6+6 pilot. It cannot establish clinical validity, cross-dataset generalization, final thresholds, or submission readiness.
