# Frozen protocol: scale-declared local orientation on the external SHG test split

## Status and rationale

This endpoint was defined after the adaptive local selector failed on the archive training split. The official 199-patch test split was previously opened for global FFT orientation, but local centerline-tangent outcomes have not been calculated. The experiment is therefore endpoint-new external-test evidence, not pristine dataset-level confirmation.

## Measurement

Use every paired image and manual centerline label in `final_train_test/test` from Zenodo DOI 10.5281/zenodo.7243211. Resize both from 256 × 256 to 128 × 128 pixels. Construct eligible reference tangents exactly as protocol `nostos-local-orientation/1.0`: one-pixel thinning, 5-pixel centerline neighborhood, at least five centerline coordinates, six-pixel edge exclusion and reference anisotropy at least 0.70.

The primary NOSTOS measurement is the local structure-tensor fiber axis at the development-selected declared scale sigma 2 pixels. No adaptive scale selection or confidence-based rejection is used. Sigma 4 is the prespecified scale comparator. A finite-difference gradient axis after sigma-2 Gaussian smoothing is the conventional local comparator. All estimators are evaluated at identical eligible centerline coordinates.

## Inference

Source groups are defined by dropping the final underscore-delimited tile field from the supplied identifier. Report eligible pixels/groups, pooled median and 75th-percentile axial errors, median source-group median error, axial alignment `mean(cos(2*error))`, and 10,000-draw source-group bootstrap intervals (seed 7243214) for pooled median error. Report the same summaries for both comparators. Bootstrap draws resample source groups and retain every eligible pixel from each selected group.

## Frozen gates

All gates must pass:

- at least 100 eligible source groups and 15,000 eligible reference pixels;
- pooled median axial error at most 10 degrees;
- source-group bootstrap upper 95% bound for median error at most 12 degrees;
- median source-group median error at most 12 degrees;
- 75th-percentile axial error at most 20 degrees;
- axial alignment at least 0.75;
- primary median error no worse than sigma 4 by more than 1 degree;
- primary median error no worse than the smoothed-gradient comparator by more than 1 degree.

This validates a scale-declared local orientation field against manual-centerline geometry in one external archive. It does not validate local wavelength, physical calibration, biological mechanism, reliability under a new acquisition or clinical use. Failure remains in the evidence ledger.

