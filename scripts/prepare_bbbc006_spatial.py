"""Hash-select and extract the frozen BBBC006 spatial confirmation subset."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


ARCHIVES = {
    "z00": ("BBBC006_v1_images_z_00.zip", "ca6a7c023fd3258c0175ec74fe4568203fc158c5022b765e07d0b202ab5c19bc"),
    "z15": ("BBBC006_v1_images_z_15.zip", "bf17883413e4625b942753773db53b8f30b94c8177c978402f0e29e5aef44697"),
    "z16": ("BBBC006_v1_images_z_16.zip", "6e1515d08f6365c075e4ce813d7d1670e620b51d5b87339c7f02d9fa56313d0e"),
}


def run(root: Path, output: Path, *, start: int = 0, count: int = 64) -> dict:
    def key(name: str) -> str:
        match = re.match(r"(.+_[a-p][0-9]{2}_s[12]_w1)", name, flags=re.IGNORECASE)
        if not match:
            raise ValueError(f"Unrecognized BBBC006 DAPI filename: {name}")
        return match.group(1).lower()

    with zipfile.ZipFile(root / ARCHIVES["z16"][0]) as archive:
        names = [Path(item.filename).name for item in archive.infolist() if item.filename.lower().endswith(".tif") and "_w1" in Path(item.filename).name]
    ordered = sorted((key(name) for name in names), key=lambda name: (hashlib.sha256(name.encode()).hexdigest(), name))
    selected = ordered[start:start + count]
    cases = []
    for plane, (archive_name, archive_hash) in ARCHIVES.items():
        destination = output / plane
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(root / archive_name) as archive:
            members = {key(Path(item.filename).name): item for item in archive.infolist() if item.filename.lower().endswith(".tif") and "_w1" in Path(item.filename).name}
            for case in selected:
                item = members[case]
                target = destination / f"{case}.tif"
                with archive.open(item) as source, target.open("wb") as sink:
                    while block := source.read(1024 * 1024):
                        sink.write(block)
                cases.append({"plane": plane, "case": case, "source_member": item.filename, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    payload = {
        "protocol_version": "nostos-bbbc006-spatial-selection/1.0",
        "selection": f"sha256_rank_{start + 1}_through_{start + len(selected)}_of_common_well_site_channel_identifier",
        "archive_sha256": {plane: value[1] for plane, value in ARCHIVES.items()},
        "selected_cases": selected, "files": cases,
    }
    (output / "selection_manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=64)
    args = parser.parse_args()
    result = run(args.root.resolve(), args.output.resolve(), start=args.start, count=args.count)
    print(json.dumps({"selected": len(result["selected_cases"]), "files": len(result["files"])}, indent=2))
