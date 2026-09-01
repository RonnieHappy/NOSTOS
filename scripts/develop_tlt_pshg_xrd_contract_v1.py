from __future__ import annotations

import argparse
from pathlib import Path

from nostos.validation.tlt_pshg_xrd_transfer import run_contract_development


def main() -> None:
    parser = argparse.ArgumentParser(description="Develop the sealed TLT pSHG-XRD contract.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prelock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_contract_development(
        args.dataset_root, args.config, args.prelock, args.output
    )
    development = result["development"]
    print(
        f"fields={development['fields']} cases={development['cases']} "
        f"invalid={development['invalid']} "
        f"clean_median_error={development['clean_median_field_error_degrees']:.3f}"
    )


if __name__ == "__main__":
    main()
