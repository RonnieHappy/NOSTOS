"""Generate, run or finalize the frozen canonical-geometry confirmation v3."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from nostos.validation.canonical_confirmation_v3 import finalize, generate_dataset, run_internal

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest="command",required=True)
    g=commands.add_parser("generate"); g.add_argument("--dataset",type=Path,required=True)
    i=commands.add_parser("internal"); i.add_argument("--dataset",type=Path,required=True); i.add_argument("--output",type=Path,required=True)
    f=commands.add_parser("finalize"); f.add_argument("--internal",type=Path,required=True); f.add_argument("--kymatio",type=Path,required=True); f.add_argument("--pyradiomics",type=Path,required=True); f.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="generate": payload={"dataset":str(generate_dataset(args.dataset).resolve())}
    elif args.command=="internal":
        result=run_internal(args.dataset,args.output); payload={"output":str((args.output/"internal_results.json").resolve()),"accuracies":{row["representation"]:row["balanced_accuracy"] for row in result["results"]}}
    else:
        result=finalize(args.internal,args.kymatio,args.pyradiomics,args.output); payload={"status":result["status"],"output":str((args.output/"canonical_confirmation_v3.json").resolve()),"gates":result["success_gates"]}
    print(json.dumps(payload,indent=2,allow_nan=False))
if __name__=="__main__": main()
