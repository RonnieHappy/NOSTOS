from __future__ import annotations

import argparse
from pathlib import Path

from nostos.validation.tlt_pshg_xrd_transfer import run_locked_confirmation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the locked TLT pSHG-XRD confirmation.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prelock", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_locked_confirmation(
        args.project_root,
        args.dataset_root,
        args.config,
        args.prelock,
        args.lock,
        args.output,
    )
    summary = result["summary"]
    print(
        f"status={result['status']} specimens={summary['specimens']} "
        f"fields={summary['fields']} cases={summary['cases']} "
        f"full_risk={summary['matched_coverage']['full_contract']['risk']:.4f} "
        f"organization_rho={summary['organization']['pooled_spearman']:.4f}"
    )


if __name__ == "__main__":
    main()
