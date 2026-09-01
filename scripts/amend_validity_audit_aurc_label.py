from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.reporting_amendment import (
    amend_primary_candidate_aurc_label,
)
from nostos.validation.validity_profile_compiler import sha256_file, write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Issue a reporting-only amendment for the legacy AURC label."
    )
    parser.add_argument("source_audit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_path = args.source_audit.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite reporting amendment: {output_path}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    amended = amend_primary_candidate_aurc_label(
        source,
        source_file_sha256=sha256_file(source_path),
    )
    write_json(output_path, amended)
    print(
        json.dumps(
            {
                "status": "reporting_only_amendment_written",
                "source": str(source_path),
                "output": str(output_path),
                "content_sha256": amended["content_sha256"],
                "statistical_values_recomputed": False,
                "gate_decisions_changed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
