"""Independent arithmetic and provenance audit of physical-truth v2.4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "outputs/nostos0-synthetic-physical-truth-v2-4-confirmation/validation.json"
)
REPEAT = (
    ROOT
    / "outputs/nostos0-synthetic-physical-truth-v2-4-confirmation-repeat/validation.json"
)
OUTPUT = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-4-audit/audit.json"
AUDIT_NAME = "nostos-synthetic-physical-truth-v2-4-independent-audit/1.0"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _close(left: float, right: float) -> bool:
    return bool(abs(left - right) <= 1e-12)


def _metric_block_matches(stored: dict, recomputed: dict) -> bool:
    for name, value in recomputed.items():
        if isinstance(value, dict):
            if not _metric_block_matches(stored[name], value):
                return False
        elif isinstance(value, bool) or isinstance(value, int):
            if stored[name] != value:
                return False
        elif not _close(float(stored[name]), float(value)):
            return False
    return True


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    payload_without_hash = dict(payload)
    claimed_content_hash = payload_without_hash.pop("content_sha256")
    canonical = json.dumps(
        payload_without_hash, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    checks = {
        "content_hash": hashlib.sha256(canonical).hexdigest() == claimed_content_hash,
        "protocol_hash": _hash(ROOT / payload["protocol"])
        == payload["protocol_sha256"],
        "development_hash": _hash(ROOT / payload["development"])
        == payload["development_sha256"],
        "implementation_hash": _hash(ROOT / payload["implementation"])
        == payload["implementation_sha256"],
        "evaluator_hash": _hash(ROOT / payload["evaluator"])
        == payload["evaluator_sha256"],
        "repeat_byte_identical": SOURCE.read_bytes() == REPEAT.read_bytes(),
        "scientific_status_is_failed": payload["status"] == "fail",
    }
    hessian = payload["cases"]["hessian"]
    spatial = payload["cases"]["spatial"]
    equivariance = payload["cases"]["equivariance"]
    checks["case_counts"] = (
        len(hessian) == 36 and len(spatial) == 150 and len(equivariance) == 24
    )
    checks["unique_case_ids"] = all(
        len(rows) == len({row["case_id"] for row in rows})
        for rows in (hessian, spatial, equivariance)
    )

    accepted_hessian = [row for row in hessian if row["supported"]]
    recalls = {}
    for label in ("blob", "tube", "sheet"):
        class_rows = [
            row for row in accepted_hessian if row["truth"]["class"] == label
        ]
        recalls[label] = float(
            np.mean([not row["invalid"] for row in class_rows])
        )
    scale_errors = [
        row["measurement"]["scale_relative_error"] for row in accepted_hessian
    ]
    hessian_recomputed = {
        "cases": len(hessian),
        "accepted": len(accepted_hessian),
        "coverage": len(accepted_hessian) / len(hessian),
        "raw_invalid": sum(row["invalid"] for row in hessian),
        "accepted_invalid": sum(row["invalid"] for row in accepted_hessian),
        "accepted_risk": float(
            np.mean([row["invalid"] for row in accepted_hessian])
        ),
        "all_raw_misclassifications_rejected": all(
            not row["supported"] for row in hessian if row["invalid"]
        ),
        "balanced_accuracy": float(np.mean(list(recalls.values()))),
        "per_class_recall": recalls,
        "median_scale_relative_error": float(np.median(scale_errors)),
        "p95_scale_relative_error": float(np.percentile(scale_errors, 95)),
    }
    checks["hessian_metrics"] = _metric_block_matches(
        payload["metrics"]["hessian"], hessian_recomputed
    )

    accepted = [row for row in spatial if row["supported"]]
    anisotropic = [
        row for row in spatial if row["truth"]["anisotropy_ratio"] > 1.0
    ]
    accepted_anisotropic = [row for row in anisotropic if row["supported"]]
    isotropic = [
        row for row in spatial if row["truth"]["anisotropy_ratio"] == 1.0
    ]
    accepted_isotropic = [row for row in isotropic if row["supported"]]
    high = [
        row
        for row in accepted
        if row["truth"]["anisotropy_ratio"] >= 2.0
    ]
    truth = [row["truth"]["anisotropy_ratio"] for row in accepted_anisotropic]
    estimate = [row["measurement"]["ratio"] for row in accepted_anisotropic]
    accepted_errors = [row["relative_ratio_error"] for row in accepted_anisotropic]
    raw_errors = [row["relative_ratio_error"] for row in anisotropic]
    spatial_recomputed = {
        "cases": len(spatial),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(spatial),
        "anisotropic_cases": len(anisotropic),
        "accepted_anisotropic": len(accepted_anisotropic),
        "anisotropic_coverage": len(accepted_anisotropic) / len(anisotropic),
        "accepted_isotropic": len(accepted_isotropic),
        "gradient_spearman_rho": float(spearmanr(truth, estimate).statistic),
        "gradient_median_relative_error": float(np.median(accepted_errors)),
        "gradient_p95_relative_error": float(np.percentile(accepted_errors, 95)),
        "always_emit_p95_relative_error": float(np.percentile(raw_errors, 95)),
        "accepted_invalid_risk": float(
            np.mean([row["invalid"] for row in accepted_anisotropic])
        ),
        "always_emit_invalid_risk": float(
            np.mean([row["invalid"] for row in anisotropic])
        ),
        "isotropic_median_ratio": float(
            np.median([row["measurement"]["ratio"] for row in accepted_isotropic])
        ),
        "isotropic_p95_ratio": float(
            np.percentile(
                [row["measurement"]["ratio"] for row in accepted_isotropic], 95
            )
        ),
        "isotropic_axis_abstention": float(
            np.mean([not row["axis_identifiable"] for row in accepted_isotropic])
        ),
        "ratio_ge_2_axis_retention": float(
            np.mean([row["axis_identifiable"] for row in high])
        ),
        "median_stability_score": float(
            np.median([row["measurement"]["stability_score"] for row in spatial])
        ),
    }
    checks["spatial_metrics"] = _metric_block_matches(
        payload["metrics"]["spatial"], spatial_recomputed
    )

    accepted_equivariance = [row for row in equivariance if row["supported"]]
    rotation = [
        row["measurement"]["rotation_ratio_relative_drift"]
        for row in accepted_equivariance
    ]
    resampling = [
        row["measurement"]["resampling_ratio_relative_drift"]
        for row in accepted_equivariance
    ]
    turns = [
        row["measurement"]["rotation_turn_error_degrees"]
        for row in accepted_equivariance
        if row["measurement"]["rotation_turn_error_degrees"] is not None
    ]
    equivariance_recomputed = {
        "cases": len(equivariance),
        "accepted": len(accepted_equivariance),
        "coverage": len(accepted_equivariance) / len(equivariance),
        "rotation_median_ratio_drift": float(np.median(rotation)),
        "rotation_p95_ratio_drift": float(np.percentile(rotation, 95)),
        "rotation_axis_cases": len(turns),
        "rotation_p95_turn_error_degrees": float(np.percentile(turns, 95)),
        "resampling_median_ratio_drift": float(np.median(resampling)),
        "resampling_p95_ratio_drift": float(np.percentile(resampling, 95)),
    }
    checks["equivariance_metrics"] = _metric_block_matches(
        payload["metrics"]["equivariance"], equivariance_recomputed
    )
    checks["label_blind_hashes"] = bool(
        payload["label_blindness"]["unchanged"]
        and payload["label_blindness"]["geometry_sha256"]
        == payload["label_blindness"]["label_complement_geometry_sha256"]
    )
    receipt = {
        "audit": AUDIT_NAME,
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "repeat_sha256": _hash(REPEAT),
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }
    canonical_receipt = json.dumps(
        receipt, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    receipt["content_sha256"] = hashlib.sha256(canonical_receipt).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"status": receipt["status"], "checks": checks},
            indent=2,
            sort_keys=True,
        )
    )
    if receipt["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
