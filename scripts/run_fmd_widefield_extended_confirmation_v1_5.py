from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_widefield_extended_confirmation import (
    build_extended_confirmation_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the locked seven-field FMD widefield v1.5 extension."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--extension-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_extended_confirmation_rows(
        args.data.resolve(),
        args.config.resolve(),
        args.extension_lock.resolve(),
        args.output.resolve(),
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
