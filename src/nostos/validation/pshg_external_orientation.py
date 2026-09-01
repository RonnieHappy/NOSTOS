"""Pristine external local-orientation validation against polarization SHG maps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from scipy import ndimage

from nostos.validation.local_orientation import _axial_errors, _tensor_fields
from nostos.validation.local_orientation_external import _bootstrap_median


PROTOCOL_SHA256 = "a38212778a8e1f978471891a0c1b9d52ec1538bdb34bc8521131406ae6099e1f"


def _case(root: Path, reference_offset_degrees: float = 0.0) -> dict[str, np.ndarray]:
    frames = sorted(root.glob("*_FSHG_p*.tif"), key=lambda path: int(path.stem.rsplit("p", 1)[1]))
    if len(frames) != 10:
        raise ValueError(f"{root.name}: expected 10 FSHG frames, found {len(frames)}")
    image = np.mean([tifffile.imread(path).astype(float) for path in frames], axis=0)
    reference = tifffile.imread(root / "FI.tif").astype(float)
    r2 = tifffile.imread(root / "R2.tif").astype(float)
    snr = tifffile.imread(root / "SNR.tif").astype(float)
    eligible = np.isfinite(reference) & np.isfinite(r2) & np.isfinite(snr) & (r2 >= 0.90) & (snr >= 3.0) & (image > 0)
    eligible[:8] = False; eligible[-8:] = False; eligible[:, :8] = False; eligible[:, -8:] = False
    yy, xx = np.nonzero(eligible)
    angles, _, _ = _tensor_fields(image, scales=(2.0, 4.0))
    smoothed = ndimage.gaussian_filter(image, sigma=2.0, mode="reflect")
    gy, gx = np.gradient(smoothed)
    gradient = np.degrees(np.mod(np.arctan2(gy, gx) + np.pi / 2, np.pi))
    ref = np.mod(reference[yy, xx] + reference_offset_degrees, 180.0)
    return {"primary": _axial_errors(angles[0, yy, xx], ref),
            "sigma4": _axial_errors(angles[1, yy, xx], ref),
            "gradient": _axial_errors(gradient[yy, xx], ref)}


def _summary(grouped: list[np.ndarray], bootstrap: bool = False, seed: int = 7242322) -> dict:
    pooled = np.concatenate(grouped)
    result = {"eligible_rois": len(grouped), "eligible_pixels": len(pooled),
              "median_error": float(np.median(pooled)), "p75_error": float(np.percentile(pooled, 75)),
              "median_roi_median_error": float(np.median([np.median(row) for row in grouped])),
              "axial_alignment": float(np.mean(np.cos(2 * np.radians(pooled))))}
    if bootstrap:
        result["median_error_roi_bootstrap95"] = _bootstrap_median(grouped, draws=10000, seed=seed)
    return result


def run_validation(dataset_root: Path, output: Path, *, reference_offset_degrees: float = 0.0,
                   protocol_version: str = "nostos-pshg-external-orientation/1.0",
                   protocol_sha256: str = PROTOCOL_SHA256, bootstrap_seed: int = 7242322) -> dict:
    manifest_path = dataset_root / "download_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rois = sorted(path for path in dataset_root.iterdir() if path.is_dir())
    errors = {"primary": [], "sigma4": [], "gradient": []}
    cases = []
    for roi in rois:
        values = _case(roi, reference_offset_degrees)
        if not len(values["primary"]):
            continue
        for name in errors:
            errors[name].append(values[name])
        cases.append({"roi": roi.name, "eligible_pixels": len(values["primary"]),
                      "median_error": float(np.median(values["primary"]))})
    primary = _summary(errors["primary"], bootstrap=True, seed=bootstrap_seed)
    sigma4 = _summary(errors["sigma4"])
    gradient = _summary(errors["gradient"])
    gates = {"eligible_rois_ge_30": primary["eligible_rois"] >= 30,
             "eligible_pixels_ge_50000": primary["eligible_pixels"] >= 50000,
             "median_error_le_15_degrees": primary["median_error"] <= 15.0,
             "bootstrap_upper_le_15_degrees": primary["median_error_roi_bootstrap95"][1] <= 15.0,
             "p75_error_le_30_degrees": primary["p75_error"] <= 30.0,
             "median_roi_median_error_le_15_degrees": primary["median_roi_median_error"] <= 15.0,
             "axial_alignment_ge_0_65": primary["axial_alignment"] >= 0.65,
             "noninferior_to_sigma4_within_2_degrees": primary["median_error"] <= sigma4["median_error"] + 2.0,
             "noninferior_to_gradient_within_2_degrees": primary["median_error"] <= gradient["median_error"] + 2.0}
    payload = {"protocol_version": protocol_version, "protocol_sha256": protocol_sha256,
               "dataset": {"doi": manifest["doi"], "subset": manifest["subset"],
                           "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                           "reference_offset_degrees": reference_offset_degrees},
               "status": "pass" if all(gates.values()) else "fail", "primary": primary,
               "comparators": {"sigma4": sigma4, "smoothed_gradient": gradient},
               "success_gates": gates,
               "scope": "Pristine external-acquisition validation of a scale-declared local 2D direction field against polarization-SHG orientation.",
               "cases": cases}
    output.mkdir(parents=True, exist_ok=True)
    (output / "pshg_external_orientation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
