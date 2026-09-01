# NOSTOS-0 PSHG breast local-orientation confirmation protocol

Protocol version: `nostos-pshg-breast-orientation/1.0`

Frozen: 26 August 2026, before download or inspection of any unstained-breast PSHG image or outcome.

## Rationale and locked coordinate calibration

The frozen unstained-skin experiment (`nostos-pshg-external-orientation/1.0`) failed with a median axial error of 82.25° and axial alignment -0.874 across 1,263,724 pixels. Inspection of the depositors' published `SMART_FFT1.m` code established that `FI` is a polarization-phase angle in the microscope coordinate system; the archive supplies no transform from that laboratory polarization zero to the raster x-axis. Skin is therefore retained as a failed development/calibration cohort. A single 90° axial offset, chosen from that development result and fixed here, maps archived FI into the raster coordinate system. No other estimator, eligibility rule or threshold changes.

## Untouched confirmation cohort

The confirmation cohort is every available unstained breast ROI and forward-SHG stack in PSHG-TISS (`OSF.IO/UDTQP`). These files had not been downloaded, viewed or measured when this protocol was frozen. An ROI is the inferential group. Filename and archive structure are the only selection variables.

## Frozen inputs, estimator and reference

The NOSTOS input is the arithmetic mean of all ten 512 × 512 FSHG frames. The reference is `(FI + 90°) mod 180°`. Eligibility requires finite FI, `R2 >= 0.90`, `SNR >= 3 dB`, positive mean FSHG intensity and an eight-pixel edge exclusion. The primary estimator is the unchanged sigma-2-pixel NOSTOS local structure tensor; sigma 4 and a sigma-2 smoothed-gradient line direction are comparators. FI, R2 and SNR do not enter the estimator.

## Statistics and success gates

The primary endpoint is pooled-pixel median axial error. A 10,000-draw whole-ROI bootstrap (seed 7,242,323) provides the 95% interval. All nine gates must pass:

1. at least 30 eligible ROIs;
2. at least 50,000 eligible pixels;
3. median error no greater than 15°;
4. ROI-bootstrap upper 95% limit no greater than 15°;
5. 75th-percentile error no greater than 30°;
6. median ROI-level median error no greater than 15°;
7. axial alignment at least 0.65;
8. median error no worse than sigma 4 by more than 2°;
9. median error no worse than the smoothed-gradient comparator by more than 2°.

Any failed gate is retained. A pass confirms transfer of one calibrated local orientation field to an untouched tissue cohort acquired on the same PSHG platform. It does not establish an instrument-independent coordinate transform, molecular orientation, mechanism, diagnosis or clinical use.
