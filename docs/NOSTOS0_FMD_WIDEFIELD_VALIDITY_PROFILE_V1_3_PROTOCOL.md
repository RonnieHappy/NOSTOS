# NOSTOS-0 FMD widefield validity-profile protocol v1.3

## Why this experiment exists

The v1.2 mixed-modality confirmation passed every pooled primary gate, but the mandatory stratified audit found a clear acquisition boundary. Accepted confocal and two-photon coherence measurements had zero invalid cases, whereas accepted widefield measurements had 20 invalid cases among 48 emissions. The pooled result is retained, but it is not sufficient evidence for widefield use.

Version 1.3 tests the appropriate repair: validity profiles are calibrated for an acquisition stratum, and a stratum with fewer than two independent development fields is unsupported. Tissue identity remains outside the risk model.

## Newly selected public fields

The official `WideField_BPAE_R.tar` archive is 709,232,640 bytes, MD5 `e02b07bc4cfcd19dc911bd9d0c4e65a0`, and SHA-256 `4914cd7d951b4ddc1a01f6c7f121b7e9936fd2a7d1505f3e802984ffee69cad7`.

FOV 19 is excluded because it supplied the previously analyzed mixed test set. A hash rule selected eight of the other 19 fields before any image was decoded. FOVs 7, 15, 13 and 9 are development. FOVs 16, 17, 18 and 11 are untouched confirmation. Each field contributes four hash-selected realization indices at raw, 2-, 4-, 8- and 16-capture levels. The field of view is always the independent unit.

## Frozen analysis

The endpoint estimator, mild perturbations, pixel-relative scales, reference eligibility, error tolerances, acquisition-QC comparator, score formula and leave-one-component-out ablations are unchanged from v1.2. Development uses two grouped folds. The profile needs at least two independent development fields in the declared `WideField` acquisition stratum.

The development operating point must cover at least 20% of coherence cases, have observed risk at most 10%, and have clustered 95% upper risk at most 30%. If no threshold passes, confirmation remains unopened.

Confirmation is a one-shot test on four unseen fields. It retains pass, fail or non-assessable status. Primary inference uses field-clustered bootstrap resampling. No threshold, score component, tolerance, field, realization, or gate may change after confirmation decoding.
