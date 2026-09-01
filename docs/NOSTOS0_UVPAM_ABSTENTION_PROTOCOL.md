# NOSTOS-0 UV-PAM calibration and semantic-abstention protocol

Status: frozen after archive inventory and PNG metadata inspection, before feature extraction.

The archive contains 70,418 UV-PAM `trainA` PNG tiles, 89,743 stained-domain `trainB` PNG tiles, and six apparent UV-PAM filename-prefix groups. The 286 x 286 RGB PNG files inspected contain no physical pixel-size metadata. Filename groups are treated as source groups, not asserted to be independent patients.

NOSTOS is asked for a physical characteristic scale and collagen-orientation interpretation. The complete contract must abstain because calibration is absent and the requested collagen semantics are not established for UV-PAM nuclear-absorption imagery. Always-emit and image-QC-only comparators use a nominal one-unit pixel spacing and are adjudicated silently invalid for the requested physical endpoint.

For auditability, NOSTOS may additionally emit dimensionless/pixel-domain angular entropy, anisotropy, and characteristic wavelength with explicit `pixels` units. These descriptors are not cross-modality physical measurements and carry no tissue-specific biological interpretation.

Twenty-four evenly spaced UV-PAM tiles are sampled from each of the six filename-prefix groups. Inference is descriptive at source-group level only.

