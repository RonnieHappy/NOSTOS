from __future__ import annotations

import argparse
from pathlib import Path

from nostos.validation.tlt_pshg_xrd_audit import audit_confirmation


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the locked TLT pSHG-XRD confirmation.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_confirmation(
        args.project_root, args.dataset_root, args.lock, args.result_root, args.output
    )
    print(
        f"status={result['status']} checks={result['verified_checks']}/{result['total_checks']}"
    )


if __name__ == "__main__":
    main()

