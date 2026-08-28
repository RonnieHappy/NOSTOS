from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.final_audit import build_final_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the terminal NOSTOS-0 audit.")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("outputs/nostos0-final-max-audit-v1/final_audit.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("docs/NOSTOS0_FINAL_MAX_AUDIT.md"),
    )
    args = parser.parse_args()
    result = build_final_audit(
        args.project_root, args.json_output, args.markdown_output
    )
    print(json.dumps(result["terminal_verdict"], indent=2))
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

