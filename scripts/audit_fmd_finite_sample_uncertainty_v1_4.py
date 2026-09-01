from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.finite_sample_risk import audit_nested_zero_event_uncertainty
from nostos.validation.validity_profile_compiler import (
    read_jsonl,
    sha256_file,
    write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add nested-row and independent-FOV exact intervals to the v1.4 audit."
    )
    parser.add_argument("confirmation_audit", type=Path)
    parser.add_argument("confirmation_scored", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit_path = args.confirmation_audit.resolve()
    scored_path = args.confirmation_scored.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite finite-sample audit: {output_path}")
    source = json.loads(audit_path.read_text(encoding="utf-8"))
    rows = read_jsonl(scored_path)
    payload = audit_nested_zero_event_uncertainty(
        rows,
        predicted_risk_threshold=float(
            source["primary_operating_point"]["predicted_risk_threshold"]
        ),
        source_audit_file_sha256=sha256_file(audit_path),
        source_audit_content_sha256=str(source["content_sha256"]),
        scored_rows_file_sha256=sha256_file(scored_path),
    )
    write_json(output_path, payload)
    print(json.dumps(payload, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
