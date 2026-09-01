from __future__ import annotations

import pandas as pd

from .grouped_ridge import locked_ridge_predictions


PREFIXES = {
    "global_fft": ("global_fft_",),
    "intensity_morphology": ("intensity_", "morphology_"),
    "texture": ("texture_",),
    "zsd": ("zsd_",),
}


def derive_feature_contract(columns: list[str]) -> dict[str, list[str]]:
    contract = {
        name: sorted(column for column in columns if column.startswith(prefixes))
        for name, prefixes in PREFIXES.items()
    }
    contract["zsd_plus_conventional"] = sorted(
        set(contract["zsd"] + contract["intensity_morphology"] + contract["texture"])
    )
    contract["all_morphology"] = sorted(set(sum(contract.values(), [])))
    return contract


def run_prespecified_ablations(
    table: pd.DataFrame,
    *,
    outcome: str,
    feature_sets: dict[str, list[str]],
) -> pd.DataFrame:
    """Evaluate frozen feature and stain/site ablations in the same locked test event."""
    rows: list[dict] = []
    if "valid_section_count" in table:
        table = table[pd.to_numeric(table["valid_section_count"], errors="coerce").fillna(0) > 0].copy()
    table = table[pd.to_numeric(table[outcome], errors="coerce").notna()].copy()
    analyses: list[tuple[str, str, dict[str, list[str]]]] = [("overall", "all", feature_sets)]
    zsd = feature_sets["zsd"]
    for stain in ("HE", "SafO", "PLM"):
        selected = [column for column in zsd if f"__stain_{stain}__" in column]
        if selected:
            analyses.append(("stain", stain, {"zsd": selected}))
    for site in ("Medial", "Lateral"):
        selected = [column for column in zsd if f"__site_{site}" in column]
        if selected:
            analyses.append(("site", site, {"zsd": selected}))
    development = table[table["split"].isin(["train", "validation"])]
    test = table[table["split"] == "test"]
    for stratum_type, stratum_value, selected_models in analyses:
        if development["participant_id"].nunique() < 3 or test["participant_id"].nunique() < 1:
            continue
        for model_name, columns in selected_models.items():
            if not columns:
                continue
            result = locked_ridge_predictions(
                development[columns].to_numpy(float),
                development[outcome].to_numpy(float),
                development["participant_id"].to_numpy(str),
                test[columns].to_numpy(float),
                test[outcome].to_numpy(float),
                test["participant_id"].to_numpy(str),
            )
            for participant, observed, predicted in zip(result.participant_ids, result.observed, result.predicted):
                rows.append({
                    "stratum_type": stratum_type,
                    "stratum_value": stratum_value,
                    "model": model_name,
                    "participant_id": participant,
                    "observed": observed,
                    "predicted": predicted,
                    "selected_alpha": result.selected_alpha,
                })
    return pd.DataFrame(rows)
