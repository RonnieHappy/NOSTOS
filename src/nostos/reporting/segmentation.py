from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def summarize_segmentation(frame: pd.DataFrame) -> dict:
    required = {"participant_id", "stain", "cartilage_dice", "cartilage_iou", "cartilage_boundary_hd95_um", "catastrophic"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing segmentation columns: {sorted(missing)}")
    valid = frame[np.isfinite(pd.to_numeric(frame["cartilage_dice"], errors="coerce"))]
    participant = valid.groupby("participant_id", as_index=False).agg(
        cartilage_dice=("cartilage_dice", "mean"),
        cartilage_iou=("cartilage_iou", "mean"),
        cartilage_boundary_hd95_um=("cartilage_boundary_hd95_um", "median"),
    )
    return {
        "eligible_sections": len(frame),
        "valid_sections": len(valid),
        "validation_participants": int(frame["participant_id"].nunique()),
        "success_rate": float(len(valid) / len(frame)) if len(frame) else 0.0,
        "cartilage_dice": float(participant["cartilage_dice"].mean()) if len(participant) else float("nan"),
        "cartilage_iou": float(participant["cartilage_iou"].mean()) if len(participant) else float("nan"),
        "median_boundary_hd95_um": float(participant["cartilage_boundary_hd95_um"].median()) if len(participant) else float("inf"),
        "catastrophic_masks": int(frame["catastrophic"].astype(str).str.lower().isin({"true", "1"}).sum()),
    }


def generate_segmentation_report(frame: pd.DataFrame, output_dir: str | Path) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = summarize_segmentation(frame)
    by_stain = frame.groupby("stain", as_index=False).agg(
        sections=("participant_id", "size"),
        participants=("participant_id", "nunique"),
        cartilage_dice=("cartilage_dice", "mean"),
        cartilage_iou=("cartilage_iou", "mean"),
        median_boundary_hd95_um=("cartilage_boundary_hd95_um", "median"),
    )
    by_stain.to_csv(output / "table_segmentation_by_stain.csv", index=False)
    (output / "segmentation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    stains = sorted(frame["stain"].dropna().unique())
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), constrained_layout=True)
    axes[0].boxplot([frame.loc[frame["stain"] == stain, "cartilage_dice"].dropna() for stain in stains], tick_labels=stains)
    axes[0].axhline(0.90, color="#A33A2B", linestyle="--", linewidth=1)
    axes[0].set(ylabel="Cartilage Dice", title="Held-out participant masks")
    axes[1].boxplot([frame.loc[frame["stain"] == stain, "cartilage_boundary_hd95_um"].replace([np.inf, -np.inf], np.nan).dropna() for stain in stains], tick_labels=stains)
    axes[1].axhline(100, color="#A33A2B", linestyle="--", linewidth=1)
    axes[1].set(ylabel="Boundary HD95 (µm)", title="Physical boundary error")
    for suffix in ("png", "svg"):
        fig.savefig(output / f"figure_segmentation.{suffix}", dpi=300)
    plt.close(fig)
    return {**summary, "outputs": ["segmentation_summary.json", "table_segmentation_by_stain.csv", "figure_segmentation.png", "figure_segmentation.svg"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate held-out segmentation results and figure.")
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_segmentation_report(pd.read_csv(args.metrics), args.output), indent=2))


if __name__ == "__main__":
    main()
