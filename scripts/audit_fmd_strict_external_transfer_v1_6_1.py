from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_strict_external_transfer_audit_v1_6_1 import (
    run_transfer_audit_v1_6_1,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the v1.6.1 audit-only zero-coverage repair on locked FMD transfer rows."
    )
    parser.add_argument("rows", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_transfer_audit_v1_6_1(
        args.rows.resolve(), args.config.resolve(), args.output.resolve()
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

