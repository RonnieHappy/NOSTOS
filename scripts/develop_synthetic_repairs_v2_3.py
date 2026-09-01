"""Outcome-aware v2.3 development on the opened v2.2 failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-2-confirmation/validation.json"
OUTPUT = ROOT / "outputs/nostos0-synthetic-repair-development-v2-3/development.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    hessian = source["cases"]["hessian"]
    hessian_candidates = []
    for boundary in (4.25, 4.5, 4.75, 5.0, 5.5, 6.0):
        accepted = [
            row
            for row in hessian
            if row["measurement"]["samples_per_winning_scale"] >= boundary
        ]
        hessian_candidates.append(
            {
                "minimum_samples_per_winning_scale": boundary,
                "coverage": len(accepted) / len(hessian),
                "accepted": len(accepted),
                "invalid": sum(row["invalid"] for row in accepted),
                "risk": float(np.mean([row["invalid"] for row in accepted])),
            }
        )
    spatial = source["cases"]["spatial"]
    equivariance = source["cases"]["equivariance"]
    axis_candidates = []
    for threshold in (1.50, 1.55, 1.60, 1.65, 1.70, 1.75, 1.80, 2.00):
        isotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] == 1.0]
        anisotropic = [row for row in spatial if row["truth"]["anisotropy_ratio"] >= 2.0]
        isotropic_abstention = float(
            np.mean([row["measurement"]["gradient_moment_ratio"] < threshold for row in isotropic])
        )
        anisotropic_retention = float(
            np.mean([row["measurement"]["gradient_moment_ratio"] >= threshold for row in anisotropic])
        )
        turns = []
        for row in equivariance:
            if (
                row["measurement"]["reference_ratio"] >= threshold
                and row["measurement"]["rotated_ratio"] >= threshold
                and row["measurement"]["rotation_turn_error_degrees"] is not None
            ):
                turns.append(row["measurement"]["rotation_turn_error_degrees"])
        axis_candidates.append(
            {
                "minimum_axis_ratio": threshold,
                "isotropic_axis_abstention": isotropic_abstention,
                "ratio_ge_2_axis_retention": anisotropic_retention,
                "rotation_axis_cases": len(turns),
                "rotation_p95_turn_error_degrees": None
                if not turns
                else float(np.percentile(turns, 95)),
            }
        )
    eligible_axis = [
        item
        for item in axis_candidates
        if item["isotropic_axis_abstention"] >= 0.90
        and item["ratio_ge_2_axis_retention"] >= 0.80
        and item["rotation_axis_cases"] >= 12
        and item["rotation_p95_turn_error_degrees"] <= 3.0
    ]
    selected_axis = min(eligible_axis, key=lambda item: item["minimum_axis_ratio"])
    payload = {
        "protocol_version": "nostos-synthetic-repair-development/2.3",
        "evidence_status": "opened_failed_v2_2_development_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "hessian_candidates": hessian_candidates,
        "axis_candidates": axis_candidates,
        "selected_axis_by_frozen_rule": selected_axis,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"hessian_candidates": hessian_candidates, "selected_axis": selected_axis}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
