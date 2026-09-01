# NOSTOS-0 dense-deformation validation protocol

**Frozen:** 27 August 2026, before outcome generation  
**Endpoint:** calibrated 2-D frame-to-frame deformation fields, not object tracks or native biological motion

## Method contract

For each adjacent image pair, NOSTOS estimates a dense displacement field with pinned scikit-image 0.25.2 TV-L1 optical flow. Displacements are expressed in the specimen's physical units. Reliability is estimated without labels from forward-backward inconsistency after bilinear sampling of the reverse field. Pixels outside the valid warp support, with insufficient local gradient energy, or with inconsistency above the declared limit are ineligible. The response geometry stores displacement components, magnitude, uncertainty and eligibility on explicit time, y and x axes. The implementation must abstain rather than emit a field when fewer than 20% of pixels are eligible.

This endpoint does not claim invention of optical flow, superiority to every registration method, object correspondence, cell motion, material strain or clinical validity. NOSTOS contributes calibration, uncertainty, eligibility, abstention and provenance around the estimator.

## Analytic validation set

Generate 36 deterministic 128 × 128 texture phantoms from seeds 2400–2435. Each combines band-limited random texture, Gaussian objects and line structures. Apply one of six known fields: translation, affine shear, radial expansion, sinusoidal horizontal deformation, sinusoidal vertical deformation or a smooth mixed field. Maximum programmed displacement is 6 pixels. Add independently seeded Gaussian noise with standard deviation 1% of robust range. No biological images enter development.

The comparator is scikit-image 0.25.2 iterative Lucas–Kanade with radius 7, ten warps, Gaussian integration and prefiltering. Both methods receive identical normalized frames. Errors are evaluated only on a 10-pixel interior and where the ground-truth source coordinate remains inside the image.

## Frozen analytic gates

1. NOSTOS median endpoint error ≤1.00 pixel.
2. NOSTOS 95th-percentile endpoint error ≤2.50 pixels.
3. Median eligible fraction ≥0.70 and no construct family below 0.50.
4. Spearman correlation between forward-backward uncertainty and endpoint error ≥0.35.
5. NOSTOS median endpoint error ≤1.25 times the comparator error.
6. Multiplying pixel spacing by four multiplies reported physical displacement and uncertainty by four to numerical tolerance.
7. A constant pair and a pair with fewer than 20% eligible pixels abstain with a declared reason.

## Untouched public-content confirmation

After all implementation choices and thresholds are fixed on analytic data, use the checksum-locked BBBC035 volume already registered in `docs/NOSTOS0_BBBC035_DYNAMIC_CONFIRMATION_PROTOCOL.md`. Select eight z planes by evenly spaced rank without inspecting results. Create one previously unseen smooth mixed deformation per plane from fixed seeds 9100–9107, maximum displacement 4 pixels, plus 1% noise. This is microscopy-content confirmation under known programmed deformation, not native biological-motion validation.

The confirmation comparator and metrics are identical to the analytic protocol. No threshold may be changed after outcomes are opened.

## Frozen public-content gates

1. All eight cases execute and preserve their source checksums and programmed-field seeds.
2. NOSTOS median endpoint error ≤1.25 pixels.
3. NOSTOS 95th-percentile endpoint error ≤3.00 pixels.
4. Median eligible fraction ≥0.60.
5. Uncertainty–error Spearman correlation ≥0.30.
6. NOSTOS median endpoint error ≤1.25 times the comparator error.
7. All output components, uncertainty and coordinates are finite and physically calibrated.

## Interpretation rule

A pass supports calibrated dense deformation on analytic truth and public microscopy content under controlled warps. It does not support tracking, native cellular dynamics, tissue mechanics, strain, relaxation or intraoperative motion. Every failed gate remains in the evidence bundle.

## Frozen post-failure uncertainty confirmation addendum

The initial analytic run passed six of seven gates but forward–backward inconsistency correlated only 0.202 with endpoint error. On those opened seeds only, five label-free scores were compared. TV-L1 versus iterative Lucas–Kanade disagreement ranked highest (Spearman 0.259) but still did not meet the original ranking gate. The uncertainty claim is therefore redesigned from error ranking to a calibrated upper bound. A fixed additive split-conformal offset of 0.3076263275 pixels, the higher 95th percentile of development error minus estimator disagreement, is now frozen.

Confirmation uses previously unopened analytic seeds 3000–3035 and the eight BBBC035 planes specified above. The final uncertainty at each pixel is `TV-L1–iLK disagreement + 0.3076263275 pixels`; it is multiplied by physical spacing for isotropic acquisitions. No recalibration is permitted.

The disjoint analytic confirmation must pass: median endpoint error ≤1.00 pixel; median casewise 95th-percentile error ≤2.50 pixels; uncertainty coverage ≥0.90; median uncertainty bound ≤1.50 pixels; median eligible fraction ≥0.70 with every family ≥0.50; NOSTOS error ≤1.25 times iLK error; physical calibration and both abstentions pass. The public-content confirmation must pass the seven gates above with the ranking gate replaced by uncertainty coverage ≥0.90 and median uncertainty bound ≤1.75 pixels. The original failed ranking receipt remains part of the release.
