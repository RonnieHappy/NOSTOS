from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_strict_external_transfer import build_transfer_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the locked FMD v1.6 strict-profile external transfer."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--transfer-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_transfer_rows(
        args.data.resolve(),
        args.config.resolve(),
        args.transfer_lock.resolve(),
        args.output.resolve(),
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
