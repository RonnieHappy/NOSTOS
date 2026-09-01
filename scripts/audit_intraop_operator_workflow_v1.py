"""Audit the frozen NOSTOS unstained-PSHG operator export without rewriting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import tifffile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(str(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _walk_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _walk_strings(child)]
    return []


def _same_float(observed: float, expected: float, *, atol: float = 1e-12) -> bool:
    return bool(np.isclose(float(observed), float(expected), rtol=0.0, atol=atol))


def audit(root: Path, dataset_root: Path, config_path: Path, output: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    lock_path = root / config["lock_path"]
    result_path = root / config["result_path"]
    lock_integrity = bool(
        lock_path.is_file()
        and lock_path.stat().st_size == int(config["lock_bytes"])
        and _sha256(lock_path) == config["lock_sha256"]
    )
    result_integrity = bool(
        result_path.is_file()
        and result_path.stat().st_size == int(config["result_bytes"])
        and _sha256(result_path) == config["result_sha256"]
    )
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))

    bad_locked_files: list[str] = []
    for item in lock["locked_files"]:
        path = root / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or _sha256(path) != item["sha256"]
        ):
            bad_locked_files.append(item["path"])

    source_group = str(config["source_group"])
    source_dir = dataset_root / source_group
    expected_sources = {
        Path(item["relative_path"]).name: item
        for item in lock["selected_source_files"]
        if Path(item["relative_path"]).parent.as_posix() == source_group
        and Path(item["relative_path"]).name.lower() != "fi.tif"
    }
    registered_sources = {item["name"]: item for item in result["source_files"]}
    bad_source_files: list[str] = []
    for name, expected in expected_sources.items():
        path = source_dir / name
        registered = registered_sources.get(name)
        if (
            not path.is_file()
            or path.stat().st_size != int(expected["bytes"])
            or _sha256(path) != expected["sha256"]
            or registered is None
            or int(registered["bytes"]) != int(expected["bytes"])
            or registered["sha256"] != expected["sha256"]
        ):
            bad_source_files.append(name)
    source_integrity = bool(
        not bad_source_files and set(registered_sources) == set(expected_sources)
    )

    frame_paths = [source_dir / f"{source_group}_FSHG_p{angle}.tif" for angle in range(0, 181, 20)]
    reconstructed_source = np.mean(
        [tifffile.imread(path).astype(np.float64) for path in frame_paths], axis=0
    )
    source_array_reconstruction = bool(
        _array_sha256(reconstructed_source) == result["input"]["source_array_sha256"]
    )

    artifact_dir = result_path.parent
    artifacts = result["artifacts"]
    artifact_paths = [str(item["path"]) for item in artifacts.values()]
    expected_artifacts = set(config["expected_artifacts"])
    existing_artifacts = {
        path.name for path in artifact_dir.iterdir()
        if path.is_file() and path.name not in {result_path.name, output.name}
    }
    artifact_registry_complete = bool(
        int(result["artifact_manifest"]["expected_count"]) == len(artifacts) == len(expected_artifacts)
        and result["artifact_manifest"]["unique_keys"] is True
        and result["artifact_manifest"]["unique_paths"] is True
        and len(artifact_paths) == len(set(artifact_paths))
        and set(artifact_paths) == expected_artifacts
        and existing_artifacts == expected_artifacts
    )
    bad_artifacts: list[str] = []
    for item in artifacts.values():
        path = artifact_dir / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or _sha256(path) != item["sha256"]
        ):
            bad_artifacts.append(str(item["path"]))
    artifact_file_integrity = not bad_artifacts

    orientation = np.load(artifact_dir / "orientation_degrees.npy", allow_pickle=False)
    coherence = np.load(artifact_dir / "coherence.npy", allow_pickle=False)
    eligible_u8 = np.load(artifact_dir / "eligible.npy", allow_pickle=False)
    eligible = eligible_u8.astype(bool)
    array_manifest_integrity = bool(
        orientation.dtype == np.float32
        and coherence.dtype == np.float32
        and eligible_u8.dtype == np.uint8
        and orientation.shape == coherence.shape == eligible.shape == tuple(result["input"]["shape"])
        and np.isfinite(orientation).all()
        and np.isfinite(coherence).all()
        # The frozen float32 serialization contract permits 180.0 as the
        # rounded representation of an axial direction infinitesimally below
        # 180 degrees; it is equivalent to 0 degrees on the axial circle.
        and np.all((orientation >= 0.0) & (orientation <= 180.0))
        and np.all((coherence >= 0.0) & (coherence <= 1.0))
        and set(np.unique(eligible_u8)).issubset({0, 1})
        and _array_sha256(orientation) == result["measurement"]["map_hashes"]["orientation_degrees"]
        and _array_sha256(coherence) == result["measurement"]["map_hashes"]["coherence"]
        and _array_sha256(eligible_u8) == result["measurement"]["map_hashes"]["eligible"]
    )
    summary = result["measurement"]["summary"]
    coherence_values = coherence[eligible]
    summary_reproduction = bool(
        int(eligible.sum()) == int(summary["eligible_pixels"])
        and _same_float(eligible.mean(), summary["eligible_fraction"])
        and _same_float(np.median(coherence_values), summary["median_coherence"], atol=5e-8)
        and _same_float(np.percentile(coherence_values, 10.0), summary["p10_coherence"], atol=5e-8)
        and _same_float(np.percentile(coherence_values, 90.0), summary["p90_coherence"], atol=5e-8)
    )

    provenance = result["operator_provenance"]
    public_provenance_verified = bool(
        provenance["status"] == "verified_public_bundle"
        and provenance["verified"] is True
        and provenance["matched_group"] == source_group
        and provenance["lock_file"] == lock_path.name
        and provenance["lock_sha256"] == config["lock_sha256"]
        and int(provenance["required_files"]) == len(expected_sources)
    )
    clinical = result["clinical_output"]
    clinical_output_withheld = bool(
        clinical["status"] == "withheld"
        and all(
            clinical[key] is None
            for key in ("diagnosis", "margin_or_boundary", "mechanical_property", "treatment_recommendation")
        )
    )
    reference_excluded = bool(
        result["reference_evaluation"] is None
        and "evaluation_reference_file" not in result
        and "FI.tif" not in registered_sources
    )
    path_leaks = sorted(
        {
            value
            for value in _walk_strings(result)
            if re.search(r"(?i)(?:[a-z]:[\\/]|(?:^|[\\s\"'])/(?:home|users|mnt|tmp)/)", value)
        }
    )

    checks = {
        "lock_integrity": lock_integrity,
        "locked_implementation_integrity": not bad_locked_files,
        "result_integrity": result_integrity,
        "source_integrity": source_integrity,
        "source_array_reconstruction": source_array_reconstruction,
        "artifact_registry_complete": artifact_registry_complete,
        "artifact_file_integrity": artifact_file_integrity,
        "array_manifest_integrity": array_manifest_integrity,
        "summary_reproduction": summary_reproduction,
        "public_provenance_verified": public_provenance_verified,
        "reference_excluded_from_deployment": reference_excluded,
        "clinical_output_withheld": clinical_output_withheld,
        "no_absolute_local_paths": not path_leaks,
    }
    payload = {
        "schema_version": "nostos-intraop-operator-workflow-final-audit/1.0",
        "target_schema": result["schema_version"],
        "status": "verified_pass" if all(checks.values()) else "audit_fail",
        "checks": checks,
        "observed": {
            "source_group": source_group,
            "source_files": len(registered_sources),
            "artifacts": len(artifacts),
            "eligible_pixels": int(eligible.sum()),
            "measurement_status": result["status"],
            "measurement_evidence": result["measurement"]["evidence_status"],
            "operator_provenance": provenance["status"],
            "clinical_output": clinical["status"],
            "reference_used": result["reference_evaluation"] is not None,
        },
        "bad_locked_files": bad_locked_files,
        "bad_source_files": bad_source_files,
        "bad_artifacts": bad_artifacts,
        "unregistered_artifacts": sorted(existing_artifacts - set(artifact_paths)),
        "missing_artifacts": sorted(expected_artifacts - existing_artifacts),
        "absolute_local_path_leaks": path_leaks,
        "claim_boundary": (
            "This audit verifies an operator export for one hash-identical public unstained-PSHG field. "
            "It does not validate a new microscope, operator, tissue, clinical endpoint, diagnosis, "
            "mechanical inference, margin assessment, treatment decision or patient outcome."
        ),
        "clinical_readiness": "not_ready",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/intraop_operator_workflow_v1_audit.locked.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/nostos0-intraop-operator-workflow-v1/workflow_audit.json"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    payload = audit(
        root,
        args.dataset_root.resolve(),
        (root / args.config).resolve(),
        (root / args.output).resolve(),
    )
    print(json.dumps({"status": payload["status"], "checks": payload["checks"]}, indent=2))
    if payload["status"] != "verified_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
