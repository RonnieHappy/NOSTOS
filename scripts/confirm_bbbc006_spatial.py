"""Execute the frozen BBBC006 spatial-response confirmation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from scipy.stats import spearmanr

from nostos.features.response_modules import directional_variogram


PROTOCOL = "nostos-bbbc006-spatial-confirmation/1.0"


def _response(path: Path, spacing: float, separations: tuple[float, ...]) -> dict:
    image = np.asarray(tifffile.imread(path), dtype=float)
    measured = directional_variogram(image, spacing_um=(spacing, spacing), separations_um=separations)
    curve = (np.asarray(measured.horizontal) + np.asarray(measured.vertical)) / 2.0
    maximum = float(curve.max())
    return {
        "horizontal": list(measured.horizontal), "vertical": list(measured.vertical),
        "normalized_mean": None if maximum <= 0 else (curve / maximum).tolist(),
        "mean_estimated_range_um": float((measured.estimated_range_horizontal_um + measured.estimated_range_vertical_um) / 2.0),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def run(data: Path, output: Path) -> dict:
    manifest = json.loads((data / "selection_manifest.json").read_text(encoding="utf-8"))
    spacing = 0.645
    separations = tuple(spacing * value for value in (1, 2, 4, 8, 16, 24))
    rows, abstentions = [], []
    for case in manifest["selected_cases"]:
        responses = {plane: _response(data / plane / f"{case}.tif", spacing, separations) for plane in ("z00", "z15", "z16")}
        if any(responses[plane]["normalized_mean"] is None for plane in responses):
            abstentions.append({"case": case, "code": "ZERO_SPATIAL_SEMIVARIANCE"})
            continue
        z00 = np.asarray(responses["z00"]["normalized_mean"])
        z15 = np.asarray(responses["z15"]["normalized_mean"])
        z16 = np.asarray(responses["z16"]["normalized_mean"])
        adjacent = float(np.sqrt(np.mean((z15 - z16) ** 2)))
        defocus = float(np.sqrt(np.mean((z00 - z16) ** 2)))
        rows.append({"case": case, "responses": responses, "adjacent_distance": adjacent, "defocus_distance": defocus, "defocus_minus_adjacent": defocus - adjacent})
    adjacent = np.asarray([row["adjacent_distance"] for row in rows])
    defocus = np.asarray([row["defocus_distance"] for row in rows])
    paired = defocus - adjacent
    z15_range = np.asarray([row["responses"]["z15"]["mean_estimated_range_um"] for row in rows])
    z16_range = np.asarray([row["responses"]["z16"]["mean_estimated_range_um"] for row in rows])
    range_rho = float(spearmanr(z15_range, z16_range).statistic)
    rng = np.random.default_rng(6006)
    bootstrap = np.median(paired[rng.integers(0, len(paired), size=(20000, len(paired)))], axis=1) if len(paired) else np.asarray([np.nan])
    interval = [float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975))]
    gates = {
        "all_64_triplets_processed": len(rows) == 64 and not abstentions,
        "all_outputs_finite": bool(rows) and all(np.isfinite([*row["responses"]["z00"]["horizontal"], *row["responses"]["z15"]["horizontal"], *row["responses"]["z16"]["horizontal"]]).all() for row in rows),
        "adjacent_range_spearman_at_least_0_75": range_rho >= 0.75,
        "median_adjacent_curve_distance_at_most_0_15": float(np.median(adjacent)) <= 0.15,
        "defocus_distance_greater_in_at_least_75_percent": float(np.mean(defocus > adjacent)) >= 0.75,
        "paired_bootstrap_interval_excludes_zero": interval[0] > 0,
    }
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "source": {"dataset": "BBBC006v1", "url": "https://bbbc.broadinstitute.org/BBBC006", "license": "public-domain dedication", "archive_sha256": manifest["archive_sha256"]},
        "calibration": {"spacing_um": spacing, "derivation": "6.45 um camera pixels * 2 binning / 20x magnification"},
        "selection": manifest["selection"], "selected_cases": manifest["selected_cases"],
        "summary": {
            "case_count": len(rows), "abstention_count": len(abstentions),
            "z15_z16_range_spearman": range_rho,
            "median_adjacent_curve_distance": float(np.median(adjacent)),
            "median_defocus_curve_distance": float(np.median(defocus)),
            "fraction_defocus_greater": float(np.mean(defocus > adjacent)),
            "median_defocus_minus_adjacent": float(np.median(paired)),
            "paired_bootstrap_95_interval": interval,
        },
        "gates": gates, "abstentions": abstentions, "cases": rows,
        "interpretation": "Repeatability and focus sensitivity of the spatial estimator; not biological correlation-length truth.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "bbbc006_spatial_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.data.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
