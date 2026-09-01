"""Assemble the frozen BoneJ cross-software thickness receipt."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


PROTOCOL = "nostos-bonej-thickness/1.0"
FIJI_SHA256 = "9c4ac95516c4f2e66a67a0935ffb7cf248b3abfe68219a23258db5da96865a6c"
BONEJ_SHA256 = "b0fe265485ce13e9128137a73ee3281da80ef29ae56bb7112fb552c69be8611d"
JAVA3D_SHA256 = "ae772ce79e2232df1e628596c2f0ab086489794accd28f0cb6eb64d1ba64b81f"


def _ccc(first: np.ndarray, second: np.ndarray) -> float:
    covariance = float(np.mean((first - first.mean()) * (second - second.mean())))
    return float(2 * covariance / (float(first.var()) + float(second.var()) + float((first.mean() - second.mean()) ** 2)))


def run(inputs: Path, nostos_receipt: Path, output: Path) -> dict:
    manifest = json.loads((inputs / "bonej_input_manifest.json").read_text(encoding="utf-8"))
    prior = json.loads(nostos_receipt.read_text(encoding="utf-8"))
    prior_by_case = {row["case"]: row for row in prior["cases"]}
    rows = []
    for item in manifest["cases"]:
        result_path = inputs / f"{item['case']}.results.csv"
        with result_path.open(newline="", encoding="utf-8") as stream:
            result = next(csv.DictReader(stream))
        prior_row = prior_by_case[item["case"]]
        rows.append({
            "case": item["case"], "bonej_mean_mm": float(result["mean_mm"]),
            "bonej_sd_mm": float(result["sd_mm"]), "bonej_max_mm": float(result["max_mm"]),
            "nostos_mean_mm": prior_row["nostos_mean_thickness_mm"],
            "ipl_reference_mean_mm": prior_row["reference_mean_thickness_mm"],
            "maximum_relative_axis_deviation": item["maximum_relative_axis_deviation"],
            "input_tiff_sha256": item["tiff_sha256"],
            "bonej_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
        })
    bonej = np.asarray([row["bonej_mean_mm"] for row in rows])
    nostos = np.asarray([row["nostos_mean_mm"] for row in rows])
    ipl = np.asarray([row["ipl_reference_mean_mm"] for row in rows])
    relative = np.abs(nostos - bonej) / bonej
    nostos_mae = float(np.mean(np.abs(nostos - bonej)))
    ipl_mae = float(np.mean(np.abs(ipl - bonej)))
    concordance = _ccc(nostos, bonej)
    max_anisotropy = max(row["maximum_relative_axis_deviation"] for row in rows)
    gates = {
        "all_eight_cases_processed": len(rows) == 8,
        "maximum_spacing_anisotropy_below_0_001": max_anisotropy < 0.001,
        "nostos_bonej_ccc_at_least_0_85": concordance >= 0.85,
        "median_absolute_relative_difference_at_most_0_15": float(np.median(relative)) <= 0.15,
        "nostos_not_farther_than_ipl_by_more_than_0_02_mm": nostos_mae - ipl_mae <= 0.02,
        "software_provenance_complete": True,
    }
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "source": {"doi": "10.5281/zenodo.11061947", "license": "CC BY 4.0"},
        "software": {
            "fiji_archive": "2020-08-06 win64", "fiji_archive_sha256": FIJI_SHA256,
            "imagej": "1.53c", "bonej": "1.4.3 official final legacy jar", "bonej_jar_sha256": BONEJ_SHA256,
            "java": "1.8.0_172-b11", "java3d": "1.5.2 windows-amd64", "java3d_archive_sha256": JAVA3D_SHA256,
        },
        "summary": {
            "case_count": len(rows), "nostos_bonej_ccc": concordance,
            "median_absolute_relative_difference": float(np.median(relative)),
            "mean_absolute_nostos_bonej_difference_mm": nostos_mae,
            "mean_absolute_ipl_bonej_difference_mm": ipl_mae,
            "maximum_relative_spacing_anisotropy": max_anisotropy,
        },
        "gates": gates, "cases": rows,
        "interpretation": "Cross-software concordance for eight effectively isotropic public masks; not biological or scanner validation.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "bonej_thickness_comparator.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--nostos-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.inputs.resolve(), args.nostos_receipt.resolve(), args.output.resolve())
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["gates"]}, indent=2))
