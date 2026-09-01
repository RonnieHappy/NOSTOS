"""Run the frozen PSHG structure-tensor cross-software audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from scipy import ndimage
from scipy.stats import spearmanr
from skimage.feature import structure_tensor


PROTOCOL = "nostos-structure-tensor-comparator/1.0"
MANIFEST_SHA256 = "441553b9f5af96f285b40dc042dd6fe2681e919020f28126819f80f1830d768d"


def _axial_errors(measured: np.ndarray, reference: np.ndarray) -> np.ndarray:
    difference = np.abs(measured - reference) % 180.0
    return np.minimum(difference, 180.0 - difference)


def _nostos_sigma2(image: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(np.asarray(image, dtype=float))
    jxx = ndimage.gaussian_filter(gx * gx, sigma=2.0, mode="reflect")
    jyy = ndimage.gaussian_filter(gy * gy, sigma=2.0, mode="reflect")
    jxy = ndimage.gaussian_filter(gx * gy, sigma=2.0, mode="reflect")
    return np.degrees(np.mod(0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2, np.pi))


def run(root: Path, output: Path) -> dict:
    import skimage

    rows, nostos_grouped, upstream_grouped, disagreements = [], [], [], []
    for roi in sorted(path for path in root.iterdir() if path.is_dir()):
        frames = sorted(roi.glob("*_FSHG_p*.tif"), key=lambda path: int(path.stem.rsplit("p", 1)[1]))
        if len(frames) != 10:
            continue
        image = np.mean([tifffile.imread(path).astype(float) for path in frames], axis=0)
        reference = tifffile.imread(roi / "FI.tif").astype(float)
        r2 = tifffile.imread(roi / "R2.tif").astype(float)
        snr = tifffile.imread(roi / "SNR.tif").astype(float)
        eligible = np.isfinite(reference) & np.isfinite(r2) & np.isfinite(snr) & (r2 >= 0.90) & (snr >= 3.0) & (image > 0)
        eligible[:8] = False; eligible[-8:] = False; eligible[:, :8] = False; eligible[:, -8:] = False
        yy, xx = np.nonzero(eligible)
        nostos_angles = _nostos_sigma2(image)
        arr, arc, acc = structure_tensor(image, sigma=2.0, mode="reflect", order="rc")
        upstream_angles = np.degrees(np.mod(0.5 * np.arctan2(2 * arc, acc - arr) + np.pi / 2, np.pi))
        ref = np.mod(reference[yy, xx] + 90.0, 180.0)
        nostos_error = _axial_errors(nostos_angles[yy, xx], ref)
        upstream_error = _axial_errors(upstream_angles[yy, xx], ref)
        disagreement = _axial_errors(nostos_angles[yy, xx], upstream_angles[yy, xx])
        nostos_grouped.append(nostos_error); upstream_grouped.append(upstream_error); disagreements.append(disagreement)
        rows.append({"roi": roi.name, "eligible_pixels": len(yy), "nostos_median_error": float(np.median(nostos_error)), "skimage_median_error": float(np.median(upstream_error)), "median_disagreement": float(np.median(disagreement))})
    nostos_all = np.concatenate(nostos_grouped)
    upstream_all = np.concatenate(upstream_grouped)
    disagreement_all = np.concatenate(disagreements)
    roi_rho = float(spearmanr([row["nostos_median_error"] for row in rows], [row["skimage_median_error"] for row in rows]).statistic)
    gates = {
        "all_48_rois_and_one_million_pixels": len(rows) == 48 and len(nostos_all) >= 1_000_000,
        "all_orientations_finite": bool(np.isfinite(nostos_all).all() and np.isfinite(upstream_all).all() and np.isfinite(disagreement_all).all()),
        "nostos_noninferior_within_2_degrees": float(np.median(nostos_all)) <= float(np.median(upstream_all)) + 2.0,
        "median_cross_software_disagreement_at_most_10_degrees": float(np.median(disagreement_all)) <= 10.0,
        "roi_error_spearman_at_least_0_75": roi_rho >= 0.75,
        "provenance_complete": skimage.__version__ == "0.25.2",
    }
    payload = {
        "protocol_version": PROTOCOL, "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "dataset": {"doi": "10.17605/OSF.IO/UDTQP", "subset": "breast tissue unstained / FSHG", "manifest_sha256": MANIFEST_SHA256},
        "comparator": {"implementation": "skimage.feature.structure_tensor", "version": skimage.__version__, "sigma_pixels": 2.0},
        "summary": {"roi_count": len(rows), "eligible_pixels": len(nostos_all), "nostos_median_error": float(np.median(nostos_all)), "skimage_median_error": float(np.median(upstream_all)), "median_cross_software_disagreement": float(np.median(disagreement_all)), "roi_error_spearman": roi_rho},
        "gates": gates, "cases": rows,
        "interpretation": "Post-confirmation cross-software consistency audit; not a new biological confirmation or superiority claim.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "structure_tensor_comparator.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.data.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
