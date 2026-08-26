from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .grouped_ridge import locked_ridge_predictions
from .ablations import run_prespecified_ablations


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def run_locked_analysis(
    table: pd.DataFrame,
    *,
    outcome: str,
    feature_sets: dict[str, list[str]],
) -> tuple[pd.DataFrame, dict]:
    required = {"participant_id", "split", outcome}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"missing locked-analysis columns: {sorted(missing)}")
    invalid = set(table["split"].unique()).difference({"train", "validation", "test"})
    if invalid:
        raise ValueError(f"unsupported split values: {sorted(invalid)}")
    eligible_rows = len(table)
    if "valid_section_count" in table:
        table = table[pd.to_numeric(table["valid_section_count"], errors="coerce").fillna(0) > 0].copy()
    table = table[pd.to_numeric(table[outcome], errors="coerce").notna()].copy()
    valid_rows = len(table)
    development = table[table["split"].isin(["train", "validation"])].copy()
    test = table[table["split"] == "test"].copy()
    if development.empty or test.empty:
        raise ValueError("both development and locked-test rows are required")
    output = test.loc[:, ["participant_id", outcome]].rename(columns={outcome: "observed"}).copy()
    receipt: dict[str, object] = {
        "outcome": outcome,
        "eligible_participants": eligible_rows,
        "valid_participants": valid_rows,
        "participant_no_answer_rate": 1.0 - valid_rows / eligible_rows if eligible_rows else 1.0,
        "development_participants": int(development["participant_id"].nunique()),
        "test_participants": int(test["participant_id"].nunique()),
        "models": {},
    }
    for model_name, columns in feature_sets.items():
        absent = set(columns).difference(table.columns)
        if absent or not columns:
            raise ValueError(f"invalid columns for {model_name}: {sorted(absent) if absent else 'empty'}")
        result = locked_ridge_predictions(
            development[columns].to_numpy(float),
            development[outcome].to_numpy(float),
            development["participant_id"].to_numpy(str),
            test[columns].to_numpy(float),
            test[outcome].to_numpy(float),
            test["participant_id"].to_numpy(str),
        )
        output[model_name] = result.predicted
        receipt["models"][model_name] = {"features": columns, "selected_alpha": result.selected_alpha}
    return output, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Perform the one-time participant-locked analysis.")
    parser.add_argument("table", type=Path)
    parser.add_argument("feature_contract", type=Path, help="JSON mapping model names to frozen feature columns")
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-first-locked-evaluation", action="store_true")
    args = parser.parse_args()
    if not args.confirm_first_locked_evaluation:
        parser.error("locked evaluation requires --confirm-first-locked-evaluation")
    predictions_path = args.output / "locked_predictions.csv"
    ablations_path = args.output / "locked_ablation_predictions.csv"
    receipt_path = args.output / "locked_receipt.json"
    if predictions_path.exists() or ablations_path.exists() or receipt_path.exists():
        raise FileExistsError("locked results already exist; refusing to overwrite or re-evaluate")
    contract = json.loads(args.feature_contract.read_text(encoding="utf-8"))
    table = pd.read_csv(args.table)
    predictions, receipt = run_locked_analysis(table, outcome=args.outcome, feature_sets=contract)
    ablations = run_prespecified_ablations(table, outcome=args.outcome, feature_sets=contract)
    args.output.mkdir(parents=True, exist_ok=True)
    receipt.update({"table_sha256": _sha256(args.table), "feature_contract_sha256": _sha256(args.feature_contract)})
    predictions.to_csv(predictions_path, index=False)
    ablations.to_csv(ablations_path, index=False)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
