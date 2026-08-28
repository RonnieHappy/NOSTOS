from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.bone_contract_orientation import run

parser = argparse.ArgumentParser()
parser.add_argument("--data", type=Path, required=True)
parser.add_argument("--config", type=Path, default=Path("configs/bone_contract_orientation.locked.json"))
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
print(json.dumps(run(args.data, args.config, args.output), indent=2))
