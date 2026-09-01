from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_widefield_conditional_run import (
    build_conditional_confirmation_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the one-shot FMD widefield conditional-support confirmation."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base-profile", type=Path, required=True)
    parser.add_argument("--conditional-profile", type=Path, required=True)
    parser.add_argument("--confirmation-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_conditional_confirmation_rows(
        args.data.resolve(),
        args.config.resolve(),
        args.base_profile.resolve(),
        args.conditional_profile.resolve(),
        args.confirmation_lock.resolve(),
        args.output.resolve(),
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
