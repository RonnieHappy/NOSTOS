"""Execute the frozen four-domain public tool workflow study."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import tifffile
from scipy.ndimage import shift

from nostos.app.measure import measure_file
from nostos.features.dynamic import analyze_time_series


PROTOCOL = "nostos-public-tool-workflows/1.0"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(output: Path, *, bbbc007: Path, hrf_image: Path, hrf_mask: Path, bone: Path, bbbc035: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    workflows = []

    def measured(name: str, image: Path, spacing: str, unit: str, mask: Path | None = None) -> None:
        started = time.perf_counter()
        summary = measure_file(image, output / name, spacing=spacing, spatial_unit=unit, mask_path=mask)
        elapsed = time.perf_counter() - started
        payload = json.loads(Path(summary["output"]).read_text(encoding="utf-8"))
        workflows.append({"name": name, "elapsed_seconds": elapsed, "summary": summary, "payload": payload, "source_sha256": _hash(image), "mask_sha256": None if mask is None else _hash(mask)})

    measured("unmasked_2d_bbbc007", bbbc007, "1", "relative")
    measured("masked_2d_hrf", hrf_image, "1", "relative", hrf_mask)
    nii = nib.load(str(bone))
    spacing = ",".join(str(float(value)) for value in nii.header.get_zooms()[:3])
    measured("masked_3d_bone", bone, spacing, "mm", bone)

    volume = tifffile.imread(bbbc035).astype(float)
    projection = volume.max(axis=0)
    series = np.stack([projection, shift(projection, (3, -5), order=0, mode="wrap")])
    started = time.perf_counter()
    dynamic = analyze_time_series(series, spacing=(0.1267, 0.1267), temporal_spacing=29.0, temporal_unit="min")
    elapsed = time.perf_counter() - started
    dynamic_payload = dynamic.to_dict()
    dynamic_path = output / "dynamic_2dt_bbbc035" / "dynamic_response_geometry.json"
    dynamic_path.parent.mkdir(parents=True, exist_ok=True)
    dynamic_path.write_text(json.dumps(dynamic_payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    workflows.append({"name": "dynamic_2dt_bbbc035", "elapsed_seconds": elapsed, "summary": {"output": str(dynamic_path), "modules": sorted({item["module"] for item in dynamic_payload["responses"]})}, "payload": dynamic_payload, "source_sha256": _hash(bbbc035), "mask_sha256": None})

    by_name = {item["name"]: item for item in workflows}
    def modules(name: str) -> set[str]:
        return {item["module"] for item in by_name[name]["payload"]["responses"]}
    schema_valid = all(item["payload"].get("schema_version") == "nostos-response-geometry/1.0" and item["payload"].get("input_dimensions") and item["payload"].get("calibration") and item["payload"].get("provenance") and (item["payload"].get("responses") or item["payload"].get("abstentions")) for item in workflows)
    unmasked_abstentions = {item["requested_measurement"] for item in by_name["unmasked_2d_bbbc007"]["payload"]["abstentions"]}
    network_names = {item["measurement"] for item in by_name["masked_2d_hrf"]["payload"]["responses"] if item["module"] == "network"}
    gates = {
        "all_four_workflows_complete": len(workflows) == 4,
        "all_schema_contracts_valid": schema_valid,
        "unmasked_2d_modules_and_abstention_correct": {"spectral", "tensor", "hessian", "spatial"}.issubset(modules("unmasked_2d_bbbc007")) and "geometry/network" in unmasked_abstentions,
        "masked_2d_geometry_and_network_v2_present": {"geometry", "network"}.issubset(modules("masked_2d_hrf")) and "surviving_fraction_boundary_v2" in network_names,
        "masked_3d_module_contract_correct": {"hessian", "geometry", "network"}.issubset(modules("masked_3d_bone")) and not ({"spectral", "spatial"} & modules("masked_3d_bone")),
        "dynamic_time_contract_correct": modules("dynamic_2dt_bbbc035") == {"dynamic"} and by_name["dynamic_2dt_bbbc035"]["payload"]["calibration"]["temporal_unit"] == "min",
        "every_workflow_under_60_seconds": max(item["elapsed_seconds"] for item in workflows) <= 60.0,
    }
    compact = [{key: value for key, value in item.items() if key != "payload"} | {"status": item["payload"]["status"], "modules": sorted(modules(item["name"]))} for item in workflows]
    receipt = {
        "protocol_version": PROTOCOL, "protocol_sha256": hashlib.sha256(PROTOCOL.encode()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail", "gates": gates, "workflows": compact,
        "interpretation": "End-to-end public-data software execution; not independent usability or clinical validation.",
    }
    (output / "public_tool_workflows.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bbbc007", type=Path, required=True)
    parser.add_argument("--hrf-image", type=Path, required=True)
    parser.add_argument("--hrf-mask", type=Path, required=True)
    parser.add_argument("--bone", type=Path, required=True)
    parser.add_argument("--bbbc035", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), bbbc007=args.bbbc007.resolve(), hrf_image=args.hrf_image.resolve(), hrf_mask=args.hrf_mask.resolve(), bone=args.bone.resolve(), bbbc035=args.bbbc035.resolve())
    print(json.dumps(result, indent=2))
