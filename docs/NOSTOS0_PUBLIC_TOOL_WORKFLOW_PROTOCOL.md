# Frozen public-data end-to-end tool workflow protocol

**Protocol:** `nostos-public-tool-workflows/1.0`  
**Frozen:** 27 August 2026

## Workflows

The released Python API is exercised on four distinct contracts without tissue-specific retraining:

1. unmasked 2-D fluorescence: public BBBC007 `A9 p10d.tif`, relative spacing 1;
2. masked 2-D network: official HRF `01_h.jpg` with its expert `01_h.tif` vessel mask, relative spacing 1;
3. masked 3-D volume: public `BMLPL_001_REF_17_SEG_SUB.nii`, spacing read from NIfTI and supplied explicitly in millimetres;
4. 2-D+t registration: maximum projection of BBBC035 `01/t000.tif` followed by a programmed `(3,-5)` translation, 0.1267 µm/pixel and 29 min/frame.

Every workflow writes the public response-geometry JSON, measures wall time, retains source hashes and validates the schema-level contract. Large source data and generated arrays remain on bulk storage.

## Gates

1. All four workflows complete without an exception.
2. Every output has schema `nostos-response-geometry/1.0`, input dimensions, calibration, provenance, status and at least one response or declared abstention.
3. The 2-D unmasked workflow reports spectral, tensor, Hessian and spatial modules and abstains from mask-dependent geometry/network measurements.
4. The 2-D masked workflow reports geometry and the versioned boundary-corrected network response.
5. The 3-D masked workflow reports Hessian, geometry and network modules without fabricating 2-D spectral or spatial responses.
6. The time-series workflow reports calibrated dynamic displacement and the explicit time-axis contract.
7. Every workflow completes in at most 60 s on the author CPU reference environment.

This is end-to-end software execution, not independent usability, biological validation or clinical performance.
