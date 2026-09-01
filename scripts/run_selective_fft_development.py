from __future__ import annotations
import argparse,json
from pathlib import Path
from nostos.validation.selective_fft_development import run_development
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--cases",type=int,default=500);a=p.parse_args();r=run_development(a.output,a.cases);print(json.dumps({"output":str((a.output/"selective_fft_development.json").resolve()),"selected_threshold":r["selected_threshold"]},indent=2))
if __name__=="__main__":main()
