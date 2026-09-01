from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LOCKED_PATHS = (
    "configs/intraop_pshg_orientation_profile_v1.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1_1.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1_2.locked.json",
    "configs/intraop_pshg_deployment_benchmark_v1_3.locked.json",
    "manifests/intraop_pshg_deployment_v1_lock.json",
    "manifests/intraop_pshg_deployment_v1_1_lock.json",
    "manifests/intraop_pshg_deployment_v1_2_lock.json",
    "outputs/nostos0-intraop-pshg-deployment-v1/failure_receipt.json",
    "outputs/nostos0-intraop-pshg-deployment-v1_1/failure_receipt.json",
    "outputs/nostos0-intraop-pshg-deployment-v1_2/deployment_benchmark.json",
    "outputs/nostos0-intraop-pshg-deployment-v1_2/failure_receipt.json",
    "outputs/nostos0-pshg-breast-orientation-v1/pshg_external_orientation.json",
    "src/nostos/intraop/label_free.py",
    "src/nostos/intraop/label_free_v1_1.py",
    "src/nostos/intraop/label_free_v1_2.py",
    "src/nostos/intraop/label_free_v1_3.py",
    "src/nostos/intraop/support_qc.py",
    "scripts/run_intraop_pshg_deployment_benchmark.py",
    "scripts/run_intraop_pshg_deployment_benchmark_v1_1.py",
    "scripts/run_intraop_pshg_deployment_benchmark_v1_2.py",
    "scripts/run_intraop_pshg_deployment_benchmark_v1_3.py",
    "scripts/build_intraop_pshg_deployment_v1_1_lock.py",
    "scripts/build_intraop_pshg_deployment_v1_2_lock.py",
    "scripts/build_intraop_pshg_deployment_v1_3_lock.py",
    "tests/test_intraop_label_free.py",
    "tests/test_intraop_label_free_v1_1.py",
    "tests/test_intraop_label_free_v1_2.py",
    "tests/test_intraop_label_free_v1_3.py",
    "tests/test_intraop_support_qc.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_lineage(root: Path, config: dict) -> dict:
    observed = {}
    for stem in ("v1_2_lock", "v1_2_result", "v1_2_failure"):
        path = root / config["lineage"][f"{stem}_path"]
        expected_bytes = int(config["lineage"][f"{stem}_bytes"])
        expected_hash = config["lineage"][f"{stem}_sha256"]
        if path.stat().st_size != expected_bytes or _sha256(path) != expected_hash:
            raise ValueError(f"The {stem} artifact does not match the amendment lineage.")
        observed[stem] = {"path": path.relative_to(root).as_posix(), "bytes": expected_bytes, "sha256": expected_hash}
    return observed


def _selection(config: dict, dataset_root: Path, prior_rois: set[str]) -> list[str]:
    salt = config["selection"]["salt"]
    candidates = [
        path.name
        for path in dataset_root.glob("breast_*")
        if path.is_dir() and path.name not in prior_rois
    ]
    ranked = sorted(candidates, key=lambda name: hashlib.sha256(f"{salt}|{name}".encode()).hexdigest())
    selected = ranked[: int(config["gates"]["required_completed_rois"])]
    if selected != list(config["selection"]["selected_rois"]):
        raise ValueError("The v1.3 field selection does not reproduce from the locked rule.")
    digests = [hashlib.sha256(f"{salt}|{name}".encode()).hexdigest() for name in selected]
    if digests != list(config["selection"]["selection_sha256"]):
        raise ValueError("The v1.3 field-selection digests do not match.")
    return selected


def _source_files(dataset_root: Path, selected: list[str]) -> list[dict]:
    records = []
    for roi in selected:
        directory = dataset_root / roi
        expected = [directory / "FI.tif", directory / "R2.tif", directory / "SNR.tif"]
        expected.extend(sorted(directory.glob(f"{roi}_FSHG_p*.tif")))
        if len(expected) != 13 or any(not path.is_file() for path in expected):
            raise ValueError(f"{roi} does not contain the required 13-file acquisition bundle.")
        for path in expected:
            records.append(
                {
                    "relative_path": path.relative_to(dataset_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    return records


def build_lock(root: Path, dataset_root: Path, output: Path) -> dict:
    config_path = root / "configs/intraop_pshg_deployment_benchmark_v1_3.locked.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    lineage = _verify_lineage(root, config)
    prior_lock = json.loads((root / config["lineage"]["v1_2_lock_path"]).read_text(encoding="utf-8"))
    selected = _selection(config, dataset_root, set(prior_lock["selection"]["selected_rois"]))
    manifest_path = dataset_root / config["dataset"]["manifest_relative_path"]
    if _sha256(manifest_path) != prior_lock["dataset_manifest"]["sha256"]:
        raise ValueError("The public download manifest changed after the v1.2 lock.")
    locked_files = []
    for relative in LOCKED_PATHS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        locked_files.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    payload = {
        "schema_version": "nostos-intraop-pshg-deployment-lock/1.3",
        "status": "locked_before_v1_3_pixel_decode",
        "protocol_version": config["protocol_version"],
        "selection": config["selection"],
        "amendment": config["amendment"],
        "serialization_contract": config["serialization_contract"],
        "lineage": lineage,
        "dataset_manifest": {**prior_lock["dataset_manifest"], "sha256": _sha256(manifest_path)},
        "locked_files": locked_files,
        "selected_source_files": _source_files(dataset_root, selected),
        "access_state": "V1.3 code, gates, selection and source hashes were frozen before selected v1.3 pixel arrays or FI reference values were decoded by the deployment benchmark.",
        "claim_boundary": config["claim_boundary"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("manifests/intraop_pshg_deployment_v1_3_lock.json"))
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = build_lock(root, args.dataset_root.resolve(), (root / args.output).resolve())
    print(json.dumps({"status": result["status"], "files": len(result["locked_files"]), "source_files": len(result["selected_source_files"])}, indent=2))


if __name__ == "__main__":
    main()
