"""Pristine transfer of the post-failure lineage rule to reserved HeLa sequence 02."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from confirm_ctc_tracking import run_dataset


PARAMETERS = {"division_combined_area_range": (0.4, 1.5), "division_child_area_range": (0.05, 1.3),
              "division_balance_max": 8.0, "division_distance_radii": 2.0, "division_separation_radii": 3.0}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--hela-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run_dataset(args.hela_root, "02", "02_ST/SEG", 1.6, 10.0, PARAMETERS)
    gates = {"mapping_coverage": result["mapping_coverage"] >= 0.80, "link_f1": result["metrics"]["links"]["f1"] >= 0.80,
             "identity_switches": result["metrics"]["identity_switch_fraction"] <= 0.05,
             "baseline": result["metrics"]["links"]["f1"] >= result["baseline"]["links"]["f1"] - 0.02,
             "division_f1": result["metrics"]["divisions"]["reference"] < 5 or result["metrics"]["divisions"]["f1"] >= 0.45,
             "finite_calibrated": result["finite_measurement_fraction"] >= 0.90,
             "runtime": result["runtime_seconds"] < 300.0}
    payload = {"protocol_version": "nostos0-ctc-hela02-lineage-transfer/1.0", "status": "pass" if all(gates.values()) else "fail",
               "source": {"dataset": "Fluo-N2DL-HeLa", "sequence": "02", "archive_sha256": "35dd99d58e071aba0b03880128d920bd1c063783cc280f9531fbdc5be614c82e", "url": "https://celltrackingchallenge.net/2d-datasets/"},
               "parameters": {key: list(value) if isinstance(value, tuple) else value for key, value in PARAMETERS.items()}, "result": result, "gates": gates,
               "interpretation": "Pristine real-sequence transfer of a post-failure synthetic-developed lineage rule; imported silver masks, not automatic segmentation or hidden CTC test performance."}
    args.output.mkdir(parents=True, exist_ok=True); (args.output / "ctc_hela02_lineage_transfer.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "result": result, "gates": gates}, indent=2)); raise SystemExit(0 if payload["status"] == "pass" else 1)


if __name__ == "__main__": main()
