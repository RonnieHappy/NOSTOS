from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_validity_profile import (
    attach_declared_capture_stability_score,
)
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Attach the frozen v1.2 input-only FMD score to retained development rows."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    input_path = args.input.resolve()
    config_path = args.config.resolve()
    output_directory = args.output.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected = str(config["supersedes"]["development_rows_sha256"])
    observed = sha256_file(input_path)
    if observed != expected:
        raise ValueError("Development rows differ from the v1.2 repair lock.")
    rows = read_jsonl(input_path)
    for row in rows:
        attach_declared_capture_stability_score(row, config=config)
    output_directory.mkdir(parents=True, exist_ok=True)
    rows_path = output_directory / "development_rows_v1_2.jsonl"
    write_jsonl(rows_path, rows)
    receipt = {
        "schema_version": "nostos-fmd-input-only-rescore/1.0",
        "status": "complete",
        "protocol_id": config["protocol_id"],
        "input_rows_name": input_path.name,
        "input_rows_sha256": observed,
        "output_rows_name": rows_path.name,
        "output_rows_sha256": sha256_file(rows_path),
        "config_file_sha256": sha256_file(config_path),
        "config_content_sha256": canonical_sha256(config),
        "rows": len(rows),
        "score_key": config["measurement"]["input_only_score"]["score_key"],
        "reference_label_access": "The scoring function reads only metadata.averaged_captures and support_components.perturbation_stability.",
    }
    receipt["content_sha256"] = canonical_sha256(receipt)
    receipt_path = output_directory / "rescore_receipt.json"
    write_json(receipt_path, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "rows": receipt["rows"],
                "output": str(rows_path),
                "output_rows_sha256": receipt["output_rows_sha256"],
                "receipt": str(receipt_path),
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
