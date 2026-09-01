"""Develop input-only spatial stability support on opened v2.3 failures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from nostos.features.validated_responses import gradient_moment_anisotropy_2d
from nostos.validation.phantoms import generate_phantom


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/nostos0-synthetic-physical-truth-v2-3-confirmation/validation.json"
OUTPUT = ROOT / "outputs/nostos0-synthetic-repair-development-v2-4/development.json"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _seed(correlation: float, ratio: float, offset: int) -> int:
    return 1210000 + int(correlation) * 1000 + int(ratio * 100) + offset


def _stability(image: np.ndarray, full_ratio: float) -> dict[str, float]:
    height, width = image.shape
    quadrants = (
        image[: height // 2, : width // 2],
        image[: height // 2, width // 2 :],
        image[height // 2 :, : width // 2],
        image[height // 2 :, width // 2 :],
    )
    quadrant_ratios = [
        gradient_moment_anisotropy_2d(value, spacing_um=(1.0, 1.0)).ratio
        for value in quadrants
    ]
    margin_y = int(round(height * 0.125))
    margin_x = int(round(width * 0.125))
    nested = image[margin_y : height - margin_y, margin_x : width - margin_x]
    nested_ratio = gradient_moment_anisotropy_2d(
        nested, spacing_um=(1.0, 1.0)
    ).ratio
    log_quadrant = np.abs(np.log(np.asarray(quadrant_ratios) / full_ratio))
    nested_drift = abs(float(np.log(nested_ratio / full_ratio)))
    return {
        "quadrant_median_log_drift": float(np.median(log_quadrant)),
        "quadrant_maximum_log_drift": float(np.max(log_quadrant)),
        "nested_log_drift": nested_drift,
        "combined_median_nested_score": max(float(np.median(log_quadrant)), nested_drift),
        "combined_maximum_nested_score": max(float(np.max(log_quadrant)), nested_drift),
    }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = []
    for item in source["cases"]["spatial"]:
        correlation = float(item["truth"]["correlation_length_um"])
        ratio = float(item["truth"]["anisotropy_ratio"])
        offset = int(str(item["case_id"]).rsplit("seed", 1)[1])
        phantom = generate_phantom(
            "heterogeneity",
            shape=(192, 192),
            spacing_um=(1.0, 1.0),
            seed=_seed(correlation, ratio, offset),
            correlation_length_um=correlation,
            anisotropy_ratio=ratio,
        )
        full_ratio = float(item["measurement"]["gradient_moment_ratio"])
        rows.append(
            {
                "case_id": item["case_id"],
                "truth_ratio": ratio,
                "estimated_ratio": full_ratio,
                "relative_error": float(item["relative_ratio_error"]),
                "stability": _stability(phantom.image, full_ratio),
            }
        )
    candidates = []
    for component in (
        "quadrant_median_log_drift",
        "quadrant_maximum_log_drift",
        "nested_log_drift",
        "combined_median_nested_score",
        "combined_maximum_nested_score",
    ):
        for threshold in (0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30):
            accepted = [row for row in rows if row["stability"][component] <= threshold]
            anisotropic = [row for row in accepted if row["truth_ratio"] > 1.0]
            isotropic = [row for row in accepted if row["truth_ratio"] == 1.0]
            if len(anisotropic) < 2 or len(set(row["truth_ratio"] for row in anisotropic)) < 2:
                continue
            candidates.append(
                {
                    "component": component,
                    "maximum_score": threshold,
                    "coverage": len(accepted) / len(rows),
                    "anisotropic_coverage": len(anisotropic)
                    / sum(row["truth_ratio"] > 1.0 for row in rows),
                    "gradient_spearman_rho": float(
                        spearmanr(
                            [row["truth_ratio"] for row in anisotropic],
                            [row["estimated_ratio"] for row in anisotropic],
                        ).statistic
                    ),
                    "median_relative_error": float(
                        np.median([row["relative_error"] for row in anisotropic])
                    ),
                    "p95_relative_error": float(
                        np.percentile([row["relative_error"] for row in anisotropic], 95)
                    ),
                    "isotropic_cases": len(isotropic),
                    "isotropic_p95_ratio": None
                    if not isotropic
                    else float(np.percentile([row["estimated_ratio"] for row in isotropic], 95)),
                }
            )
    deployable = [
        item
        for item in candidates
        if item["coverage"] >= 0.60
        and item["anisotropic_coverage"] >= 0.60
        and item["gradient_spearman_rho"] >= 0.80
        and item["median_relative_error"] <= 0.10
        and item["p95_relative_error"] <= 0.25
        and (item["isotropic_p95_ratio"] is None or item["isotropic_p95_ratio"] <= 1.50)
    ]
    selected = None
    if deployable:
        selected = max(
            deployable,
            key=lambda item: (
                item["coverage"],
                item["anisotropic_coverage"],
                item["gradient_spearman_rho"],
                -item["maximum_score"],
            ),
        )
    payload = {
        "protocol_version": "nostos-synthetic-repair-development/2.4",
        "evidence_status": "opened_failed_v2_3_development_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _hash(SOURCE),
        "cases": rows,
        "candidates": candidates,
        "selected_by_frozen_rule": selected,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"selected": selected, "deployable_candidates": len(deployable)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
