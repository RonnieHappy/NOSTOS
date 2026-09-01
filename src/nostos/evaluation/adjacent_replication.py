"""Locked adjacent-section repeatability and outcome replication analysis."""
from __future__ import annotations

import argparse, json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

FEATURES = ["angular_entropy_median", "anisotropy_median", "spectral_slope_median", "characteristic_frequency_cycles_per_mm_median", "tensor_coherence_median", "glcm_contrast_median", "glcm_homogeneity_median"]
OUTCOMES = ["mean_total_plm", "mean_total_oarsi", "mean_total_hhgs"]

def icc_a1(x: np.ndarray, y: np.ndarray) -> float:
    values = np.column_stack([x, y]).astype(float); n, k = values.shape
    grand = values.mean(); row_means = values.mean(axis=1); col_means = values.mean(axis=0)
    ms_rows = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_cols = n * np.sum((col_means - grand) ** 2) / (k - 1)
    residual = values - row_means[:, None] - col_means[None, :] + grand
    ms_error = np.sum(residual ** 2) / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    return float((ms_rows - ms_error) / denominator) if denominator else np.nan

def concordance_ccc(x: np.ndarray, y: np.ndarray) -> float:
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1); covariance = np.cov(x, y, ddof=1)[0, 1]
    denominator = vx + vy + (np.mean(x) - np.mean(y)) ** 2
    return float(2 * covariance / denominator) if denominator else np.nan

def bh(values: pd.Series) -> np.ndarray:
    p = values.to_numpy(float); order = np.argsort(p); ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]; result = np.empty_like(ranked); result[order] = np.clip(ranked, 0, 1); return result

def bootstrap_spearman(x, y, repeats=5000, seed=260825):
    rng = np.random.default_rng(seed); n = len(x); estimates = []
    for _ in range(repeats):
        idx = rng.integers(0, n, n); value = spearmanr(x[idx], y[idx]).statistic
        if np.isfinite(value): estimates.append(value)
    return np.quantile(estimates, [.025, .975])

def paired(rank1: Path, rank2: Path, site: str) -> pd.DataFrame:
    a, b = pd.read_csv(rank1), pd.read_csv(rank2)
    a = a[a.feature_success.astype(str).str.lower().eq("true")]; b = b[b.feature_success.astype(str).str.lower().eq("true")]
    return a.merge(b, on="participant_id", suffixes=("_rank1", "_rank2"), validate="one_to_one").assign(replication_site=site)

def run(medial1, medial2, lateral1, lateral2, metadata, output, bootstrap=5000):
    output.mkdir(parents=True, exist_ok=True); meta = pd.read_csv(metadata)
    agreement_rows, outcome_rows, paired_frames = [], [], []
    for site, first, second in (("Medial", medial1, medial2), ("Lateral", lateral1, lateral2)):
        frame = paired(first, second, site); paired_frames.append(frame)
        for feature in FEATURES:
            x, y = frame[f"{feature}_rank1"].to_numpy(float), frame[f"{feature}_rank2"].to_numpy(float); diff = y - x
            rho, p = spearmanr(x, y)
            agreement_rows.append({"site": site, "feature": feature, "n_pairs": len(frame), "icc_a1": icc_a1(x,y), "lin_ccc": concordance_ccc(x,y), "spearman_rho": rho, "spearman_p": p, "median_absolute_difference": np.median(np.abs(diff)), "bland_altman_bias": np.mean(diff), "bland_altman_lower_loa": np.mean(diff)-1.96*np.std(diff,ddof=1), "bland_altman_upper_loa": np.mean(diff)+1.96*np.std(diff,ddof=1)})
        merged = frame.merge(meta[["participant_id", *OUTCOMES]], on="participant_id", validate="one_to_one")
        for feature in ("angular_entropy_median", "anisotropy_median"):
            for outcome in OUTCOMES:
                x, y = merged[f"{feature}_rank2"].to_numpy(float), merged[outcome].to_numpy(float); rho, p = spearmanr(x,y); lo, hi = bootstrap_spearman(x,y,bootstrap)
                outcome_rows.append({"site":site,"feature":feature,"outcome":outcome,"n":len(x),"replication_rho":rho,"bootstrap_ci_lower":lo,"bootstrap_ci_upper":hi,"p_value":p})
    agreement = pd.DataFrame(agreement_rows); agreement["q_value_bh"] = bh(agreement.spearman_p)
    outcomes = pd.DataFrame(outcome_rows); outcomes["q_value_bh"] = bh(outcomes.p_value)
    agreement.to_csv(output/"table_adjacent_section_agreement.csv",index=False); outcomes.to_csv(output/"table_replication_section_associations.csv",index=False)
    pd.concat(paired_frames,ignore_index=True).to_csv(output/"table_adjacent_section_pairs.csv",index=False)
    fig, axes = plt.subplots(1,2,figsize=(10.5,4.2),constrained_layout=True)
    for ax, frame, site in zip(axes, paired_frames, ("Medial","Lateral")):
        x=frame.angular_entropy_median_rank1.to_numpy(float); y=frame.angular_entropy_median_rank2.to_numpy(float); mean=(x+y)/2; diff=y-x; bias=diff.mean(); sd=diff.std(ddof=1)
        ax.scatter(mean,diff,s=24,alpha=.7,color="#2b6f77"); ax.axhline(bias,color="#b34a32"); ax.axhline(bias+1.96*sd,color="#777",linestyle="--"); ax.axhline(bias-1.96*sd,color="#777",linestyle="--"); ax.set_title(f"{site} (n={len(frame)})"); ax.set_xlabel("Mean adjacent-section entropy"); ax.set_ylabel("Rank 2 - rank 1 entropy")
    for suffix in ("png","svg"): fig.savefig(output/f"figure_adjacent_entropy_bland_altman.{suffix}",dpi=300)
    plt.close(fig)
    report={"medial_pairs":len(paired_frames[0]),"lateral_pairs":len(paired_frames[1]),"bootstrap_repeats":bootstrap,"protocol":"docs/confirmatory_replication_protocol.md"}; (output/"adjacent_replication_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); return report

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("medial_rank1",type=Path); p.add_argument("medial_rank2",type=Path); p.add_argument("lateral_rank1",type=Path); p.add_argument("lateral_rank2",type=Path); p.add_argument("metadata",type=Path); p.add_argument("--output",type=Path,required=True); p.add_argument("--bootstrap",type=int,default=5000)
    a=p.parse_args(); print(json.dumps(run(a.medial_rank1,a.medial_rank2,a.lateral_rank1,a.lateral_rank2,a.metadata,a.output,a.bootstrap),indent=2))
if __name__=="__main__": main()
