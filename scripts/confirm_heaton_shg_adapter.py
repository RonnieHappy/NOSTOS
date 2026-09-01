"""Execute the frozen Heaton Exp15 confirmation exactly once."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from nostos.validation.heaton_shg_confirmation import run_confirmation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--official-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    args = parser.parse_args()
    result = run_confirmation(
        args.stage.resolve(),
        args.config.resolve(),
        args.protocol.resolve(),
        args.lock.resolve(),
        args.official_receipt.resolve(),
        args.output_dir.resolve(),
        args.workers,
    )
    print(json.dumps({"status": result["status"], "success_gates": result["success_gates"]}, indent=2))


if __name__ == "__main__":
    main()
