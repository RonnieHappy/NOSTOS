# NOSTOS-0 small-pilot score repair, version 5

The balanced version-4 pilot showed that the generic cross-scale term was not a validity measurement. In ER tensor coherence, the full maximum score had AURC 0.571, whereas the identical score without cross-scale variation had AURC 0.061. Scale-dependent response is part of the NOSTOS estimand; penalizing it can reject real multiscale structure.

Version 5 therefore defines the decision score as the maximum of acquisition QC, physical sampling, perturbation stability and measurement identifiability. Cross-scale variation remains in every row as a visible diagnostic and as an exploratory ablation, but it cannot determine validity.

The pilot also establishes a provisional acquisition profile. Hessian winning-scale scalars are disabled because the reference peaks were censored at the scale-grid boundary. Spectral power-median wavelength is disabled because 85 of 86 eligible pairs failed the frozen relative-error tolerance. Curves are retained. These endpoint decisions are acquisition-profile-specific, not claims that the algorithms are universally invalid.

This is a developmental choice made before threshold-calibration or confirmation access. The next untouched partition must test the score and profile without further endpoint editing.
