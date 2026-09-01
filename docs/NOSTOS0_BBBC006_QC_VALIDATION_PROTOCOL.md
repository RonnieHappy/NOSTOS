# Frozen BBBC006 acquisition-QC validation protocol

**Protocol:** `nostos-bbbc006-qc/1.0`  
**Frozen:** 27 August 2026, after spatial-response analysis but before QC endpoint computation  
**Role:** endpoint-new development/validation on an opened dataset

The same 64 hash-selected BBBC006 DAPI triplets are used. NOSTOS normalized Laplacian focus, robust dynamic range, contrast-to-residual ratio and observed endpoint fraction are computed without tissue-specific parameters. z=16 is the microscope's optimal plane, z=15 is expert-classified in focus and z=0 is out of focus.

## Gates

1. All 64 triplets produce finite QC outputs without exclusion.
2. z=16 focus score exceeds z=0 in at least 90% of fields.
3. z=15 focus score exceeds z=0 in at least 90% of fields.
4. Median z=15/z=16 focus-score ratio lies between 0.5 and 2.0.
5. Paired bootstrap 95% intervals for median z=16-minus-z=0 and z=15-minus-z=0 focus score both exclude zero, with 20,000 resamples and seed 6007.
6. Constant-field and high-endpoint-fraction synthetic controls produce their declared abstain and review flags.

A pass validates focus ordering and failure semantics for this public acquisition. It does not create a universal acceptable-focus threshold or determine specimen quality.
