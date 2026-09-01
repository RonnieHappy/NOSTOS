from __future__ import annotations

import argparse
import json
from pathlib import Path

from nostos.validation.fmd_validity_profile import build_fmd_evidence_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build prospectively split FMD endpoint evidence for NOSTOS validity profiles."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/fmd_validity_profile_v1_1.locked.json"),
    )
    parser.add_argument("--split", choices=("development", "confirmation"), required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--confirmation-lock", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_fmd_evidence_rows(
        args.data.resolve(),
        args.config.resolve(),
        args.output.resolve(),
        split=args.split,
        profile_path=None if args.profile is None else args.profile.resolve(),
        confirmation_lock_path=(
            None if args.confirmation_lock is None else args.confirmation_lock.resolve()
        ),
    )
    print(json.dumps(payload, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
