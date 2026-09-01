from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.bone_program_summary import build_bone_program_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/nostos0-bone-contract-summary"),
    )
    args = parser.parse_args()
    result = build_bone_program_summary(args.project_root, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
