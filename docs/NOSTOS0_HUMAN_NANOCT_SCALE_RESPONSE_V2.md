# Human nanoCT scale-response development amendment

V1 demonstrated that a single raw-gradient orientation can remain self-consistent after blur or resampling while disagreeing with its clean reference. The scalar endpoint is retired without threshold retuning.

V2 preserves the directional response at Gaussian physical scales 0.20, 0.40, and 0.80 micrometres. Support is decided per scale. A requested scale must span at least four public voxels (0.40 micrometres), pass image support, and agree with its adjacent scale within 15 degrees and 25% relative anisotropy. Axis-permutation and monotone-intensity equivariance remain required. Withheld invalidity remains a clean-reference axis error above 15 degrees or anisotropy error above 25% at the same scale.

All v1 transformations and crops remain unchanged. The human dataset has already been inspected, so v2 is development evidence only. Success requires at least 80% coverage and lower silent-invalid risk than always emit at a supported scale. A subsequent dataset is required for confirmation.

