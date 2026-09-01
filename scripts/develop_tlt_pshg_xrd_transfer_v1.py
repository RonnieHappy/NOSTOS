from __future__ import annotations

import argparse
from pathlib import Path

from nostos.validation.tlt_pshg_xrd_transfer import screen_clean_candidates, write_screen


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the development-only TLT pSHG-XRD clean candidate screen."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = screen_clean_candidates(args.dataset_root)
    write_screen(result, args.output)
    selected = result["selected_candidate"]
    print(
        "development fields={fields} transform={transform} scale_um={scale_um} "
        "offset={reference_offset_degrees} median_field_error={median_field_median_error_degrees:.3f}".format(
            **selected
        )
    )


if __name__ == "__main__":
    main()
