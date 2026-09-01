from __future__ import annotations
import argparse,json
from pathlib import Path
from nostos.validation.selective_fft_confirmation import run_confirmation
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--cases",type=int,default=600);a=p.parse_args();r=run_confirmation(a.output,a.cases);print(json.dumps({"status":r["status"],"output":str((a.output/"selective_fft_confirmation.json").resolve()),"summary":r["summary"],"gates":r["success_gates"]},indent=2))
if __name__=="__main__":main()
