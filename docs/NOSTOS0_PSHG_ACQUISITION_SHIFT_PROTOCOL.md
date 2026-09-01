# NOSTOS-0 PSHG acquisition-shift validity benchmark

**Protocol:** `nostos-pshg-acquisition-shift/1.0`  
**Frozen:** 30 August 2026, before generating or inspecting any acquisition-shift result  
**Data:** PSHG-TISS unstained breast forward-SHG, DOI `10.17605/OSF.IO/UDTQP`

## Primary question

Can an input-only NOSTOS measurement contract identify unstained-tissue local-orientation maps that become wrong under a controlled acquisition shift, while preserving useful coverage and outperforming ordinary acquisition QC and component-ablated contracts?

This benchmark isolates the support layer. Every policy uses the same sigma-2-pixel structure-tensor estimator. Policies differ only in which input-known diagnostics they use to rank or reject a result. The polarization-derived `FI` map is withheld from every deployment decision and is used only after measurement to adjudicate error.

## Prior access and split

The 48 source ROIs were previously characterized in the pristine PSHG confirmation. The acquisition-shift images, condition-level errors, risk maps and policy comparisons have not been generated. This is therefore a prospectively frozen perturbation challenge on previously characterized source tissue, not an untouched-tissue cohort.

ROI names are ordered by `SHA-256("NOSTOS-PSHG-SHIFT-v1|" + roi_name)`. The first 24 are development ROIs and the remaining 24 are confirmation ROIs. Development may fit monotone risk calibration but may not change the estimator, perturbations, diagnostics, comparator definitions, invalidity rule or success gates. Confirmation cannot be opened until the development profile, configuration, protocol and split have been hash-locked.

## Measurement and reference

For each ROI, the ten deposited forward-SHG frames are averaged after a frozen deterministic perturbation. NOSTOS reports the local axial structure-tensor orientation at sigma 2 pixels. The reference is `(FI + 90 degrees) mod 180 degrees`, as frozen on the separate skin qualification subset before the pristine breast confirmation.

Reference eligibility requires finite `FI`, `R2 >= 0.90`, `SNR >= 3 dB`, positive mean FSHG intensity and an eight-pixel edge exclusion. These maps define where error can be adjudicated. They do not enter the calibrated risk score. A case must contain at least 1,000 adjudicable pixels.

A case is silently invalid when either its median axial error exceeds 15 degrees or its 75th-percentile axial error exceeds 30 degrees. The case, not the pixel, is the selective-risk observation; repeated conditions remain nested within ROI.

## Frozen acquisition shifts

Each ROI is evaluated under 15 conditions:

1. clean;
2. common Gaussian blur, sigma 1 pixel;
3. common Gaussian blur, sigma 2 pixels;
4. common Gaussian blur, sigma 4 pixels;
5. independent frame noise at 20 dB;
6. independent frame noise at 10 dB;
7. independent frame noise at 5 dB;
8. circular inter-frame motion of radius 1 pixel;
9. circular inter-frame motion of radius 2 pixels;
10. circular inter-frame motion of radius 4 pixels;
11. twofold downsampling followed by restoration to the native grid;
12. fourfold downsampling followed by restoration to the native grid;
13. fourfold contrast compression about the frame median;
14. moderate compound shift: sigma-2 blur, 10-dB noise and one-pixel motion;
15. severe compound shift: sigma-4 blur, 5-dB noise, two-pixel motion and twofold resampling.

Noise seeds are derived from the frozen seed, ROI name, condition and frame index. Images are clipped only to the non-negative source-intensity domain. FI, R2 and SNR are never perturbed or supplied to the risk calibrator.

## Input-only diagnostics and policies

The policies use the following diagnostics calculated on the deposited R2/SNR acquisition-support domain:

- ordinary acquisition QC: observed endpoint fraction, contrast-to-residual ratio and normalized focus diagnostics;
- endpoint observability: median sigma-2 tensor coherence;
- scale consistency: median axial disagreement between sigma-2 and sigma-4 orientation;
- split-stack consistency: median axial disagreement between orientations computed from alternating five-frame averages.

Raw component risks are normalized by the frozen constants in `configs/pshg_acquisition_shift_v1.locked.json`; higher values indicate less support. A policy score is the maximum of its included component risks.

Policies are:

- `always_emit`: no selective score;
- `acquisition_qc`: ordinary acquisition diagnostics only;
- `endpoint_qc`: acquisition QC plus coherence;
- `without_scale_consistency`: acquisition QC, coherence and split-stack consistency;
- `without_split_consistency`: acquisition QC, coherence and scale consistency;
- `full_contract`: all four components.

Each scored policy receives its own monotone isotonic risk map fit on development cases with four ROI-grouped folds and six quantile bins. No policy inherits a component that its definition omits. Deployment accepts a case only when its predicted invalidity risk is at most 0.15.

Sigma-4 structure tensor and a sigma-2 smoothed-gradient line direction are fixed upstream estimator comparators. They always report a value and do not receive NOSTOS support components.

## Primary and secondary endpoints

The primary endpoint is silent-invalid risk at the frozen 0.15 predicted-risk cutoff. Secondary endpoints are coverage, area under the tied-score risk-coverage curve, matched-coverage risk, clean-case accuracy, component ablations and upstream-estimator error.

Uncertainty resamples the 24 confirmation ROIs with replacement and retains all 15 nested conditions for a selected ROI. Five thousand frozen bootstrap draws estimate intervals for full-contract risk and paired differences in risk and risk-coverage area.

## Frozen success gates

All gates must pass:

1. exactly 24 confirmation ROIs and 360 eligible condition cases;
2. at least 30 confirmation cases are silently invalid, making selective risk assessable;
3. full-contract coverage is at least 0.50;
4. the ROI-bootstrap upper 95% limit for full-contract risk is at most 0.20;
5. at matched full-contract coverage, full-contract risk is at least 0.05 lower than both acquisition QC and endpoint QC;
6. full-contract risk-coverage area is lower than both acquisition QC and endpoint QC, and both paired ROI-bootstrap lower limits for comparator-minus-full differences exceed zero;
7. removing scale consistency or split-stack consistency worsens risk-coverage area by at least 0.01 for at least one ablation;
8. clean full-contract coverage is at least 0.90 and clean median error is at most 15 degrees;
9. clean sigma-2 error is no more than 2 degrees worse than either upstream comparator;
10. a terminal label-blindness audit proves that changing reference-only errors and invalid labels does not change any deployment decision.

Failure of any gate is the result. No condition, tolerance, policy, component, split or gate may be removed after confirmation access.

## Claim boundary

A pass supports a failure-aware local-orientation measurement under this deposited unstained PSHG acquisition family and the frozen controlled shifts. It does not establish molecular collagen orientation, a universal microscope profile, cartilage or bone transfer, tissue mechanics, diagnosis, margins, treatment guidance, intraoperative acquisition time or clinical utility.
