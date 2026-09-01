from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _evenly_spaced_participants(metadata: pd.DataFrame, candidates: list[str], count: int) -> list[str]:
    selected = metadata[metadata["participant_id"].isin(candidates)].copy()
    selected["mean_total_plm"] = pd.to_numeric(selected["mean_total_plm"], errors="coerce")
    selected = selected.sort_values(["mean_total_plm", "participant_id"], na_position="last")
    if len(selected) < count:
        raise ValueError(f"requested {count} participants but only {len(selected)} are available")
    indices = np.linspace(0, len(selected) - 1, count).round().astype(int)
    return selected.iloc[indices]["participant_id"].astype(str).tolist()


def select_annotation_images(
    dataset_manifest: dict,
    metadata: pd.DataFrame,
    split_payload: dict,
    *,
    training_participants: int = 24,
    validation_participants: int = 8,
) -> tuple[pd.DataFrame, dict]:
    metadata = metadata.copy()
    metadata["participant_id"] = metadata["participant_id"].astype(str).str.removeprefix("P").str.zfill(3)
    splits = {name: [str(value).removeprefix("P").zfill(3) for value in values] for name, values in split_payload["splits"].items()}
    train_ids = _evenly_spaced_participants(metadata, splits["train"], training_participants)
    validation_ids = _evenly_spaced_participants(metadata, splits["validation"], validation_participants)
    records = pd.DataFrame(dataset_manifest["records"])
    records["participant_id"] = records["participant_id"].astype(str).str.zfill(3)
    records = records[records["modality"].isin(["HE", "SafO", "PLM"]) & records["site"].isin(["Medial", "Lateral"])]
    records = records.sort_values("relative_path").drop_duplicates(["participant_id", "modality", "site"])
    root = Path(dataset_manifest["dataset_root"])
    rows = []
    brightfield_cycle = [("HE", "Medial"), ("HE", "Lateral"), ("SafO", "Medial"), ("SafO", "Lateral")]
    for cohort, identifiers in (("train", train_ids), ("validation", validation_ids)):
        for index, participant in enumerate(identifiers):
            if cohort == "train":
                desired = [("PLM", "Medial"), brightfield_cycle[index % 4], brightfield_cycle[(index + 2) % 4]]
            else:
                desired = [("HE", "Medial"), ("HE", "Lateral"), ("SafO", "Medial"), ("SafO", "Lateral"), ("PLM", "Medial")]
            for modality, site in desired:
                matched = records[(records["participant_id"] == participant) & (records["modality"] == modality) & (records["site"] == site)]
                if matched.empty:
                    raise ValueError(f"missing {participant} {site} {modality} image")
                record = matched.iloc[0]
                rows.append({
                    "participant_id": participant,
                    "specimen_id": f"{site}_{modality}",
                    "site": site,
                    "stain": modality,
                    "split": cohort,
                    "image_path": str((root / record["relative_path"]).resolve()),
                    "pixel_size_um": record["pixel_size_um_x"],
                })
    selection = pd.DataFrame(rows)
    report = {
        "training_participants": len(train_ids),
        "validation_participants": len(validation_ids),
        "training_images": int((selection["split"] == "train").sum()),
        "validation_images": int((selection["split"] == "validation").sum()),
        "stain_counts": selection["stain"].value_counts().to_dict(),
        "site_counts": selection["site"].value_counts().to_dict(),
        "morphology_test_participants_used": len(set(selection["participant_id"]).intersection(splits["test"])),
    }
    return selection, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock disease-range and modality-balanced segmentation annotations.")
    parser.add_argument("dataset_manifest", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("splits", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selection, report = select_annotation_images(
        json.loads(args.dataset_manifest.read_text(encoding="utf-8")),
        pd.read_csv(args.metadata),
        json.loads(args.splits.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    selection.to_csv(args.output, index=False)
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
