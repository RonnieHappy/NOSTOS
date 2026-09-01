"""Convert the frozen public bone masks into calibrated ImageJ TIFF stacks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import tifffile


def run(data: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for source in sorted(data.glob("*_SEG_SUB.nii")):
        nii = nib.load(str(source))
        mask = np.asanyarray(nii.dataobj) > 0
        spacing = tuple(float(v) for v in nii.header.get_zooms()[:3])
        isotropic = float(np.mean(spacing))
        relative_deviation = float(max(abs(value - isotropic) for value in spacing) / isotropic)
        destination = output / f"{source.name.removesuffix('_SEG_SUB.nii')}.tif"
        # NIfTI x,y,z is transposed to ImageJ z,y,x.
        stack = np.transpose(mask, (2, 1, 0)).astype(np.uint8) * 255
        tifffile.imwrite(
            destination, stack, imagej=True, resolution=(1.0 / isotropic, 1.0 / isotropic),
            metadata={"spacing": isotropic, "unit": "mm", "axes": "ZYX"},
        )
        cases.append({
            "case": source.name.removesuffix("_SEG_SUB.nii"), "source": source.name,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "tiff": destination.name, "tiff_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "shape_zyx": list(stack.shape), "spacing_xyz_mm": list(spacing),
            "assigned_isotropic_spacing_mm": isotropic, "maximum_relative_axis_deviation": relative_deviation,
        })
    payload = {"protocol_version": "nostos-bonej-inputs/1.0", "case_count": len(cases), "cases": cases}
    (output / "bonej_input_manifest.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.data.resolve(), args.output.resolve()), indent=2))
