"""Run the frozen PSHG acquisition-shift development/lock/confirmation workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.pshg_acquisition_shift import (
    freeze_profile,
    run_confirmation,
    run_development,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("development", "confirmation"):
        command = subparsers.add_parser(name)
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--protocol", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "confirmation":
            command.add_argument("--profile", type=Path, required=True)
            command.add_argument("--lock", type=Path, required=True)
    lock = subparsers.add_parser("freeze")
    lock.add_argument("--dataset", type=Path, required=True)
    lock.add_argument("--config", type=Path, required=True)
    lock.add_argument("--protocol", type=Path, required=True)
    lock.add_argument("--profile", type=Path, required=True)
    lock.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "development":
        result = run_development(args.dataset, args.config, args.protocol, args.output)
    elif args.command == "freeze":
        result = freeze_profile(args.dataset, args.config, args.protocol, args.profile, args.lock)
    else:
        result = run_confirmation(
            args.dataset,
            args.config,
            args.protocol,
            args.profile,
            args.lock,
            args.output,
        )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
