from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LOCKED_PATHS = (
    "configs/intraop_pshg_orientation_profile_v1.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1.locked.json",
    "src/nostos/intraop/__init__.py",
    "src/nostos/intraop/label_free.py",
    "scripts/run_intraop_pshg_deployment_benchmark.py",
    "scripts/build_intraop_pshg_deployment_lock.py",
    "tests/test_intraop_label_free.py",
    "outputs/nostos0-pshg-breast-orientation-v1/pshg_external_orientation.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rank(salt: str, value: str) -> str:
    return hashlib.sha256(f"{salt}|{value}".encode("utf-8")).hexdigest()


def build_lock(root: Path, dataset_root: Path, output: Path) -> dict:
    config_path = root / "configs/intraop_pshg_deployment_benchmark_v1.locked.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    manifest_path = dataset_root / config["dataset"]["manifest_relative_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    all_rois = sorted(path.name for path in dataset_root.iterdir() if path.is_dir())
    salt = config["selection"]["salt"]
    expected = sorted(all_rois, key=lambda name: _rank(salt, name))[:8]
    selected = list(config["selection"]["selected_rois"])
    if selected != expected:
        raise ValueError(f"Frozen ROI selection does not match the declared rule: {selected} != {expected}")
    entries = {
        (str(item["roi"]), str(item["name"])): item for item in manifest["files"]
    }
    selected_source_files = []
    for roi in selected:
        expected_names = ["FI.tif", "R2.tif", "SNR.tif"] + [
            f"{roi}_FSHG_p{angle}.tif" for angle in range(0, 181, 20)
        ]
        for name in expected_names:
            item = entries.get((roi, name))
            if item is None:
                raise ValueError(f"Manifest does not contain {roi}/{name}")
            selected_source_files.append(
                {
                    "relative_path": f"{roi}/{name}",
                    "bytes": int(item["bytes"]),
                    "sha256": str(item["sha256"]),
                }
            )
    locked_files = []
    for relative in LOCKED_PATHS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        locked_files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    payload = {
        "schema_version": "nostos-intraop-pshg-deployment-lock/1.0",
        "status": "locked_before_selected_pixel_decode",
        "protocol_version": config["protocol_version"],
        "selection": config["selection"],
        "dataset_manifest": {
            "relative_path": config["dataset"]["manifest_relative_path"],
            "bytes": manifest_path.stat().st_size,
            "sha256": _sha256(manifest_path),
            "doi": manifest.get("doi"),
            "subset": manifest.get("subset"),
        },
        "locked_files": locked_files,
        "selected_source_files": selected_source_files,
        "access_state": "Only directory names and the existing download manifest were read while constructing this deployment lock; selected pixel arrays are decoded only by the locked runner.",
        "claim_boundary": config["claim_boundary"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manifests/intraop_pshg_deployment_v1_lock.json"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = build_lock(root, args.dataset_root.resolve(), (root / args.output).resolve())
    print(json.dumps({"status": result["status"], "files": len(result["locked_files"]), "source_files": len(result["selected_source_files"])}, indent=2))


if __name__ == "__main__":
    main()

