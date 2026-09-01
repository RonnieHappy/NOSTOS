from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_program_final_audit import build_fmd_program_final_audit
from nostos.validation.validity_profile_compiler import sha256_file, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the terminal FMD program audit.")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite FMD final audit: {output}")
    payload, markdown = build_fmd_program_final_audit(args.project_root.resolve())
    output.mkdir(parents=True)
    json_path = output / "final_audit.json"
    markdown_path = output / "FINAL_AUDIT.md"
    write_json(json_path, payload)
    markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "checks_passed": sum(payload["checks"].values()),
                "checks_total": len(payload["checks"]),
                "json": str(json_path),
                "json_sha256": sha256_file(json_path),
                "markdown": str(markdown_path),
                "markdown_sha256": sha256_file(markdown_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
