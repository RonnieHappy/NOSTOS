from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.bone_orientation_v2 import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/bone_contract_orientation_v2.locked.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/nostos0-bone-orientation-v2"))
    args = parser.parse_args()
    print(json.dumps(run(args.images, args.masks, args.config, args.output), indent=2))


if __name__ == "__main__":
    main()

