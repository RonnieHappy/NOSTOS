from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.biological_retrieval import load_cases, run_confirmation


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("pshg_root", "nuclei_root", "mycelium_root", "collagen_root", "development_receipt", "output"):
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.pshg_root, args.nuclei_root, args.mycelium_root, args.collagen_root)
    payload = run_confirmation(cases, args.development_receipt, args.output)
    print(json.dumps({"status": payload["status"], "primary": payload["primary"],
                      "gates": payload["success_gates"]}, indent=2))


if __name__ == "__main__":
    main()
