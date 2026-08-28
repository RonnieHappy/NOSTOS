from __future__ import annotations
import argparse, json
from pathlib import Path
from nostos.validation.bone_network_3d import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/bone_3d_network_contract.locked.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/nostos0-bone-network-3d"))
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.config, args.output), indent=2))

