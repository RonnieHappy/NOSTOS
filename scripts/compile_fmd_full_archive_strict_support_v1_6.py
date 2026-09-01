from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_full_archive_strict_profile import write_strict_profile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile the post-v1.5 FMD full-archive strict support profile."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    result = write_strict_profile(
        project_root, args.config.resolve(), args.output.resolve()
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
