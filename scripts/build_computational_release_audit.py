from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.computational_release_audit import (
    build_computational_release_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the post-release, computation-only NOSTOS-0 audit."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(
            "outputs/nostos0-computational-release-audit-v1/final_audit.json"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("docs/NOSTOS0_FINAL_COMPUTATIONAL_METHODS_AUDIT_V4.md"),
    )
    args = parser.parse_args()
    result = build_computational_release_audit(
        args.project_root,
        args.json_output,
        args.markdown_output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "failed_checks": result["failed_checks"],
                "release_identity": result["release_identity"],
            },
            indent=2,
        )
    )
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

