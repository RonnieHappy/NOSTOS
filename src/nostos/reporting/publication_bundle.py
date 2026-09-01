"""Assemble numbered manuscript artifacts from CPU-pilot outputs."""
from __future__ import annotations

import argparse, hashlib, json, shutil
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUTCOMES = {"mean_total_plm": "PLM", "mean_total_oarsi": "OARSI", "mean_total_hhgs": "HHGS"}
MODELS = {"fft_entropy": "FFT angular entropy", "fft_multiscale": "FFT multiscale", "conventional_texture": "Conventional texture", "combined": "Combined"}

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def build_bundle(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    report, lateral = root / "report", root / "report_safo_lateral"
    validation, robustness = root / "validation", root / "robustness"

    tables = []
    for site, directory in (("Medial", report), ("Lateral", lateral)):
        frame = pd.read_csv(directory / "table_cpu_correlations.csv")
        frame = frame[frame.feature == "angular_entropy_median"].copy()
        frame.insert(0, "site", site)
        frame["outcome"] = frame.outcome.map(OUTCOMES)
        tables.append(frame[["site", "outcome", "n", "spearman_rho", "bootstrap_ci_lower", "bootstrap_ci_upper", "p_value", "q_value_bh"]])
    pd.concat(tables, ignore_index=True).to_csv(output / "table_2_entropy_associations.csv", index=False)

    adjusted = pd.read_csv(validation / "table_confounder_adjusted.csv")
    adjusted["feature"] = adjusted.feature.map({"angular_entropy_median": "Angular entropy", "anisotropy_median": "Anisotropy"})
    adjusted["outcome"] = adjusted.outcome.map(OUTCOMES)
    adjusted.to_csv(output / "table_3_adjusted_associations.csv", index=False)
    cv = pd.read_csv(validation / "table_nested_cv_ablations.csv")
    cv["outcome"], cv["model"] = cv.outcome.map(OUTCOMES), cv.model.map(MODELS)
    cv.to_csv(output / "table_4_nested_cv_ablations.csv", index=False)
    mechanism = root.parent / "flagship" / "mechanistic"
    if (mechanism / "table_mechanistic_associations.csv").exists():
        shutil.copy2(mechanism / "table_mechanistic_associations.csv", output / "table_5_mechanistic_associations.csv")

    yield_rows = []
    for label, available, name in (("Safranin-O medial", 90, "safo_medial_features.csv"), ("Safranin-O lateral", 87, "safo_lateral_features.csv"), ("H&E medial", 90, "he_medial_features.csv")):
        frame = pd.read_csv(root / name)
        ok = frame["feature_success"].astype(str).str.lower().eq("true")
        yield_rows.append({"analysis": label, "available": available, "successful": int(ok.sum()), "median_eligible_tiles": float(frame.loc[ok, "analyzed_tiles"].median())})
    pd.DataFrame(yield_rows).to_csv(output / "table_1_processing_yield.csv", index=False)

    for number, source in ((1, report / "figure_cpu_entropy_associations"), (2, lateral / "figure_cpu_entropy_associations"), (3, validation / "figure_nested_cv_plm")):
        for suffix in ("png", "svg"):
            shutil.copy2(source.with_suffix(f".{suffix}"), output / f"figure_{number}.{suffix}")

    robust = pd.read_csv(robustness / "tile_robustness_summary.csv").sort_values("angular_entropy_relative_drift_median")
    mask = pd.read_csv(robustness / "mask_sensitivity_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    y = np.arange(len(robust))
    axes[0].barh(y, 100 * robust.angular_entropy_relative_drift_median, color="#2b6f77")
    axes[0].scatter(100 * robust.angular_entropy_relative_drift_p95, y, color="#b34a32", s=22, label="95th percentile")
    axes[0].set_yticks(y, robust.perturbation.str.replace("_", " ")); axes[0].set_xlabel("Absolute relative entropy drift (%)"); axes[0].set_title("Acquisition perturbations"); axes[0].legend(frameon=False, fontsize=8)
    axes[1].plot(mask.delta_um, 100 * mask.entropy_drift_median, marker="o", color="#2b6f77", label="Median")
    axes[1].plot(mask.delta_um, 100 * mask.entropy_drift_p95, marker="s", color="#b34a32", label="95th percentile")
    axes[1].axvline(0, color="#888", linewidth=.8); axes[1].set_xlabel("Cartilage-mask boundary change (µm)"); axes[1].set_ylabel("Absolute relative entropy drift (%)"); axes[1].set_title("Mask-boundary sensitivity"); axes[1].legend(frameon=False, fontsize=8)
    for suffix in ("png", "svg"): fig.savefig(output / f"figure_4.{suffix}", dpi=300)
    plt.close(fig)
    if (mechanism / "figure_mechanistic_component_heatmap.png").exists():
        for suffix in ("png", "svg"):
            shutil.copy2(mechanism / f"figure_mechanistic_component_heatmap.{suffix}", output / f"figure_5.{suffix}")

    captions = """# Publication artifact captions

**Table 1.** Whole-section processing yield and eligible-tile counts by stain and site.

**Table 2.** Participant-level associations between Safranin-O angular entropy and expert histologic outcomes. Confidence intervals are participant-bootstrap intervals; q values use Benjamini-Hochberg correction within site.

**Table 3.** Paired-site partial-rank associations after adjustment for age, sex, surgical side, cartilage fraction, bone fraction, and analyzed tile count.

**Table 4.** Participant-grouped nested cross-validation ablation results in 87 paired participants.

**Table 5.** Frozen component-level associations testing structural, cellular, staining, extent, and zonal-collagen explanations across first and untouched second sections; q values control the global component-feature family.

**Figure 1.** Medial Safranin-O angular entropy associations with HHGS, OARSI, and PLM scores.

**Figure 2.** Lateral Safranin-O internal replication of angular entropy associations.

**Figure 3.** Out-of-fold PLM predictions from participant-grouped nested cross-validation.

**Figure 4.** Angular-entropy robustness under acquisition perturbations and cartilage-mask boundary changes.

**Figure 5.** Replicated angular-entropy associations with histologic components. Negative coefficients indicate lower angular dispersion with increasing abnormality; blank lateral PLM cells reflect the prespecified medial participant-level PLM analysis.
"""
    (output / "captions.md").write_text(captions, encoding="utf-8")
    artifacts = [{"file": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)} for p in sorted(output.iterdir()) if p.is_file() and p.name != "artifact_manifest.json"]
    manifest = {"bundle_version": 1, "source_root": str(root.resolve()), "artifacts": artifacts}
    (output / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("root", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(build_bundle(args.root, args.output), indent=2))

if __name__ == "__main__": main()
