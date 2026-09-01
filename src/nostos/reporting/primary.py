from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nostos.evaluation.participant import collapse_by_participant, paired_participant_bootstrap, participant_metrics


REQUIRED_COLUMNS = {"participant_id", "observed", "global_fft", "zsd"}


def generate_primary_report(predictions: pd.DataFrame, output_dir: str | Path) -> dict:
    missing = REQUIRED_COLUMNS.difference(predictions.columns)
    if missing:
        raise ValueError(f"missing primary prediction columns: {sorted(missing)}")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    identifiers = predictions["participant_id"].astype(str)
    observed = predictions["observed"].astype(float)
    models = {name: predictions[name].astype(float) for name in ("global_fft", "zsd")}
    metric_rows = []
    for name, values in models.items():
        metric_rows.append({"model": name, **asdict(participant_metrics(identifiers, observed, values))})
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(output / "table_primary_metrics.csv", index=False)
    comparison = paired_participant_bootstrap(
        identifiers, observed, models["global_fft"], models["zsd"], iterations=5000
    )
    (output / "primary_bootstrap.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")

    participant_ids, truth, global_prediction = collapse_by_participant(identifiers, observed, models["global_fft"])
    _, _, zsd_prediction = collapse_by_participant(identifiers, observed, models["zsd"])
    error_global = np.abs(global_prediction - truth)
    error_zsd = np.abs(zsd_prediction - truth)
    order = np.argsort(error_global - error_zsd)
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.0), constrained_layout=True)
    limits = [float(min(truth.min(), global_prediction.min(), zsd_prediction.min())), float(max(truth.max(), global_prediction.max(), zsd_prediction.max()))]
    axes[0].plot(limits, limits, color="0.6", linewidth=1, linestyle="--")
    axes[0].scatter(truth, global_prediction, s=22, color="#7A7A7A", label="Global FFT")
    axes[0].scatter(truth, zsd_prediction, s=22, color="#176B87", label="ZSD")
    axes[0].set(xlabel="Observed expert score", ylabel="Held-out prediction", title="Participant-level predictions")
    axes[0].legend(frameon=False)
    axes[1].axhline(0, color="0.6", linewidth=1)
    axes[1].scatter(np.arange(len(order)), (error_global - error_zsd)[order], s=20, color="#176B87")
    axes[1].set(xlabel="Locked-test participant (ordered)", ylabel="Absolute-error improvement", title="Positive values favor ZSD")
    for suffix in ("png", "svg"):
        fig.savefig(output / f"figure_primary.{suffix}", dpi=300)
    plt.close(fig)
    return {
        "participant_count": len(participant_ids),
        "metrics": metric_rows,
        "comparison": comparison,
        "outputs": ["table_primary_metrics.csv", "primary_bootstrap.json", "figure_primary.png", "figure_primary.svg"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the locked primary NOSTOS table and figure.")
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = generate_primary_report(pd.read_csv(args.predictions), args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
