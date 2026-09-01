"""Run the independent PSHG acquisition-shift confirmation audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.pshg_acquisition_shift_audit import run_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = run_audit(
        dataset_root=args.dataset,
        config_path=args.config,
        protocol_path=args.protocol,
        profile_path=args.profile,
        lock_path=args.lock,
        result_path=args.result,
        rows_path=args.rows,
        output_path=args.output,
    )
    print(json.dumps(audit, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
