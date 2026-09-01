from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

from nostos.intraop.label_free import (
    analyze_pshg_directory,
    analyze_unstained_field,
    load_intraop_profile,
    load_pshg_directory,
)
from nostos.validation.local_orientation import _tensor_fields


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _axial_errors(measured: np.ndarray, reference: np.ndarray) -> np.ndarray:
    difference = np.abs(measured - reference) % 180.0
    return np.minimum(difference, 180.0 - difference)


def _verify_lock(root: Path, lock: dict, dataset_root: Path) -> dict:
    verified_files = []
    for item in lock["locked_files"]:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != int(item["bytes"]) or _sha256(path) != item["sha256"]:
            raise ValueError(f"Locked artifact verification failed: {item['path']}")
        verified_files.append(item["path"])
    verified_sources = []
    for item in lock["selected_source_files"]:
        path = dataset_root / item["relative_path"]
        if not path.is_file() or path.stat().st_size != int(item["bytes"]) or _sha256(path) != item["sha256"]:
            raise ValueError(f"Selected public source verification failed: {item['relative_path']}")
        verified_sources.append(item["relative_path"])
    return {
        "locked_files_verified": len(verified_files),
        "selected_source_files_verified": len(verified_sources),
    }


def run_benchmark(
    project_root: Path,
    dataset_root: Path,
    output: Path,
    *,
    config_path: Path,
    lock_path: Path,
) -> dict:
    root = project_root.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("status") != "locked_before_selected_pixel_decode":
        raise ValueError("The deployment benchmark lock is not in the required state.")
    verification = _verify_lock(root, lock, dataset_root)
    profile_path = root / config["profile_path"]
    profile = load_intraop_profile(profile_path)
    selected = list(config["selection"]["selected_rois"])
    gates = config["gates"]
    output.mkdir(parents=True, exist_ok=True)

    cases = []
    pooled_errors = []
    for roi in selected:
        directory = dataset_root / roi
        receipt = analyze_pshg_directory(
            directory,
            output / "cases" / roi,
            profile_path=profile_path,
            pixel_size_um=1.0,
            include_reference_evaluation=True,
        )
        loaded = load_pshg_directory(directory)
        mean_image = np.mean(loaded["frames"], axis=0)
        repeated = analyze_unstained_field(
            mean_image,
            pixel_size_um=1.0,
            modality=profile["modality"],
            profile=profile,
            verified_stack_frame_count=10,
            r2_map=loaded["r2"],
            snr_map=loaded["snr"],
        )
        production_orientation = np.load(output / "cases" / roi / "orientation_degrees.npy", allow_pickle=False)
        production_coherence = np.load(output / "cases" / roi / "coherence.npy", allow_pickle=False)
        production_eligible = np.load(output / "cases" / roi / "eligible.npy", allow_pickle=False).astype(bool)
        validation_orientation, validation_coherence, _ = _tensor_fields(mean_image, scales=(2.0,))
        map_difference = _axial_errors(
            production_orientation.astype(float), validation_orientation[0]
        )
        coherence_difference = np.abs(production_coherence.astype(float) - validation_coherence[0])
        reference = np.mod(loaded["fi"] + 90.0, 180.0)
        errors = _axial_errors(production_orientation[production_eligible], reference[production_eligible])
        pooled_errors.append(errors)
        deterministic = (
            receipt["measurement"]["map_hashes"]
            == repeated.payload["measurement"]["map_hashes"]
        )
        cases.append(
            {
                "roi": roi,
                "status": receipt["status"],
                "evidence_status": receipt["measurement"]["evidence_status"],
                "eligible_pixels": int(errors.size),
                "median_reference_error_degrees": float(np.median(errors)),
                "p75_reference_error_degrees": float(np.percentile(errors, 75.0)),
                "maximum_production_validation_orientation_difference_degrees": float(np.max(map_difference)),
                "maximum_production_validation_coherence_difference": float(np.max(coherence_difference)),
                "deterministic_map_hashes": deterministic,
                "clinical_decision": receipt["clinical_output"]["status"],
                "runtime": receipt["runtime"],
            }
        )

    all_errors = np.concatenate(pooled_errors)
    analysis_times = np.asarray([row["runtime"]["analysis_seconds"] for row in cases], dtype=float)
    total_times = np.asarray([row["runtime"]["end_to_end_seconds"] for row in cases], dtype=float)
    peak_memory = np.asarray([row["runtime"]["peak_python_memory_mb"] for row in cases], dtype=float)
    checks = {
        "completed_rois": len(cases) == int(gates["required_completed_rois"]),
        "production_validation_equivalence": max(
            row["maximum_production_validation_orientation_difference_degrees"] for row in cases
        ) <= float(gates["maximum_production_validation_map_difference_degrees"]),
        "pooled_reference_error": float(np.median(all_errors))
        <= float(gates["maximum_pooled_median_reference_error_degrees"]),
        "worst_roi_reference_error": max(row["median_reference_error_degrees"] for row in cases)
        <= float(gates["maximum_worst_roi_median_reference_error_degrees"]),
        "analysis_latency": float(np.percentile(analysis_times, 95.0))
        <= float(gates["maximum_p95_analysis_seconds"]),
        "end_to_end_latency": float(np.percentile(total_times, 95.0))
        <= float(gates["maximum_p95_end_to_end_seconds"]),
        "peak_python_memory": float(np.max(peak_memory))
        <= float(gates["maximum_peak_python_memory_mb"]),
        "deterministic_map_hashes": all(row["deterministic_map_hashes"] for row in cases),
        "profile_and_source_hashes": (
            verification["locked_files_verified"] == len(lock["locked_files"])
            and verification["selected_source_files_verified"] == len(lock["selected_source_files"])
        ),
        "technical_endpoint_promoted_only_in_scope": all(
            row["status"] == "valid" and row["evidence_status"] == "confirmed" for row in cases
        ),
        "clinical_decision_withheld": all(row["clinical_decision"] == "withheld" for row in cases),
    }
    payload = {
        "protocol_version": config["protocol_version"],
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "selection": config["selection"],
        "verification": verification,
        "summary": {
            "rois": len(cases),
            "eligible_pixels": int(all_errors.size),
            "pooled_median_reference_error_degrees": float(np.median(all_errors)),
            "pooled_p75_reference_error_degrees": float(np.percentile(all_errors, 75.0)),
            "worst_roi_median_reference_error_degrees": max(row["median_reference_error_degrees"] for row in cases),
            "p95_analysis_seconds": float(np.percentile(analysis_times, 95.0)),
            "p95_end_to_end_seconds": float(np.percentile(total_times, 95.0)),
            "maximum_peak_python_memory_mb": float(np.max(peak_memory)),
            "maximum_production_validation_orientation_difference_degrees": max(
                row["maximum_production_validation_orientation_difference_degrees"] for row in cases
            ),
            "all_map_hashes_deterministic": all(row["deterministic_map_hashes"] for row in cases),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "author_operated": True,
            "acquisition_time_measured": False,
        },
        "lock": {
            "path": lock_path.relative_to(root).as_posix(),
            "sha256": _sha256(lock_path),
        },
        "config": {
            "path": config_path.relative_to(root).as_posix(),
            "sha256": _sha256(config_path),
        },
        "cases": cases,
        "claim_boundary": config["claim_boundary"],
        "clinical_readiness": "not_ready",
    }
    (output / "deployment_benchmark.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/intraop_pshg_deployment_benchmark_v1.locked.json"),
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("manifests/intraop_pshg_deployment_v1_lock.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/nostos0-intraop-pshg-deployment-v1"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = run_benchmark(
        root,
        args.dataset_root.resolve(),
        args.output.resolve(),
        config_path=(root / args.config).resolve(),
        lock_path=(root / args.lock).resolve(),
    )
    print(json.dumps({"status": result["status"], **result["summary"]}, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

