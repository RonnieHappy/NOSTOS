from __future__ import annotations
import argparse, json
from pathlib import Path
from nostos.validation.human_nanoct_transfer import run

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--data",type=Path,required=True)
    p.add_argument("--config",type=Path,default=Path("configs/human_nanoct_transfer.locked.json"))
    p.add_argument("--output",type=Path,default=Path("outputs/nostos0-human-nanoct-transfer")); a=p.parse_args()
    print(json.dumps(run(a.data,a.config,a.output),indent=2))

