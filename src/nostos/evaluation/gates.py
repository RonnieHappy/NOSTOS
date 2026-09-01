from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate_manuscript_gates(evidence: dict, thresholds: dict) -> dict:
    checks: list[dict[str, object]] = []

    def minimum(name: str, actual: float, key: str) -> None:
        required = float(thresholds[key])
        checks.append({"gate": name, "pass": actual >= required, "actual": actual, "required": f">={required}"})

    def maximum(name: str, actual: float, key: str) -> None:
        required = float(thresholds[key])
        checks.append({"gate": name, "pass": actual <= required, "actual": actual, "required": f"<={required}"})

    minimum("audited participants", evidence["cohort"]["audited_participants"], "minimum_audited_participants")
    maximum("participant leakage", evidence["leakage"]["violations"], "maximum_participant_leakage_violations")
    minimum("cartilage Dice", evidence["segmentation"]["cartilage_dice"], "minimum_cartilage_dice")
    minimum("cartilage IoU", evidence["segmentation"]["cartilage_iou"], "minimum_cartilage_iou")
    maximum("boundary HD95", evidence["segmentation"]["median_boundary_hd95_um"], "maximum_median_boundary_hd95_um")
    minimum("segmentation success", evidence["segmentation"]["success_rate"], "minimum_segmentation_success_rate")
    maximum("catastrophic masks", evidence["segmentation"]["catastrophic_masks"], "maximum_catastrophic_masks")
    minimum("valid feature rate", evidence["features"]["valid_rate"], "minimum_valid_feature_rate")
    maximum("rotation scalar drift", evidence["robustness"]["rotation_scalar_max_relative_drift"], "maximum_rotation_scalar_relative_drift")
    maximum("rotation orientation error", evidence["robustness"]["rotation_orientation_error_degrees"], "maximum_rotation_orientation_error_degrees")
    if thresholds["require_primary_bootstrap_ci_upper_below_zero"]:
        actual = float(evidence["primary"]["zsd_minus_global_fft_ci_95_upper"])
        checks.append({"gate": "primary ZSD improvement", "pass": actual < 0, "actual": actual, "required": "<0"})
    minimum("stable stains", evidence["stain_analysis"]["directionally_stable_stain_count"], "minimum_directionally_stable_stains")
    minimum("non-FFT comparators", evidence["comparators"]["non_fft_count"], "minimum_non_fft_comparators")
    if thresholds["require_single_command_reproduction"]:
        actual = bool(evidence["reproducibility"]["single_command_verified"])
        checks.append({"gate": "single-command reproduction", "pass": actual, "actual": actual, "required": True})
    return {
        "manuscript_quality_pass": all(bool(check["pass"]) for check in checks),
        "passed": sum(bool(check["pass"]) for check in checks),
        "total": len(checks),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NOSTOS manuscript-quality evidence gates.")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--thresholds", type=Path, default=Path("configs/manuscript_gates.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    result = evaluate_manuscript_gates(evidence, thresholds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["manuscript_quality_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
