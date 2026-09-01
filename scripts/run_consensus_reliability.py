from __future__ import annotations
import argparse, json
from pathlib import Path
from nostos.validation.consensus_reliability import run_development_confirmation

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_development_confirmation(args.dataset_root, args.output)
    print(json.dumps({"status": result["status"], "development": result["development"],
                      "confirmation": result["confirmation"], "gates": result["success_gates"]}, indent=2))

if __name__ == "__main__":
    main()

