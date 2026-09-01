from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from nostos.evaluation.participant import assert_disjoint_participant_splits


FEATURE_PREFIXES = ("zsd_", "global_fft_", "texture_", "intensity_", "morphology_")


def build_participant_analysis_table(
    section_features: pd.DataFrame,
    metadata: pd.DataFrame,
    split_payload: dict,
) -> tuple[pd.DataFrame, dict]:
    required = {"participant_id", "stain", "site", "feature_success"}
    missing = required.difference(section_features.columns)
    if missing:
        raise ValueError(f"missing section-feature columns: {sorted(missing)}")
    splits = split_payload["splits"]
    assert_disjoint_participant_splits(splits)
    split_lookup = {str(participant).removeprefix("P").zfill(3): name for name, participants in splits.items() for participant in participants}
    features = section_features.copy()
    features["participant_id"] = features["participant_id"].astype(str).str.removeprefix("P").str.zfill(3)
    metadata = metadata.copy()
    metadata["participant_id"] = metadata["participant_id"].astype(str).str.removeprefix("P").str.zfill(3)
    success = features["feature_success"].astype(str).str.lower().isin({"true", "1"})
    numeric_columns = [column for column in features.columns if column.startswith(FEATURE_PREFIXES)]
    if not numeric_columns:
        raise ValueError("no frozen feature columns found")
    long = features.loc[success, ["participant_id", "stain", "site", *numeric_columns]].copy()
    for column in numeric_columns:
        long[column] = pd.to_numeric(long[column], errors="coerce")
    grouped = long.groupby(["participant_id", "stain", "site"], as_index=False)[numeric_columns].mean()
    melted = grouped.melt(id_vars=["participant_id", "stain", "site"], var_name="feature", value_name="value")
    melted["wide_name"] = melted["feature"] + "__stain_" + melted["stain"] + "__site_" + melted["site"]
    wide = melted.pivot(index="participant_id", columns="wide_name", values="value").reset_index()
    wide.columns.name = None
    table = metadata.merge(wide, on="participant_id", how="left", validate="one_to_one")
    table["split"] = table["participant_id"].map(split_lookup)
    if table["split"].isna().any():
        missing_ids = table.loc[table["split"].isna(), "participant_id"].tolist()
        raise ValueError(f"metadata participants missing from split file: {missing_ids}")
    counts = features.groupby("participant_id")["feature_success"].agg(
        eligible_section_count="size", valid_section_count=lambda values: values.astype(str).str.lower().isin({"true", "1"}).sum()
    ).reset_index()
    counts["valid_feature_rate"] = counts["valid_section_count"] / counts["eligible_section_count"]
    table = table.merge(counts, on="participant_id", how="left", validate="one_to_one")
    report = {
        "participants": len(table),
        "feature_columns": len([column for column in table if column.startswith(FEATURE_PREFIXES)]),
        "eligible_sections": int(counts["eligible_section_count"].sum()),
        "valid_sections": int(counts["valid_section_count"].sum()),
        "valid_feature_rate": float(counts["valid_section_count"].sum() / counts["eligible_section_count"].sum()),
        "split_counts": table["split"].value_counts().to_dict(),
    }
    return table, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Collapse section features to one participant-weighted analysis row.")
    parser.add_argument("section_features", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("splits", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    table, report = build_participant_analysis_table(
        pd.read_csv(args.section_features),
        pd.read_csv(args.metadata),
        json.loads(args.splits.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
