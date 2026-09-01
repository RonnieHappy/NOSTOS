from __future__ import annotations
import argparse, json
from pathlib import Path
from nostos.validation.stability_weighting_development import run_stability_development

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--dataset",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    result=run_stability_development(args.dataset,args.output)
    print(json.dumps({"output":str((args.output/"stability_weighting_development.json").resolve()),
                      "accuracies":{name:value["balanced_accuracy"] for name,value in result["results"].items()}},indent=2))
if __name__=="__main__": main()
