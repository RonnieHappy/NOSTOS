from __future__ import annotations
import argparse, json
from pathlib import Path
from nostos.validation.selective_filament_transfer import run_transfer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_transfer(args.data_root, args.output)
    print(json.dumps({"status": result["status"], "summary": result["summary"], "gates": result["success_gates"]}, indent=2))

if __name__ == "__main__":
    main()

