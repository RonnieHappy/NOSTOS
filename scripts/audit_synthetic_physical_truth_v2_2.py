"""Independent arithmetic/provenance audit of physical-truth v2.2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-2-confirmation/validation.json"
REPEAT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-2-confirmation-repeat/validation.json"
OUTPUT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-2-audit/audit.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _close(a: float, b: float) -> bool:
    return bool(abs(a - b) <= 1e-12)


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    checks = {
        "protocol_hash": _hash(ROOT / payload["protocol"]) == payload["protocol_sha256"],
        "development_hash": _hash(ROOT / payload["development"]) == payload["development_sha256"],
        "implementation_hash": _hash(ROOT / payload["implementation"]) == payload["implementation_sha256"],
        "repeat_byte_identical": SOURCE.read_bytes() == REPEAT.read_bytes(),
        "scientific_status_is_failed": payload["status"] == "fail",
    }
    hessian = payload["cases"]["hessian"]
    spatial = payload["cases"]["spatial"]
    equivariance = payload["cases"]["equivariance"]
    checks["case_counts"] = len(hessian) == 36 and len(spatial) == 150 and len(equivariance) == 24
    checks["unique_case_ids"] = all(
        len(rows) == len({row["case_id"] for row in rows})
        for rows in (hessian, spatial, equivariance)
    )

    accepted = [row for row in hessian if row["supported"]]
    recalls = {}
    for label in ("blob", "tube", "sheet"):
        rows = [row for row in accepted if row["truth"]["class"] == label]
        recalls[label] = float(np.mean([not row["invalid"] for row in rows]))
    scale_error = [float(row["measurement"]["scale_relative_error"]) for row in accepted]
    hessian_recomputed = {
        "accepted": len(accepted),
        "coverage": len(accepted) / len(hessian),
        "raw_invalid": sum(row["invalid"] for row in hessian),
        "accepted_invalid": sum(row["invalid"] for row in accepted),
        "accepted_risk": float(np.mean([row["invalid"] for row in accepted])),
        "all_raw_misclassifications_rejected": all(
            not row["supported"] for row in hessian if row["invalid"]
        ),
        "balanced_accuracy": float(np.mean(list(recalls.values()))),
        "median_scale_relative_error": float(np.median(scale_error)),
        "p95_scale_relative_error": float(np.percentile(scale_error, 95)),
    }
    checks["hessian_metrics"] = all(
        stored == hessian_recomputed[name]
        if isinstance(stored, (bool, int))
        else _close(float(stored), float(hessian_recomputed[name]))
        for name, stored in payload["metrics"]["hessian"].items()
        if name in hessian_recomputed
    ) and all(
        _close(float(payload["metrics"]["hessian"]["per_class_recall"][label]), value)
        for label, value in recalls.items()
    )

    anisotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] > 1]
    isotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] == 1]
    truth = [row["truth"]["anisotropy_ratio"] for row in anisotropic]
    estimate = [row["measurement"]["gradient_moment_ratio"] for row in anisotropic]
    errors = [row["relative_ratio_error"] for row in anisotropic]
    subset = [row for row in anisotropic if row["measurement"]["intrinsic_supported"]]
    subset_truth = [row["truth"]["anisotropy_ratio"] for row in subset]
    intrinsic = [row["measurement"]["intrinsic_range_ratio"] for row in subset]
    gradient_subset = [row["measurement"]["gradient_moment_ratio"] for row in subset]
    spatial_recomputed = {
        "gradient_spearman_rho": float(spearmanr(truth, estimate).statistic),
        "gradient_median_relative_error": float(np.median(errors)),
        "gradient_p95_relative_error": float(np.percentile(errors, 95)),
        "isotropic_median_ratio": float(np.median([row["measurement"]["gradient_moment_ratio"] for row in isotropic])),
        "isotropic_p95_ratio": float(np.percentile([row["measurement"]["gradient_moment_ratio"] for row in isotropic], 95)),
        "isotropic_axis_abstention": float(np.mean([not row["axis_identifiable"] for row in isotropic])),
        "ratio_ge_2_axis_retention": float(
            np.mean([row["axis_identifiable"] for row in spatial if row["truth"]["anisotropy_ratio"] >= 2])
        ),
        "intrinsic_comparator_cases": len(subset),
        "intrinsic_comparator_spearman_rho": float(spearmanr(subset_truth, intrinsic).statistic),
        "gradient_on_intrinsic_subset_spearman_rho": float(spearmanr(subset_truth, gradient_subset).statistic),
    }
    checks["spatial_metrics"] = all(
        stored == spatial_recomputed[name]
        if isinstance(stored, int)
        else _close(float(stored), float(spatial_recomputed[name]))
        for name, stored in payload["metrics"]["spatial"].items()
        if name in spatial_recomputed
    )

    rotation = [row["measurement"]["rotation_ratio_relative_drift"] for row in equivariance]
    resampling = [row["measurement"]["resampling_ratio_relative_drift"] for row in equivariance]
    turns = [
        row["measurement"]["rotation_turn_error_degrees"]
        for row in equivariance
        if row["measurement"]["rotation_turn_error_degrees"] is not None
    ]
    equivariance_recomputed = {
        "cases": len(equivariance),
        "rotation_median_ratio_drift": float(np.median(rotation)),
        "rotation_p95_ratio_drift": float(np.percentile(rotation, 95)),
        "rotation_axis_cases": len(turns),
        "rotation_p95_turn_error_degrees": float(np.percentile(turns, 95)),
        "resampling_median_ratio_drift": float(np.median(resampling)),
        "resampling_p95_ratio_drift": float(np.percentile(resampling, 95)),
    }
    checks["equivariance_metrics"] = all(
        stored == equivariance_recomputed[name]
        if isinstance(stored, int)
        else _close(float(stored), float(equivariance_recomputed[name]))
        for name, stored in payload["metrics"]["equivariance"].items()
    )
    checks["label_blind_hashes"] = (
        payload["label_blindness"]["unchanged"]
        and payload["label_blindness"]["geometry_sha256"]
        == payload["label_blindness"]["label_complement_geometry_sha256"]
    )
    receipt = {
        "audit": "nostos-synthetic-physical-truth-v2-2-independent-audit/1.0",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "repeat_sha256": _hash(REPEAT),
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": receipt["status"], "checks": checks}, indent=2, sort_keys=True))
    if receipt["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
