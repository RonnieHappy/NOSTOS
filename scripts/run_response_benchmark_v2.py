"""Generate, run, or finalize the frozen NOSTOS response-geometry benchmark v2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.response_geometry_benchmark_v2 import finalize, generate_dataset, run_internal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--dataset", type=Path, required=True)
    internal = commands.add_parser("internal")
    internal.add_argument("--dataset", type=Path, required=True)
    internal.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--internal", type=Path, required=True)
    finish.add_argument("--kymatio", type=Path, required=True)
    finish.add_argument("--pyradiomics", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        path = generate_dataset(args.dataset)
        payload = {"dataset": str(path.resolve())}
    elif args.command == "internal":
        result = run_internal(args.dataset, args.output)
        payload = {"output": str((args.output / "internal_results.json").resolve()), "results": result["results"]}
    else:
        result = finalize(args.internal, args.kymatio, args.pyradiomics, args.output)
        payload = {"status": result["status"], "output": str((args.output / "response_geometry_benchmark_v2.json").resolve()), "gates": result["success_gates"]}
    print(json.dumps(payload, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
