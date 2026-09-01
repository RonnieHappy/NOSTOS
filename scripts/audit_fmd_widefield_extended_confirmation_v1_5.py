from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_widefield_extended_confirmation import run_extended_audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the no-refit seven-field FMD widefield v1.5 extension."
    )
    parser.add_argument("extension_rows", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_extended_audit(
        args.extension_rows.resolve(),
        args.config.resolve(),
        args.output.resolve(),
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
