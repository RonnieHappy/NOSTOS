# NOSTOS-0 FMD strict external-transfer protocol v1.6

## Purpose

This protocol prospectively tests whether the conservative three-cell FMD support profile transfers without refitting across two acquisition changes. The profile was compiled only after the locked v1.5 extension failed. It retains tensor-coherence measurements from average-of-16 acquisitions at requested scales of 4, 8 and 16 pixels and abstains from every other acquisition-by-scale cell.

The experiment changes one axis at a time:

- **Confocal_BPAE_R:** the mitochondrial channel is retained while the acquisition modality changes from widefield to confocal.
- **WideField_BPAE_G:** the widefield modality is retained while the fluorescent structure changes from mitochondria to F-actin.

No threshold, support cell, estimator, perturbation, field, realization, gate or comparator may be changed after the lock is written.

## Failure lineage

The v1.4 four-cell profile appeared to remove an average-of-8 by 8-pixel failure on four confirmation fields. A prospectively locked seven-field v1.5 extension then produced six invalid accepted average-of-8 by 16-pixel tensor-coherence measurements in two fields. The extension status is **fail** and remains part of the evidence record.

All nineteen non-excluded WideField_BPAE_R fields were subsequently opened for post-failure development. The v1.6 compiler retained a cell only when it had accepted observations from all nineteen fields, zero accepted failures, zero fields with any accepted failure and a two-sided exact field-event upper 95% bound no greater than 0.20. Only average-of-16 at 4, 8 and 16 pixels survived. This is development evidence, not confirmation.

## Frozen inputs

| Object | SHA-256 |
| --- | --- |
| Full-archive development configuration | `72b0e82453e318a530c231ac56677b761133b28afc098d3eb08fe66c6c6ce16b` |
| Base validity profile | `9c99e6c01359b8b8ab84f1eb6f48cf9101e913ee90269b63573ffd1abc69b737` |
| Conservative strict profile | `ddac86a5e0ae60d559975f63935e3e1bceb3bfdc41d31ec4ed1eecbdb6c48e1f` |
| Measurement protocol | `62f1e77f5e380abb3943e6014c0d0603747a403c50d06a6e2a18a17fb544045b` |
| Confocal_BPAE_R archive | `9b36bb4df24ae81947d6829b1e7ae33c31eb03430614f0de7a3382034f3f81d2` |
| WideField_BPAE_G archive | `019863658ab0ba45c2b323ef787bad2ed40b017c0cdcfae66eb7818eaf9bdeee` |

Both public archives are from the Fluorescence Microscopy Denoising dataset, DOI 10.7274/r0-ed2r-4052, distributed under CC BY-SA 4.0. FMD does not provide pixel spacing, so only dimensionless tensor-coherence endpoints are eligible and all requested scales remain explicitly pixel-relative.

## Selection

The selection seed is `26083161`. For each dataset key, field identifiers 1–20 are ordered by SHA-256 of `seed|dataset_key|fovN`; the first seven are used. Within each selected field, realization indices 0–49 are ordered by SHA-256 of `seed|dataset_key|fovN|realizationK`; the first four are used at raw, average-of-2, average-of-4, average-of-8 and average-of-16 acquisition levels.

Selected Confocal_BPAE_R fields are 7, 19, 17, 2, 3, 6 and 16. Selected WideField_BPAE_G fields are 1, 11, 5, 16, 3, 15 and 19. Each source contributes 140 paired acquisitions nested within seven fields.

The complete field and realization list is serialized in `configs/fmd_strict_external_transfer_v1_6.locked.json` and is verified against the hash rule at runtime.

## Measurement and invalidity

The input image at each acquisition level is compared with the deposited average-of-50 reference from the same field. The estimator, reference-eligibility rules, perturbation probes and invalidity tolerance are inherited unchanged from the v1.3 measurement protocol. The primary endpoint is tensor coherence. An emitted tensor-coherence measurement is invalid when its absolute deviation from the reference exceeds 0.15.

The profile decision uses only input-side information and the frozen acquisition-by-scale support lattice. Reference measurements determine adjudicability and invalidity but never enter the support decision.

## Gates

Each source must satisfy all inherited confirmation checks, contain exactly seven eligible independent fields, emit zero invalid accepted measurements, have zero fields with an accepted failure, and expose all three supported cells in every field.

The combined audit must contain exactly fourteen eligible independent fields, emit zero invalid accepted measurements, have zero fields with an accepted failure and have a two-sided exact field-failure upper 95% bound no greater than 0.25. The inherited matched ordinary acquisition-QC and risk-coverage gates remain active.

Any failed check makes the external transfer a failed confirmation. Results will not be relabeled by post hoc thresholding. A later repair, if needed, must begin with a new version and a new external archive.

## Provenance and execution order

1. Verify archive byte counts, MD5 and SHA-256 hashes.
2. Run the complete automated test suite.
3. Freeze the protocol, implementation and input identities while transfer and audit output directories are absent.
4. Index all selected archive members and write the pair index before decoding image pixels for measurement.
5. Decode and measure the selected pairs once.
6. Audit the serialized evidence rows independently of the runner summary.
7. Preserve pass or fail status, all failed checks and all output hashes in the manuscript evidence bundle.

The lock records that the files were downloaded and verified before analysis but that selected pixels had not been decoded for measurement analysis.

