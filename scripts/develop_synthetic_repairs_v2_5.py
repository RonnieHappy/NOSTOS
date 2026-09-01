"""Develop input-only v2.5 support thresholds on opened v2.4 failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "outputs/nostos0-synthetic-physical-truth-v2-4-confirmation/validation.json"
)
OUTPUT = ROOT / "outputs/nostos0-synthetic-repair-development-v2-5/development.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _hessian_candidates(rows: list[dict]) -> list[dict]:
    candidates = []
    for threshold in (4.75, 5.00, 5.25, 5.50):
        accepted = [
            row
            for row in rows
            if row["measurement"]["samples_per_winning_scale"] >= threshold
        ]
        recalls = {}
        for label in ("blob", "tube", "sheet"):
            class_rows = [
                row for row in accepted if row["truth"]["class"] == label
            ]
            recalls[label] = float(
                np.mean([not row["invalid"] for row in class_rows])
            )
        candidates.append(
            {
                "minimum_samples_per_winning_scale": threshold,
                "accepted": len(accepted),
                "coverage": len(accepted) / len(rows),
                "accepted_invalid": sum(row["invalid"] for row in accepted),
                "accepted_risk": float(
                    np.mean([row["invalid"] for row in accepted])
                ),
                "balanced_accuracy": float(np.mean(list(recalls.values()))),
                "per_class_recall": recalls,
                "all_raw_misclassifications_rejected": all(
                    row["measurement"]["samples_per_winning_scale"] < threshold
                    for row in rows
                    if row["invalid"]
                ),
            }
        )
    return candidates


def _axis_candidates(spatial: list[dict], equivariance: list[dict]) -> list[dict]:
    supported_spatial = [row for row in spatial if row["supported"]]
    supported_equivariance = [row for row in equivariance if row["supported"]]
    isotropic = [
        row
        for row in supported_spatial
        if row["truth"]["anisotropy_ratio"] == 1.0
    ]
    high = [
        row
        for row in supported_spatial
        if row["truth"]["anisotropy_ratio"] >= 2.0
    ]
    candidates = []
    for threshold in (1.55, 1.65, 1.75, 1.85, 2.00):
        axis_rows = [
            row
            for row in supported_equivariance
            if row["measurement"]["reference"]["ratio"] >= threshold
            and row["measurement"]["rotated"]["ratio"] >= threshold
        ]
        turns = [
            row["measurement"]["rotation_turn_error_degrees"] for row in axis_rows
        ]
        candidates.append(
            {
                "minimum_axis_ratio": threshold,
                "isotropic_axis_abstention": float(
                    np.mean(
                        [row["measurement"]["ratio"] < threshold for row in isotropic]
                    )
                ),
                "ratio_ge_2_axis_retention": float(
                    np.mean(
                        [row["measurement"]["ratio"] >= threshold for row in high]
                    )
                ),
                "equivariance_supported_cases": len(supported_equivariance),
                "rotation_axis_cases": len(axis_rows),
                "rotation_axis_coverage": len(axis_rows)
                / len(supported_equivariance),
                "rotation_p95_turn_error_degrees": float(
                    np.percentile(turns, 95)
                ),
            }
        )
    return candidates


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    hessian = _hessian_candidates(source["cases"]["hessian"])
    axis = _axis_candidates(
        source["cases"]["spatial"], source["cases"]["equivariance"]
    )
    deployable_hessian = [
        item
        for item in hessian
        if item["coverage"] >= 0.60
        and item["balanced_accuracy"] >= 0.95
        and min(item["per_class_recall"].values()) >= 0.90
        and item["accepted_risk"] <= 0.05
        and item["all_raw_misclassifications_rejected"]
    ]
    selected_hessian = max(
        deployable_hessian,
        key=lambda item: (
            item["coverage"],
            -item["minimum_samples_per_winning_scale"],
        ),
        default=None,
    )
    deployable_axis = [
        item
        for item in axis
        if item["isotropic_axis_abstention"] >= 0.90
        and item["ratio_ge_2_axis_retention"] >= 0.80
        and item["rotation_axis_coverage"] >= 0.60
        and item["rotation_p95_turn_error_degrees"] <= 3.0
    ]
    selected_axis = max(
        deployable_axis,
        key=lambda item: (
            item["rotation_axis_coverage"],
            item["ratio_ge_2_axis_retention"],
            -item["minimum_axis_ratio"],
        ),
        default=None,
    )
    payload = {
        "protocol_version": "nostos-synthetic-repair-development/2.5",
        "evidence_status": "opened_failed_v2_4_development_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "hessian_candidates": hessian,
        "axis_candidates": axis,
        "selection_rule": {
            "hessian": (
                "Among candidates satisfying all v2.4 classification gates, "
                "maximize coverage then choose the lowest threshold."
            ),
            "axis": (
                "Among candidates satisfying isotropic abstention, high-ratio "
                "retention, rotation-axis coverage and turn-error gates, maximize "
                "axis coverage, then high-ratio retention, then choose the lowest "
                "threshold."
            ),
        },
        "selected_by_frozen_rule": {
            "hessian": selected_hessian,
            "axis": selected_axis,
        },
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "selected_hessian": selected_hessian,
                "selected_axis": selected_axis,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
