# Architecture decision: raw response geometry and comparison geometry are distinct

The frozen v2 distribution-shift benchmark failed. Full raw response curves achieved
balanced accuracy 0.721 (95% interval 0.679–0.763), below matched collapsed summaries
(0.883) and PyRadiomics (0.883). Removing the tensor module increased accuracy to
0.933. This result is retained and rules out the original claim that direct curve
concatenation is itself a robust common representation.

The failure has a specific geometric cause. Absolute axial directions are valid
measurements, but they are nuisance coordinates when two specimens are compared up to
global image rotation. Horizontal and vertical variograms have the same problem. A
standard linear classifier cannot infer this quotient reliably under an unseen rotation
distribution.

NOSTOS therefore separates two objects:

1. **Raw response geometry**, which retains absolute physical scale, specimen-relative
   direction, amplitude, uncertainty and validity.
2. **Canonical comparison geometry**, which may quotient a declared nuisance group.
   For global axial rotation it removes the absolute Fourier angle, expresses tensor
   directions relative to their weighted axial mean, and replaces horizontal/vertical
   variograms with their mean and unsigned anisotropy magnitude.

This does not retroactively repair benchmark v2. The v2 test set is now development
information. The canonicalization must be developed without further selection on that
test set, frozen, and assessed on a newly generated protocol with different perturbation
families and seeds. Raw and canonical outputs must always be exported together so the
nuisance declaration remains auditable.
