# Frozen BBBC035 dynamic public-content confirmation protocol

**Protocol:** `nostos-bbbc035-dynamic-confirmation/1.0`  
**Frozen:** 27 August 2026, before downloading or inspecting BBBC035 files  
**Dataset:** BBBC035v1 simulated HL60 fluorescence time lapse, CC BY 3.0

## Endpoint and scope

NOSTOS currently exposes calibrated frame-to-frame bulk translation, not dense optical flow or cell tracking. The confirmation therefore tests that exact endpoint on public microscopy content under independently programmed translations. It does not compare bulk image registration with native individual-cell trajectories.

The lexicographically first time point in the lexicographically first image sequence is maximum-intensity projected along depth. Four integer translations are generated with wrap boundary conditions: `(3,-5)`, `(-7,4)`, `(10,8)` and `(-4,-9)` pixels. Independent Gaussian noise with standard deviation 1% of the projected-image standard deviation is added using seed 35,035. Calibration is declared as 0.1267 µm/pixel from the archive width range and 639–652 pixel dimensions; because the exact selected volume calibration may differ slightly, pixel error is primary and physical displacement is an execution check rather than a biological size claim.

A constant two-frame series is the abstention control. The pinned comparator is scikit-image 0.25.2 `phase_cross_correlation` with upsample factor 1.

## Gates

1. The selected source frame, archive SHA-256 and generated-series hash are recorded.
2. NOSTOS error is at most one pixel for every programmed translation.
3. Median NOSTOS error is no greater than the pinned comparator median plus 0.25 pixel.
4. Every valid displacement is emitted in the declared physical unit and temporal calibration is retained.
5. The constant series abstains.
6. No source case is excluded after outcome computation.

The result is a public-content registration confirmation. Native deformation, optical flow, division-aware tracking and biological motion remain unsupported until separately implemented and validated.
