# NOSTOS-0 operator guide: unstained PSHG research workflow

## Intended use

This pathway measures a local axial structure-orientation field from an
unstained, polarization-resolved forward second-harmonic-generation acquisition.
It is research software. It does not output a diagnosis, tissue margin,
mechanical property, treatment recommendation or surgical decision.

The only confirmed acquisition profile is the exact public PSHG-TISS breast
workflow used by the frozen confirmation: ten FSHG frames at polarization
angles 0, 20, ..., 180 degrees, plus matching `R2.tif` and `SNR.tif` support
maps. Hash identity can confirm an archived public field. Matching filenames
and dimensions cannot validate a new microscope.

## Required input folder

One acquisition folder must contain exactly:

- ten TIFF images named `*_FSHG_p0.tif` through `*_FSHG_p180.tif` in 20-degree
  increments;
- one shape-matched `R2.tif`;
- one shape-matched `SNR.tif`;
- optionally, `FI.tif` for evaluation only.

`FI.tif` is never required for deployment and is omitted unless a validation
run explicitly requests reference evaluation. Non-finite R2/SNR background is
treated as unsupported acquisition area and is not interpolated.

## Command-line operation

From the repository root:

```powershell
nostos intraop-pshg <ACQUISITION_FOLDER> `
  --pixel-size-um 1.0 `
  --output outputs\operator-case
```

For the exact hash-locked public bundle, the result can report
`verified_public_bundle` and `confirmed`. A new format-compatible acquisition
reports `unverified_new_acquisition`, changes the measurement evidence to
`unvalidated_new_acquisition`, and is placed in `review` rather than being
silently promoted.

Do not use `--include-reference-evaluation` during routine measurement. That
option exists only for method evaluation when the reference map is available.

## Local workstation

Start the application with:

```powershell
.\launch_nostos.ps1
```

or:

```powershell
nostos serve
```

The workstation listens on `http://127.0.0.1:8765`. Select the acquisition
folder, confirm pixel spacing, and run the measurement. The result viewer
provides four views: source, axial orientation, coherence and accepted support.
Export JSON to preserve evidence status, validity reasons, input hashes,
runtime, measurement summaries and the clinical-withholding statement.

The server is intended for local research use. It is not hardened for an
untrusted network, a hospital information system or patient-identifiable data.

## Result states

| State | Meaning | Permitted interpretation |
| --- | --- | --- |
| `valid` + `confirmed` | Exact locked input contract and a supported measurement | The local axial orientation estimator is operating inside the confirmed public profile |
| `review` + `unvalidated_new_acquisition` | Input format is usable but acquisition provenance is not bridged | Research visualization and method-development only |
| `abstain` | Acquisition or measurement preconditions fail | No measurement interpretation |
| clinical output `withheld` | No prospective clinical endpoint is registered | Always required in NOSTOS-0 |

An image that looks plausible is not enough to override `review` or `abstain`.

## Output contract

The operator directory contains:

- `intraop_result.json`, the authoritative receipt;
- `orientation_degrees.npy`, a float32 axial direction field;
- `coherence.npy`, a float32 local coherence field;
- `eligible.npy`, the accepted-support mask;
- `source.png`, `orientation.png`, `coherence.png` and `support.png`.

Every artifact has a unique key, relative path, byte count and SHA-256 digest.
The receipt contains no development-machine absolute path. Axial direction is
periodic over 180 degrees; a serialized value of 180 degrees is equivalent to
0 degrees and can occur through float32 rounding.

## Verified performance boundary

The public PSHG scientific confirmation used 48 regions and 1,367,747 eligible
pixels. After a transform calibrated on a separate skin subset, the untouched
breast confirmation had median axial error 7.59 degrees and axial alignment
0.877. The production v1.4 confirmation used four additional hash-selected
fields: pooled median error 7.53 degrees, worst field median error 8.09 degrees,
and p95 compute-plus-export time 0.452 seconds. The operator export and local
HTTP workstation have separate passing integrity audits.

These timings exclude acquisition, polarization switching, specimen placement,
focus, data transfer, instrument warm-up and operator interaction.

## T7 runtime

The supported T7 environment is `<DATA_ROOT>\.venv313`. It uses Python 3.13 and
CUDA-enabled PyTorch on the NVIDIA GeForce RTX 5070 Ti. `storage.json` and all
three PowerShell launchers select this environment. The older
`<DATA_ROOT>\.venv` Python 3.14 environment is retained for provenance but is
incompatible and must not be used.

The core orientation production path is CPU-fast; GPU is available in parallel
for optional workloads and does not change the verified estimator.

## New-instrument bridge required before intraoperative research

Before treating a new microscope as supported, freeze and execute a separate
bridge protocol with independent specimens and operators. At minimum it must:

1. verify angle ordering, pixel spacing, field orientation and instrument-to-
   raster coordinate transform;
2. characterize polarization switching and complete acquisition latency;
3. test focus, signal, saturation, motion, blur, resampling and partial-field
   failure modes without changing thresholds after outcome review;
4. compare accepted orientation fields with an adjudicated, acquisition-
   appropriate reference and report clustered uncertainty at the specimen
   level;
5. measure silent-invalid risk and risk-coverage against ordinary acquisition
   QC at matched coverage;
6. repeat the workflow with independent operators and repositioning;
7. document sterile-field compatibility, specimen handling, cleaning,
   cybersecurity, audit logging and failure recovery;
8. retain every failure and abstention, then lock the acquisition profile before
   any prospective clinical endpoint is evaluated.

## Clinical gate

Technical orientation accuracy does not establish clinical usefulness. A
clinical claim requires a separately governed prospective study that links a
locked label-free endpoint to an adjudicated diagnosis, mechanical measurement,
surgical boundary or decision. Workflow, safety, decision impact and patient
outcomes must then be evaluated with appropriate reporting and regulatory
review. Public-data experiments cannot close this gate.
