# NOSTOS-0 osteochondral reference-definition audit

Protocol version: `nostos-osteochondral-reference-audit/1.0`

Status: frozen post-test audit. This protocol was written after visual inspection of the failed v2 boundary-adapter benchmark and before calculating the results defined below. It is not an untouched confirmation experiment.

## Why this audit is required

The public mCTSegmentation dataset does not contain manually traced interface curves. Its masks were produced by rigidly registering CA4+-enhanced volumes to PTA volumes and thresholding the CA4+ volume to obtain mineralized-tissue masks. The source paper describes these as masks of the underlying mineralized tissues. The released evaluation code derives a surface by reversing the volume axis and taking an `argmax`, rather than taking the first foreground pixel from the top of each exported 2-D mask.

The first NOSTOS learned-adapter benchmark instead defined the reference as the first vertically contiguous foreground run from the top of each 2-D mask. Visual diagnostics subsequently showed that many masks contain disconnected foreground regions. In those images, a small detached component can determine the purported reference interface even when the prediction follows the dominant tissue body. The original boundary-error result is therefore a metric-definition result, not a validated biological interface error.

Primary provenance:

- Tiulpin et al., *Deep-Learning for Tidemark Segmentation in Human Osteochondral Tissues Imaged with Micro-computed Tomography*, arXiv:1907.05089.
- Released source repository `MIPT-Oulu/mCTSegmentation`, commit `aadc0dae99d06c58abb57062b5c97cecbd628527`.
- Source evaluation function: `code/evaluate_metrics.py::make_surf_vol`.

## Frozen data and predictions

- Dataset: the same 35 samples from 19 patients and the same 1,960 deterministically selected ZX/ZY slices used in learned-adapter v1.1 and boundary-adapter v2.0.
- Spacing after the frozen two-fold in-plane reduction: 6.4 micrometres per pixel.
- Predictions: the already-trained five-fold out-of-fold checkpoints. No retraining, threshold selection, post-processing change, or patient reassignment is permitted.
- Models: both v1.1 (BCE plus soft Dice) and v2.0 (boundary-aware development objective).

## Frozen reference policies

Each policy requires a vertical run of at least three foreground pixels.

1. `top_any`: first valid foreground run from the top of the complete mask. This reproduces the original NOSTOS analysis.
2. `bottom_any`: first valid foreground run after vertically reversing the complete mask, transformed back to image coordinates. This is the 2-D analogue of the public source code's reversed-axis surface convention.
3. `top_largest`: `top_any` after retaining only the largest 8-connected reference component.
4. `bottom_largest`: `bottom_any` after retaining only the largest 8-connected reference component.

The component-filtered policies are sensitivity analyses, not asserted biological ground truth. They match the prediction post-processing rule and test whether detached reference components dominate the result.

## Outputs

For each model and policy, report:

- slice coverage;
- patient-median absolute boundary error and patient-bootstrap 95% interval;
- patient-median 90th-percentile error;
- patient-median fraction within 30 micrometres;
- patient-median 75-micrometre band IoU;
- paired patient-level differences relative to `top_any`;
- the number of patients whose median error changes by at least 30 micrometres;
- reference-policy disagreement in micrometres;
- component count and largest-component fraction for every reference mask.

Bootstrap intervals use 10,000 patient-level resamples and seed 8,262,603. Aggregation is slice to sample by median, then sample to patient by median.

## Interpretation rule

This audit cannot promote either adapter to clinical validation. If boundary performance or model ranking changes materially across plausible reference policies, the public masks are inadequate for a definitive single-interface accuracy claim. The result must then be reported as reference-definition sensitivity, and a manually adjudicated continuous-interface test set is required.

A material change is prospectively defined as any of:

- at least 25% relative change in patient-median boundary error;
- at least 30 micrometres absolute change for five or more patients;
- reversal of the v1.1 versus v2.0 model ranking;
- change in any prespecified v1.1/v2.0 quality gate.

No policy will be selected post hoc as the preferred reference merely because it yields lower error.
