from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from nostos.modeling.ablations import derive_feature_contract


def resolve_config(config: dict, *, config_path: Path) -> dict:
    """Resolve environment placeholders and project-relative paths portably."""
    project_root = config_path.resolve().parent.parent
    resolved: dict[str, str] = {}
    for key, value in config.items():
        expanded = os.path.expandvars(str(value))
        if "${" in expanded:
            raise ValueError(f"unresolved environment variable in {key}: {value}")
        path = Path(expanded)
        resolved[key] = str(path if path.is_absolute() else project_root / path)
    return resolved


def pipeline_commands(config: dict, *, python: str = sys.executable, unlock_test: bool = False) -> list[list[str]]:
    commands = [
        [python, "-m", "nostos.data.audit", config["raw_root"], "--output", config["dataset_manifest"]],
        [python, "-m", "nostos.data.metadata", config["raw_root"], "--output", config["metadata"]],
        [python, "-m", "nostos.data.split", config["dataset_manifest"], "--output", config["splits"]],
        [python, "-m", "nostos.features.section", config["annotation_manifest"], "--pixel-sizes", config["pixel_sizes"], "--output", config["section_features"]],
        [python, "-m", "nostos.data.analysis_table", config["section_features"], config["metadata"], config["splits"], "--output", config["analysis_table"]],
    ]
    if unlock_test:
        commands.extend([
            [python, "-m", "nostos.modeling.locked_analysis", config["analysis_table"], config["feature_contract"], "--outcome", "mean_total_plm", "--output", config["locked_output"], "--confirm-first-locked-evaluation"],
            [python, "-m", "nostos.reporting.primary", str(Path(config["locked_output"]) / "locked_predictions.csv"), "--output", config["report_output"]],
            [python, "-m", "nostos.reporting.ablations", str(Path(config["locked_output"]) / "locked_ablation_predictions.csv"), "--output", config["report_output"]],
        ])
    commands.append([python, "-m", "nostos.reporting.cohort", config["metadata"], "--output", config["report_output"]])
    return commands


def write_feature_contract(analysis_table: Path, destination: Path) -> dict[str, list[str]]:
    columns = pd.read_csv(analysis_table, nrows=0).columns.tolist()
    contract = derive_feature_contract(columns)
    empty = [name for name, values in contract.items() if not values]
    if empty:
        raise ValueError(f"empty feature sets cannot be locked: {empty}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the versioned NOSTOS pilot dependency chain.")
    parser.add_argument("--config", type=Path, default=Path("configs/pipeline.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-first-locked-evaluation", action="store_true")
    args = parser.parse_args()
    config = resolve_config(json.loads(args.config.read_text(encoding="utf-8")), config_path=args.config)
    commands = pipeline_commands(config, unlock_test=args.confirm_first_locked_evaluation)
    if args.dry_run:
        print(json.dumps({"locked_test_included": args.confirm_first_locked_evaluation, "commands": commands}, indent=2))
        return
    for index, command in enumerate(commands):
        # Freeze the feature contract immediately after the participant table and before any locked access.
        if index == 5 and args.confirm_first_locked_evaluation:
            write_feature_contract(Path(config["analysis_table"]), Path(config["feature_contract"]))
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
