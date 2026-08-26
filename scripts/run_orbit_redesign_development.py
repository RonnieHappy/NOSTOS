from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.biological_retrieval import load_cases, run_orbit_redesign_development


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("pshg_root", "nuclei_root", "mycelium_root", "collagen_root", "output"):
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.pshg_root, args.nuclei_root, args.mycelium_root, args.collagen_root)
    payload = run_orbit_redesign_development(cases, args.output)
    print(json.dumps({name: row["top1_macro"] for name, row in payload["results"].items()}, indent=2))


if __name__ == "__main__":
    main()
