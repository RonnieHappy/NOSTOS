from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.conditional_support_profile import (
    audit_conditional_support_profile,
)
from nostos.validation.validity_profile_compiler import (
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit untouched confirmation rows with the frozen v1.4 support overlay."
    )
    parser.add_argument("confirmation_rows", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base-profile", type=Path, required=True)
    parser.add_argument("--conditional-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite v1.4 confirmation audit: {output}")
    rows_path = args.confirmation_rows.resolve()
    config = json.loads(args.config.resolve().read_text(encoding="utf-8"))
    base = json.loads(args.base_profile.resolve().read_text(encoding="utf-8"))
    conditional = json.loads(
        args.conditional_profile.resolve().read_text(encoding="utf-8")
    )
    rows = read_jsonl(rows_path)
    audit, scored = audit_conditional_support_profile(
        rows,
        config=config,
        base_profile=base,
        conditional_profile=conditional,
        source_receipt={
            "name": rows_path.name,
            "bytes": rows_path.stat().st_size,
            "sha256": sha256_file(rows_path),
        },
    )
    output.mkdir(parents=True)
    audit_path = output / "confirmation_audit.json"
    scored_path = output / "confirmation_scored.jsonl"
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "confirmation_audit": str(audit_path),
                "confirmation_audit_sha256": sha256_file(audit_path),
                "confirmation_scored": str(scored_path),
                "checks": audit["checks"],
                "primary_operating_point": audit["primary_operating_point"],
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
