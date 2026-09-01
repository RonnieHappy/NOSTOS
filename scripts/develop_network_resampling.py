"""Development-only HRF comparison of binary-mask resampling policies."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from nostos.features.response_modules import erosion_survival_response


PROTOCOL = "nostos-network-resampling-development/1.1"


def _occupancy(mask: np.ndarray) -> np.ndarray:
    height = mask.shape[0] - mask.shape[0] % 2
    width = mask.shape[1] - mask.shape[1] % 2
    return mask[:height, :width].reshape(height // 2, 2, width // 2, 2).mean(axis=(1, 3))


def run(root: Path, source_receipt: Path, output: Path) -> dict:
    source = json.loads(source_receipt.read_text(encoding="utf-8"))
    if source.get("protocol_version") != "nostos-hrf-network/1.0":
        raise ValueError("Expected the frozen failed HRF source receipt.")
    thresholds = (0.0, 2.0, 4.0, 8.0)
    policies = {"occupancy_0_25": 0.25, "occupancy_0_50": 0.50, "occupancy_0_75": 0.75, "occupancy_any": 0.01}
    results = {}
    paths = sorted((root / "manual1").glob("*.tif"))
    native_by_case = {}
    occupancies = {}
    for mask_path in paths:
        mask = np.asarray(Image.open(mask_path)) > 0
        native_by_case[mask_path.stem] = np.asarray(erosion_survival_response(mask, spacing_um=(1.0, 1.0), thresholds_um=thresholds, boundary_corrected=True).surviving_fraction)
        occupancies[mask_path.stem] = _occupancy(mask)
    for name, cutoff in policies.items():
        differences = []
        for mask_path in paths:
            reduced = occupancies[mask_path.stem] >= cutoff
            response = erosion_survival_response(reduced, spacing_um=(2.0, 2.0), thresholds_um=thresholds, boundary_corrected=True)
            differences.append(np.abs(np.asarray(response.surviving_fraction) - native_by_case[mask_path.stem]))
        matrix = np.asarray(differences)
        results[name] = {
            "occupancy_cutoff": cutoff,
            "median_absolute_difference": np.median(matrix, axis=0).tolist(),
            "mean_nonzero_threshold_difference": float(np.mean(matrix[:, 1:])),
            "maximum_median_nonzero_threshold_difference": float(np.max(np.median(matrix[:, 1:], axis=0))),
        }
    selected = min(results, key=lambda name: (results[name]["mean_nonzero_threshold_difference"], name))
    payload = {
        "protocol_version": PROTOCOL,
        "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "development_complete",
        "source_dataset": "HRF; previously opened development data",
        "change_from_failed_protocol": "voxel-boundary-corrected EDT plus occupancy-policy development",
        "selection_rule": "minimum mean absolute native-versus-twofold difference over nonzero physical erosion thresholds",
        "policies": results,
        "selected_policy": selected,
        "selected_occupancy_cutoff": results[selected]["occupancy_cutoff"],
        "interpretation": "Post-failure development only. The selected policy requires confirmation on an untouched archive.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "network_resampling_development.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.data.resolve(), args.source_receipt.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2))
