# NOSTOS-0 osteochondral-interface confirmation protocol

Protocol version: `nostos-osteochondral-interface-confirmation/1.0`

Frozen: 26 August 2026, after inspecting only the public paper, repository, archive filenames and the `sample_id` column of `grades.csv`; before extracting, viewing or measuring any image or mask.

## Question and claim boundary

Can a CPU-only, training-free boundary adapter localize the calcified-cartilage interface in calibrated PTA-enhanced human osteochondral micro-CT, and can NOSTOS preserve declared measurements when a predicted rather than reference interface defines the measurement band? This validates one modality-specific ROI adapter and downstream measurement validity. It does not validate the cartilage proposal used in the public Safranin-O cohort, diagnose osteoarthritis, establish clinical use or make segmentation part of the sample-agnostic response geometry.

## Public data and locked split

The source is the 35-sample PTA micro-CT dataset released with Tiulpin *et al.*, *Deep-Learning for Tidemark Segmentation in Human Osteochondral Tissues Imaged with Micro-computed Tomography* (arXiv:1907.05089; `MIPT-Oulu/mCTSegmentation`, repository commit `aadc0dae99d06c58abb57062b5c97cecbd628527`). Images and registered hard-tissue masks have isotropic 3.2-µm voxels. The downloaded archive size and SHA-256 are recorded after transfer without opening image content.

Patient identity is the prefix before the first underscore in `sample_id`. Patients were ordered by SHA-256 of that prefix. The first nine patients are development only: `O18, 29, 13, 23, 28, 26, 30, 27, O19`. The remaining ten are untouched confirmation: `21, 22, 14, 25, 24, O17, 32, 15, 31, 20`. All samples from a patient remain in one partition. Histopathological grade is not used for selection, fitting or evaluation.

## Locked sampling and references

Both orthogonal slice families (`ZX` and `ZY`) are evaluated. In each available family, indices 16, 48, 80, ..., 432 are selected when present. A reference interface is the first hard-tissue pixel along depth in each column after removing columns without a contiguous reference region. Slices with fewer than 128 valid reference columns are ineligible. The sample and patient are the clustering units; slices are never treated as independent biological replicates.

## Development-only estimator selection

Images are robustly normalized between their first and 99th percentiles. The adapter scores candidate depth locations from 20% through 90% of image height using the absolute vertical derivative of a Gaussian-smoothed image plus a signed 12-pixel above-versus-below intensity contrast. A first-order dynamic program returns one continuous interface while penalizing adjacent-column jumps. Only the following grid may be searched on development patients: Gaussian sigma `{1, 2, 4}` pixels, contrast weight `{0, 0.25, 0.5}`, jump penalty `{0.1, 0.5, 1.0}` and contrast sign `{−1, +1}`. The candidate minimizing the mean of patient-level median absolute boundary error is selected; ties within 0.1 µm use, in order, lower sigma, lower contrast weight and lower jump penalty. A global intensity-threshold/largest-lower-component method is the fixed classical comparator.

Confidence is the median selected boundary score divided by the median absolute deviation of all candidate scores, penalized by interface roughness. A single acceptance threshold may be chosen on development data to maximize coverage subject to a patient-bootstrap upper 95% limit of 75 µm for median absolute boundary error and at least 70% slice coverage. If no threshold satisfies both conditions, the adapter is frozen without selective acceptance. No estimator, parameter, confidence rule or gate may change after the development receipt and source hash are written.

## Confirmation endpoints

The primary endpoint is the median absolute vertical interface error in micrometres, aggregated first within sample and then within patient. Secondary endpoints are the 90th-percentile absolute error, fractions within 15, 30 and 60 µm, full-mask Dice, and IoU inside a ±75-µm reference band. A 10,000-draw patient-cluster bootstrap (seed 8,262,602) supplies 95% intervals. The comparator difference is paired within patient.

Downstream validity is assessed in the 100-µm non-calcified band immediately above either the reference or predicted interface. Six frozen sample-level measurements are compared: normalized mean intensity, normalized intensity standard deviation, angular spectral entropy, structure-tensor coherency at 12.8 µm, structure-tensor coherency at 25.6 µm and directional-variogram anisotropy at 25.6 µm. Agreement is reported with concordance correlation, Spearman correlation and standardized absolute error. These are measurement-agreement endpoints, not OA phenotype endpoints.

## Confirmation success gates

All ten gates must pass:

1. all ten locked confirmation patients are represented and at least 18 samples are eligible;
2. at least 400 locked confirmation slices are eligible;
3. selective coverage is at least 80%, or 100% if no development threshold was admissible;
4. patient-aggregated median absolute boundary error is no greater than 30 µm;
5. the patient-bootstrap upper 95% limit for that median is no greater than 45 µm;
6. the patient-aggregated 90th-percentile error is no greater than 75 µm;
7. at least 70% of evaluated boundary columns fall within 30 µm;
8. median IoU within the ±75-µm band is at least 0.80;
9. the adapter is not worse than the classical comparator: the upper 95% limit for paired patient-level median-error difference is no greater than 3.2 µm, and the point estimate is no greater than zero;
10. at least four of six downstream measurements have concordance correlation at least 0.85, and the median standardized absolute error across all six is no greater than 0.20.

Failure of any gate is retained as the formal result. Any post-confirmation redesign is labelled development and requires a new untouched acquisition for confirmation.
