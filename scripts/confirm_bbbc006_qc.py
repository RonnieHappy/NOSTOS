"""Execute the identity-disjoint BBBC006 Tenengrad QC confirmation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile

from nostos.core.qc import acquisition_qc


PROTOCOL = "nostos-bbbc006-qc-confirmation/1.0"


def run(data: Path, output: Path) -> dict:
    manifest = json.loads((data / "selection_manifest.json").read_text(encoding="utf-8"))
    rows = []
    for case in manifest["selected_cases"]:
        scores = {plane: acquisition_qc(tifffile.imread(data / plane / f"{case}.tif"))["tenengrad_focus_v2"] for plane in ("z00", "z15", "z16")}
        rows.append({"case": case, "scores": scores})
    z00 = np.asarray([row["scores"]["z00"] for row in rows]); z15 = np.asarray([row["scores"]["z15"] for row in rows]); z16 = np.asarray([row["scores"]["z16"] for row in rows])
    rng = np.random.default_rng(6008); indices = rng.integers(0, len(rows), size=(20000, len(rows)))
    differences = {"z16_z00": z16 - z00, "z15_z00": z15 - z00}
    intervals = {name: [float(np.quantile(np.median(values[indices], axis=1), q)) for q in (0.025, 0.975)] for name, values in differences.items()}
    constant = acquisition_qc(np.ones((32, 32))); clipped_image = np.zeros((32, 32)); clipped_image[8:24, 8:24] = 1; clipped = acquisition_qc(clipped_image)
    ratio = float(np.median(z15 / np.maximum(z16, np.finfo(float).eps)))
    gates = {
        "all_128_triplets_finite": len(rows) == 128 and bool(np.isfinite([*z00, *z15, *z16]).all()),
        "z16_exceeds_z00_in_at_least_90_percent": float(np.mean(z16 > z00)) >= 0.90,
        "z15_exceeds_z00_in_at_least_90_percent": float(np.mean(z15 > z00)) >= 0.90,
        "median_adjacent_focus_ratio_between_0_5_and_2": 0.5 <= ratio <= 2.0,
        "both_bootstrap_intervals_exclude_zero": intervals["z16_z00"][0] > 0 and intervals["z15_z00"][0] > 0,
        "failure_flags_retained": constant["status"] == "abstain" and clipped["status"] == "review",
    }
    payload = {
        "protocol_version": PROTOCOL, "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(), "status": "pass" if all(gates.values()) else "fail",
        "source": {"dataset": "BBBC006v1", "selection": manifest["selection"], "selection_manifest_sha256": hashlib.sha256((data / "selection_manifest.json").read_bytes()).hexdigest(), "identity_disjoint_from_development": True},
        "measurement": "mean squared Sobel magnitude, reflect boundary, tenengrad_focus_v2",
        "summary": {"case_count": len(rows), "fraction_z16_exceeds_z00": float(np.mean(z16 > z00)), "fraction_z15_exceeds_z00": float(np.mean(z15 > z00)), "median_z15_z16_ratio": ratio, "median_z16_minus_z00": float(np.median(z16-z00)), "median_z15_minus_z00": float(np.median(z15-z00)), "bootstrap_95_intervals": intervals},
        "gates": gates, "controls": {"constant": constant, "high_endpoint_fraction": clipped}, "cases": rows,
        "interpretation": "Identity-disjoint confirmation of relative focus ordering; no universal acceptable-focus threshold.",
    }
    output.mkdir(parents=True, exist_ok=True); (output / "bbbc006_qc_confirmation.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--data", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = run(args.data.resolve(), args.output.resolve()); print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
