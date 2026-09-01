from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile

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


def audit(root: Path, dataset_root: Path, config_path: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    lock_path = root / config["lock_path"]
    result_path = root / config["result_path"]
    lock_integrity = (
        lock_path.stat().st_size == int(config["lock_bytes"])
        and _sha256(lock_path) == config["lock_sha256"]
    )
    result_integrity = (
        result_path.stat().st_size == int(config["result_bytes"])
        and _sha256(result_path) == config["result_sha256"]
    )
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))

    bad_locked = []
    for item in lock["locked_files"]:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != int(item["bytes"]) or _sha256(path) != item["sha256"]:
            bad_locked.append(item["path"])
    bad_sources = []
    for item in lock["selected_source_files"]:
        path = dataset_root / item["relative_path"]
        if not path.is_file() or path.stat().st_size != int(item["bytes"]) or _sha256(path) != item["sha256"]:
            bad_sources.append(item["relative_path"])

    case_rows = []
    pooled_errors = []
    for case in result["cases"]:
        roi = case["roi"]
        source = dataset_root / roi
        case_dir = result_path.parent / "cases" / roi
        receipt_path = case_dir / "intraop_result.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        frames = []
        for angle in range(0, 181, 20):
            frames.append(tifffile.imread(source / f"{roi}_FSHG_p{angle}.tif").astype(np.float64))
        mean_image = np.mean(frames, axis=0)
        independent_orientation, independent_coherence, _ = _tensor_fields(mean_image, scales=(2.0,))
        orientation = np.load(case_dir / "orientation_degrees.npy", allow_pickle=False)
        coherence = np.load(case_dir / "coherence.npy", allow_pickle=False)
        eligible = np.load(case_dir / "eligible.npy", allow_pickle=False).astype(bool)
        reference = np.mod(tifffile.imread(source / "FI.tif").astype(float) + 90.0, 180.0)
        errors = _axial_errors(orientation[eligible].astype(float), reference[eligible])
        pooled_errors.append(errors)

        registered = {item["path"]: item for item in receipt["artifacts"].values()}
        expected_files = set(config["expected_case_files"])
        existing_files = {path.name for path in case_dir.iterdir() if path.is_file() and path.name != "intraop_result.json"}
        artifact_file_integrity = True
        for name, item in registered.items():
            path = case_dir / name
            artifact_file_integrity &= (
                path.is_file()
                and path.stat().st_size == int(item["bytes"])
                and _sha256(path) == item["sha256"]
            )
        case_rows.append(
            {
                "roi": roi,
                "eligible_pixels": int(errors.size),
                "median_reference_error_degrees": float(np.median(errors)),
                "maximum_independent_orientation_difference_degrees": float(
                    np.max(_axial_errors(orientation.astype(float), independent_orientation[0]))
                ),
                "maximum_independent_coherence_difference": float(
                    np.max(np.abs(coherence.astype(float) - independent_coherence[0]))
                ),
                "case_receipt_matches_summary": bool(
                    receipt["status"] == case["status"]
                    and receipt["measurement"]["evidence_status"] == case["evidence_status"]
                    and int(errors.size) == int(case["eligible_pixels"])
                    and np.isclose(float(np.median(errors)), float(case["median_reference_error_degrees"]), atol=1e-12)
                ),
                "artifact_file_integrity": bool(artifact_file_integrity),
                "artifact_registry_complete": existing_files == expected_files and set(registered) == expected_files,
                "unregistered_files": sorted(existing_files - set(registered)),
                "missing_files": sorted(expected_files - existing_files),
                "clinical_output_withheld": receipt["clinical_output"]["status"] == "withheld",
            }
        )

    all_errors = np.concatenate(pooled_errors)
    independent_summary = {
        "eligible_pixels": int(all_errors.size),
        "pooled_median_reference_error_degrees": float(np.median(all_errors)),
        "pooled_p75_reference_error_degrees": float(np.percentile(all_errors, 75.0)),
        "worst_roi_median_reference_error_degrees": max(row["median_reference_error_degrees"] for row in case_rows),
    }
    checks = {
        "lock_integrity": bool(lock_integrity and not bad_locked),
        "source_integrity": bool(not bad_sources),
        "result_integrity": bool(result_integrity),
        "all_runner_gates_pass": bool(result["status"] == "pass" and all(result["checks"].values())),
        "independent_tensor_equivalence": bool(
            max(row["maximum_independent_orientation_difference_degrees"] for row in case_rows)
            <= float(result["serialization_contract"]["maximum_orientation_difference_degrees"])
            and max(row["maximum_independent_coherence_difference"] for row in case_rows)
            <= float(result["serialization_contract"]["maximum_coherence_difference"])
        ),
        "independent_reference_metric_reproduction": bool(
            independent_summary["eligible_pixels"] == int(result["summary"]["eligible_pixels"])
            and np.isclose(independent_summary["pooled_median_reference_error_degrees"], float(result["summary"]["pooled_median_reference_error_degrees"]), atol=1e-12)
            and np.isclose(independent_summary["pooled_p75_reference_error_degrees"], float(result["summary"]["pooled_p75_reference_error_degrees"]), atol=1e-12)
            and np.isclose(independent_summary["worst_roi_median_reference_error_degrees"], float(result["summary"]["worst_roi_median_reference_error_degrees"]), atol=1e-12)
        ),
        "case_receipt_integrity": bool(all(row["case_receipt_matches_summary"] for row in case_rows)),
        "artifact_file_integrity": bool(all(row["artifact_file_integrity"] for row in case_rows)),
        "artifact_registry_complete": bool(all(row["artifact_registry_complete"] for row in case_rows)),
        "clinical_output_withheld": bool(all(row["clinical_output_withheld"] for row in case_rows)),
    }
    payload = {
        "schema_version": "nostos-intraop-pshg-deployment-final-audit/1.0",
        "target_protocol": result["protocol_version"],
        "status": "verified_pass" if all(checks.values()) else "audit_fail",
        "checks": checks,
        "independent_summary": independent_summary,
        "case_audit": case_rows,
        "bad_locked_files": bad_locked,
        "bad_source_files": bad_sources,
        "interpretation": "A measurement result is not release-verified unless both numerical reproduction and complete artifact provenance pass.",
        "clinical_readiness": "not_ready",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/intraop_pshg_deployment_v1_3_audit.locked.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/nostos0-intraop-pshg-deployment-v1_3-final-audit/final_audit.json"))
    args = parser.parse_args()
    root = args.project_root.resolve()
    result = audit(root, args.dataset_root.resolve(), (root / args.config).resolve(), (root / args.output).resolve())
    print(json.dumps({"status": result["status"], "checks": result["checks"]}, indent=2))
    if result["status"] != "verified_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
