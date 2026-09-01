"""Retrospective independent-ROI finite-sample audit of the frozen PSHG policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "outputs/nostos0-pshg-acquisition-shift-v1-development/development.json"
ROWS_PATH = ROOT / "outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation_rows.jsonl"
CONFIRMATION_PATH = ROOT / "outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation.json"
PROTOCOL_PATH = ROOT / "docs/NOSTOS0_PSHG_INDEPENDENT_UNIT_RISK_AUDIT_V1_PROTOCOL.md"
OUTPUT_PATH = ROOT / "outputs/nostos0-pshg-independent-unit-risk-audit-v1/audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def one_sided_cp_upper(failures: int, units: int, confidence: float = 0.95) -> float:
    if units <= 0:
        raise ValueError("units must be positive")
    if failures == units:
        return 1.0
    return float(beta.ppf(confidence, failures + 1, units - failures))


def main() -> None:
    development = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    confirmation = json.loads(CONFIRMATION_PATH.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in ROWS_PATH.read_text(encoding="utf-8").splitlines()]

    profile = development["profile"]
    risk_map = profile["risk_maps"]["full_contract"]
    threshold = float(profile["maximum_predicted_risk"])
    predicted = np.interp(
        np.asarray([row["scores"]["full_contract"] for row in rows], dtype=float),
        np.asarray(risk_map["x_thresholds"], dtype=float),
        np.asarray(risk_map["y_thresholds"], dtype=float),
        left=float(risk_map["y_thresholds"][0]),
        right=float(risk_map["y_thresholds"][-1]),
    )
    accepted_rows = [row for row, risk in zip(rows, predicted, strict=True) if risk <= threshold]
    rois = sorted({str(row["roi"]) for row in rows})
    accepted_by_roi = {
        roi: [row for row in accepted_rows if str(row["roi"]) == roi]
        for roi in rois
    }
    accepted_rois = [roi for roi, values in accepted_by_roi.items() if values]
    failing_rois = [
        roi for roi in accepted_rois if any(bool(row["invalid"]) for row in accepted_by_roi[roi])
    ]

    row_invalid = int(sum(bool(row["invalid"]) for row in accepted_rows))
    roi_failures = len(failing_rois)
    roi_units = len(accepted_rois)
    roi_risk = float(roi_failures / roi_units)
    roi_upper = one_sided_cp_upper(roi_failures, roi_units)
    frozen = confirmation["summary"]["operating"]["full_contract"]

    checks = {
        "exact_24_confirmation_rois": len(rois) == 24,
        "recomputed_row_counts_match_frozen_receipt": (
            len(rows) == int(frozen["eligible"])
            and len(accepted_rows) == int(frozen["accepted"])
            and row_invalid == int(frozen["invalid"])
        ),
        "row_coverage_at_least_60_percent": len(accepted_rows) / len(rows) >= 0.60,
        "roi_coverage_at_least_60_percent": roi_units / len(rois) >= 0.60,
        "roi_risk_upper95_at_most_20_percent": roi_upper <= 0.20,
    }

    payload = {
        "protocol_version": "nostos-pshg-independent-unit-risk-audit/1.0",
        "audit_class": "retrospective_fixed-policy_finite-sample_audit",
        "status": "pass" if all(checks.values()) else "fail",
        "claim_boundary": (
            "Independent-ROI silent-failure risk for the already frozen PSHG-TISS v1 "
            "computational acquisition-shift confirmation; not a prospective guarantee, "
            "instrument-transfer, tissue-mechanics, diagnosis or clinical validation."
        ),
        "inputs": {
            "profile": str(PROFILE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "profile_sha256": sha256(PROFILE_PATH),
            "rows": str(ROWS_PATH.relative_to(ROOT)).replace("\\", "/"),
            "rows_sha256": sha256(ROWS_PATH),
            "confirmation": str(CONFIRMATION_PATH.relative_to(ROOT)).replace("\\", "/"),
            "confirmation_sha256": sha256(CONFIRMATION_PATH),
            "protocol": str(PROTOCOL_PATH.relative_to(ROOT)).replace("\\", "/"),
            "protocol_sha256": sha256(PROTOCOL_PATH),
        },
        "fixed_policy": {
            "policy": "full_contract",
            "maximum_predicted_row_risk": threshold,
            "risk_map": risk_map,
        },
        "row_level": {
            "eligible": len(rows),
            "accepted": len(accepted_rows),
            "coverage": float(len(accepted_rows) / len(rows)),
            "accepted_invalid": row_invalid,
            "observed_risk": float(row_invalid / len(accepted_rows)),
        },
        "independent_roi_level": {
            "eligible": len(rois),
            "accepted": roi_units,
            "coverage": float(roi_units / len(rois)),
            "failing": roi_failures,
            "failing_roi_ids": failing_rois,
            "observed_risk": roi_risk,
            "one_sided_95_clopper_pearson_upper": roi_upper,
            "target_upper_bound": 0.20,
        },
        "checks": checks,
        "interpretation": (
            "The original condition-row comparison remains valid, but the stronger "
            "independent-ROI finite-sample risk guarantee is not supported if status is fail."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_PATH), "status": payload["status"], "content_sha256": payload["content_sha256"], "roi_upper95": roi_upper}, indent=2))


if __name__ == "__main__":
    main()
