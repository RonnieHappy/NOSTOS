"""Finalize a staged CurveAlign directory after declared parameter overrides."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PARAMETERS = ("CAP_cluster.txt", "CTFP_cluster.txt", "CAroiP_cluster.txt")
VENDOR_CAP_VALUES = ("0.06", "100")
LOCKED_CAP_VALUES = ("0.04", "50")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def finalize(stage: Path) -> dict[str, object]:
    receipt_path = stage / "stage_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    cap_path = stage / "CAP_cluster.txt"
    cap_text = cap_path.read_text(encoding="utf-8")
    cap_lines = cap_text.splitlines()
    if len(cap_lines) < 4:
        raise ValueError("CAP_cluster.txt is shorter than the official command-line schema.")
    observed = (cap_lines[2].strip(), cap_lines[3].strip())
    if observed == VENDOR_CAP_VALUES:
        cap_lines[2], cap_lines[3] = LOCKED_CAP_VALUES
        newline = "\r\n" if "\r\n" in cap_text else "\n"
        trailing = newline if cap_text.endswith(("\n", "\r")) else ""
        cap_path.write_text(newline.join(cap_lines) + trailing, encoding="utf-8", newline="")
        override_action = "vendor_example_overridden_by_lock"
    elif observed == LOCKED_CAP_VALUES:
        override_action = "preregistered_values_already_present"
    else:
        raise ValueError(
            "CAP_cluster.txt contains neither the byte-staged vendor example "
            "values 0.06/100 nor the preregistered values 0.04/50."
        )
    receipt["parameter_overrides"] = {
        "CAP_cluster.txt": {
            "line_3_fraction_of_coefficients_to_keep": {"vendor_example": 0.06, "locked": 0.04},
            "line_4_8bit_intensity_threshold": {"vendor_example": 100, "locked": 50},
            "source": "Heaton et al. DOI 10.1117/1.BIOS.1.1.015004",
            "action": override_action,
        },
        "CTFP_cluster.txt": "official packaged defaults retained",
        "CAroiP_cluster.txt": "official packaged defaults retained; ROI mode is not used",
    }
    receipt["locked_parameter_sha256"] = {
        name: sha256_file(stage / name) for name in PARAMETERS
    }
    experiment = receipt.get("experiment")
    if experiment in {None, "Exp10"}:
        receipt["status"] = "development_stage_parameters_locked"
    elif experiment == "Exp15":
        receipt["status"] = "confirmation_stage_parameters_locked"
    else:
        raise ValueError(f"Unsupported staged experiment: {experiment!r}")
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    receipt = finalize(args.stage.resolve())
    print(json.dumps({"status": receipt["status"], "fields": receipt["fields"]}, indent=2))


if __name__ == "__main__":
    main()
