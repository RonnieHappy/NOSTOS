from __future__ import annotations

import argparse
from pathlib import Path

from nostos.validation.pshg_external_orientation import run_validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-offset-degrees", type=float, default=0.0)
    parser.add_argument("--protocol-version", default="nostos-pshg-external-orientation/1.0")
    parser.add_argument("--protocol-sha256", default=None)
    parser.add_argument("--bootstrap-seed", type=int, default=7242322)
    args = parser.parse_args()
    kwargs = {"reference_offset_degrees": args.reference_offset_degrees,
              "protocol_version": args.protocol_version, "bootstrap_seed": args.bootstrap_seed}
    if args.protocol_sha256:
        kwargs["protocol_sha256"] = args.protocol_sha256
    result = run_validation(args.dataset_root, args.output, **kwargs)
    print(result["status"])


if __name__ == "__main__":
    main()
