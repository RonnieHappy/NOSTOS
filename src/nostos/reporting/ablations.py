from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nostos.evaluation.participant import collapse_by_participant, participant_metrics


def generate_ablation_report(
    predictions: pd.DataFrame,
    output_dir: str | Path,
    *,
    iterations: int = 2000,
    seed: int = 240826,
) -> dict:
    required = {"stratum_type", "stratum_value", "model", "participant_id", "observed", "predicted"}
    missing = required.difference(predictions.columns)
    if missing:
        raise ValueError(f"missing ablation columns: {sorted(missing)}")
    rng = np.random.default_rng(seed)
    rows = []
    for keys, group in predictions.groupby(["stratum_type", "stratum_value", "model"], sort=True):
        ids, truth, estimate = collapse_by_participant(group["participant_id"], group["observed"], group["predicted"])
        metrics = participant_metrics(ids, truth, estimate)
        bootstrap = np.empty(iterations)
        for index in range(iterations):
            selected = rng.integers(0, len(ids), len(ids))
            bootstrap[index] = np.mean(np.abs(estimate[selected] - truth[selected]))
        lower, upper = np.quantile(bootstrap, [0.025, 0.975])
        rows.append({
            "stratum_type": keys[0], "stratum_value": keys[1], "model": keys[2],
            "participant_count": len(ids), "mae": metrics.mae, "mae_ci_95_lower": lower,
            "mae_ci_95_upper": upper, "rmse": metrics.rmse, "r_squared": metrics.r_squared,
            "spearman_rho": metrics.spearman_rho,
        })
    table = pd.DataFrame(rows)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    table.to_csv(output / "table_ablations.csv", index=False)
    ordered = table.sort_values(["stratum_type", "stratum_value", "mae"]).reset_index(drop=True)
    labels = [f'{row.stratum_type}:{row.stratum_value} · {row.model}' for row in ordered.itertuples()]
    y = np.arange(len(ordered))
    fig_height = max(4.0, 0.28 * len(ordered) + 1.2)
    fig, axis = plt.subplots(figsize=(8.0, fig_height), constrained_layout=True)
    axis.errorbar(
        ordered["mae"], y,
        xerr=np.vstack((ordered["mae"] - ordered["mae_ci_95_lower"], ordered["mae_ci_95_upper"] - ordered["mae"])),
        fmt="o", color="#176B87", ecolor="#8AB3C2", capsize=2,
    )
    axis.set(yticks=y, yticklabels=labels, xlabel="Participant-weighted MAE (95% bootstrap CI)")
    axis.invert_yaxis()
    for suffix in ("png", "svg"):
        fig.savefig(output / f"figure_ablations.{suffix}", dpi=300)
    plt.close(fig)
    return {"comparisons": len(table), "outputs": ["table_ablations.csv", "figure_ablations.png", "figure_ablations.svg"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate prespecified ablation table and forest plot.")
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_ablation_report(pd.read_csv(args.predictions), args.output), indent=2))


if __name__ == "__main__":
    main()
