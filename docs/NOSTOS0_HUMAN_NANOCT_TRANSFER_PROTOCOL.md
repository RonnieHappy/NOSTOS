# NOSTOS-0 human-bone nanoCT transfer protocol

Status: frozen after archive integrity, dimensions, and source-method inspection, before response measurements.

## Data and calibration

Six deposited human-bone synchrotron nanoCT volumes are stored as 1024 x 1024 x 1024 little-endian uint16 arrays. The source study acquired nanoCT at 50 nm isotropic voxels; the repository states that public gray-value volumes were binned by two. NOSTOS therefore uses 0.10 micrometre isotropic spacing. This inference and its source are recorded in provenance.

The deposited lacuna/canaliculi and remodeling-region masks are two-dimensional minimum-intensity-projection masks. They will not be used as 3D voxel truth.

## Frozen experiment

Eight deterministic 96-cubed central subvolumes are sampled per deposited volume. The estimator is a physical-gradient 3D structure tensor returning its normalized eigenvalue spectrum, axial principal structural direction, and anisotropy.

Each clean cube is transformed by monotone contrast, mild blur, severe blur, half-resolution resampling/restoration, and additive noise. Internal contract probes are a separate mild gamma change, 0.5-voxel blur, and axis permutation. Withheld invalidity compares each transformed case with its clean reference and is defined as principal-axis drift above 15 degrees or anisotropy relative error above 25%.

Conditions use the identical estimator: always emit, endpoint QC, partial contracts, and the full validity contract. All reporting remains at deposited-volume level; cubes and transformations are repeated technical cases.

## Claim boundary

This is an acquisition-family transfer and perturbation benchmark for calibrated 3D directional response. Six deposited volumes do not establish population biology, diagnosis, mechanics, or clinical utility.

