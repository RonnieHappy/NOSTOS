from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CONTINUOUS = ("age", "mean_total_hhgs", "mean_total_oarsi", "mean_total_plm")
CATEGORICAL = ("sex", "surgery_side")


def cohort_summary(metadata: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(metadata)
    for variable in CONTINUOUS:
        if variable not in metadata:
            continue
        values = pd.to_numeric(metadata[variable], errors="coerce").dropna().to_numpy(float)
        rows.append({
            "variable": variable,
            "level": "continuous",
            "n": len(values),
            "missing": total - len(values),
            "summary": (
                f"mean {np.mean(values):.2f} (SD {np.std(values, ddof=1) if len(values) > 1 else float('nan'):.2f}); "
                f"median {np.median(values):.2f} [IQR {np.quantile(values, .25):.2f}–{np.quantile(values, .75):.2f}]; "
                f"range {np.min(values):.2f}–{np.max(values):.2f}"
            ) if len(values) else "not available",
        })
    for variable in CATEGORICAL:
        if variable not in metadata:
            continue
        values = metadata[variable].dropna().astype(str)
        for level, count in values.value_counts().sort_index().items():
            rows.append({"variable": variable, "level": level, "n": int(count), "missing": int(total - len(values)), "summary": f"{count} ({100 * count / total:.1f}%)"})
    return pd.DataFrame(rows)


def generate_cohort_report(metadata: pd.DataFrame, output_dir: str | Path) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    table = cohort_summary(metadata)
    table.to_csv(output / "table_cohort.csv", index=False)
    available = [column for column in ("mean_total_hhgs", "mean_total_oarsi", "mean_total_plm") if column in metadata]
    if available:
        fig, axes = plt.subplots(1, len(available), figsize=(3.2 * len(available), 3.2), constrained_layout=True)
        axes = np.atleast_1d(axes)
        for axis, column in zip(axes, available):
            axis.hist(pd.to_numeric(metadata[column], errors="coerce").dropna(), bins="auto", color="#176B87", edgecolor="white")
            axis.set(title=column.replace("mean_total_", "").upper(), xlabel="Expert score", ylabel="Participants")
        for suffix in ("png", "svg"):
            fig.savefig(output / f"figure_outcome_distributions.{suffix}", dpi=300)
        plt.close(fig)
    outputs = ["table_cohort.csv"] + (["figure_outcome_distributions.png", "figure_outcome_distributions.svg"] if available else [])
    return {"participants": len(metadata), "outputs": outputs}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cohort table and expert-score distributions.")
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_cohort_report(pd.read_csv(args.metadata), args.output), indent=2))


if __name__ == "__main__":
    main()
