from __future__ import annotations
import argparse,json
from pathlib import Path
from nostos.validation.uvpam_abstention import run
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--archive",type=Path,required=True);p.add_argument("--config",type=Path,default=Path("configs/uvpam_abstention.locked.json"));p.add_argument("--output",type=Path,default=Path("outputs/nostos0-uvpam-abstention"));a=p.parse_args();print(json.dumps(run(a.archive,a.config,a.output),indent=2))

