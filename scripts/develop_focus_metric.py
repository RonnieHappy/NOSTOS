"""Development-only focus-metric selection on the opened 64 BBBC006 fields."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from scipy import ndimage


PROTOCOL = "nostos-focus-metric-development/1.0"


def _metrics(image: np.ndarray) -> dict[str, float]:
    data = np.asarray(image, dtype=float)
    gx = ndimage.sobel(data, axis=1, mode="reflect")
    gy = ndimage.sobel(data, axis=0, mode="reflect")
    gradient = gx * gx + gy * gy
    laplacian = ndimage.laplace(data, mode="reflect")
    centered = data - float(data.mean())
    power = np.abs(np.fft.fftshift(np.fft.fft2(centered))) ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(data.shape[0])); fx = np.fft.fftshift(np.fft.fftfreq(data.shape[1]))
    yy, xx = np.meshgrid(fy, fx, indexing="ij"); radius = np.sqrt(xx * xx + yy * yy)
    eligible = radius > 0
    total = float(power[eligible].sum())
    return {
        "laplacian_variance_raw": float(np.var(laplacian)),
        "tenengrad_mean": float(np.mean(gradient)),
        "tenengrad_p90": float(np.percentile(gradient, 90)),
        "high_frequency_fraction_0_20": float(power[radius >= 0.20].sum() / max(total, np.finfo(float).eps)),
        "high_frequency_fraction_0_30": float(power[radius >= 0.30].sum() / max(total, np.finfo(float).eps)),
    }


def run(data: Path, output: Path) -> dict:
    manifest = json.loads((data / "selection_manifest.json").read_text(encoding="utf-8"))
    values = {name: {plane: [] for plane in ("z00", "z15", "z16")} for name in _metrics(tifffile.imread(data / "z16" / f"{manifest['selected_cases'][0]}.tif"))}
    for case in manifest["selected_cases"]:
        for plane in ("z00", "z15", "z16"):
            measured = _metrics(tifffile.imread(data / plane / f"{case}.tif"))
            for name, value in measured.items():
                values[name][plane].append(value)
    summaries = {}
    for name, planes in values.items():
        arrays = {plane: np.asarray(items) for plane, items in planes.items()}
        fractions = [float(np.mean(arrays[plane] > arrays["z00"])) for plane in ("z15", "z16")]
        summaries[name] = {"fraction_z15_exceeds_z00": fractions[0], "fraction_z16_exceeds_z00": fractions[1], "minimum_fraction": min(fractions), "median_z15_z16_ratio": float(np.median(arrays["z15"] / np.maximum(arrays["z16"], np.finfo(float).eps)))}
    selected = max(summaries, key=lambda name: (summaries[name]["minimum_fraction"], name))
    payload = {
        "protocol_version": PROTOCOL, "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "development_complete", "source": "opened 64-case BBBC006 development subset",
        "selection_rule": "maximum minimum fraction for z15 and z16 exceeding z00; lexical tie break",
        "candidates": summaries, "selected_metric": selected,
        "interpretation": "Development only; selected metric requires identity-disjoint confirmation.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "focus_metric_development.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--data", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(run(args.data.resolve(), args.output.resolve()), indent=2))
