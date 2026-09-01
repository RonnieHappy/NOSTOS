from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LOCKED_PATHS = (
    "configs/intraop_pshg_orientation_profile_v1.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1_1.locked.json",
    "manifests/intraop_pshg_deployment_v1_lock.json",
    "outputs/nostos0-intraop-pshg-deployment-v1/failure_receipt.json",
    "outputs/nostos0-pshg-breast-orientation-v1/pshg_external_orientation.json",
    "src/nostos/intraop/label_free.py",
    "src/nostos/intraop/label_free_v1_1.py",
    "scripts/run_intraop_pshg_deployment_benchmark.py",
    "scripts/run_intraop_pshg_deployment_benchmark_v1_1.py",
    "scripts/build_intraop_pshg_deployment_v1_1_lock.py",
    "tests/test_intraop_label_free.py",
    "tests/test_intraop_label_free_v1_1.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_lock(root: Path, dataset_root: Path, output: Path) -> dict:
    config_path = root / "configs/intraop_pshg_deployment_benchmark_v1_1.locked.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    v1_lock_path = root / config["lineage"]["v1_lock_path"]
    if _sha256(v1_lock_path) != config["lineage"]["v1_lock_sha256"]:
        raise ValueError("The v1 lock does not match the amendment lineage.")
    failure_path = root / config["lineage"]["v1_failure_path"]
    if (
        failure_path.stat().st_size != int(config["lineage"]["v1_failure_bytes"])
        or _sha256(failure_path) != config["lineage"]["v1_failure_sha256"]
    ):
        raise ValueError("The v1 failure receipt does not match the amendment lineage.")
    v1_lock = json.loads(v1_lock_path.read_text(encoding="utf-8"))
    if list(v1_lock["selection"]["selected_rois"]) != list(config["selection"]["selected_rois"]):
        raise ValueError("The v1.1 amendment changed the locked ROI selection.")
    manifest_path = dataset_root / config["dataset"]["manifest_relative_path"]
    manifest_sha256 = _sha256(manifest_path)
    if manifest_sha256 != v1_lock["dataset_manifest"]["sha256"]:
        raise ValueError("The public download manifest changed after the v1 lock.")
    locked_files = []
    for relative in LOCKED_PATHS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        locked_files.append(
            {"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        )
    payload = {
        "schema_version": "nostos-intraop-pshg-deployment-lock/1.1",
        "status": "locked_before_reference_error_evaluation",
        "protocol_version": config["protocol_version"],
        "selection": config["selection"],
        "amendment": config["amendment"],
        "lineage": config["lineage"],
        "dataset_manifest": {
            **v1_lock["dataset_manifest"],
            "sha256": manifest_sha256,
        },
        "locked_files": locked_files,
        "selected_source_files": v1_lock["selected_source_files"],
        "access_state": "The v1 run decoded the first selected ROI but stopped before reference-error computation. V1.1 is frozen before any reference error or success gate is computed.",
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
        default=Path("manifests/intraop_pshg_deployment_v1_1_lock.json"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = build_lock(root, args.dataset_root.resolve(), (root / args.output).resolve())
    print(json.dumps({"status": result["status"], "files": len(result["locked_files"]), "source_files": len(result["selected_source_files"])}, indent=2))


if __name__ == "__main__":
    main()

