"""Run the training-only canonical-geometry development audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.canonical_development import run_canonical_development


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = run_canonical_development(args.dataset, args.output)
    print(json.dumps({"output": str((args.output / "canonical_development.json").resolve()),
                      "minimum_balanced_accuracy": payload["minimum_balanced_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
