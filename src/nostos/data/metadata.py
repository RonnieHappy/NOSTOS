from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pandas as pd

from .audit import infer_participant_id


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


CANONICAL_ALIASES = {
    "age": ("age", "patientage"),
    "sex": ("sex", "gender", "patientgender"),
    # The public repository stores laterality in <TKA value="Left|Right">.
    "surgery_side": ("surgeryside", "tka", "tkaside", "totalkneearthroplastyside"),
    "mean_total_hhgs": ("meantotalhhgsscore", "meanhhgsscore", "hhgsmean"),
    "mean_total_oarsi": ("meantotaloarsiscore", "meanoarsiscore", "oarsimean"),
    "mean_total_plm": ("meantotalplmscore", "meanplmscore", "plmscore", "plmmean"),
}


def flatten_xml(path: str | Path) -> dict[str, str]:
    root = ElementTree.parse(path).getroot()
    values: dict[str, str] = {}
    for element in root.iter():
        text = (element.text or "").strip()
        value = element.attrib.get("value", text).strip()
        if value:
            values[normalize_key(element.tag)] = value
        for name, attribute in element.attrib.items():
            if name != "value" and attribute:
                values[normalize_key(f"{element.tag}_{name}")] = attribute.strip()
    return values


def canonicalize_metadata(values: dict[str, str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        matches = [values[alias] for alias in aliases if alias in values]
        result[canonical] = matches[0] if matches else None
    for numeric in ("age", "mean_total_hhgs", "mean_total_oarsi", "mean_total_plm"):
        if result[numeric] not in (None, ""):
            result[numeric] = float(str(result[numeric]))
    return result


def validate_metadata_row(row: dict[str, object]) -> list[str]:
    errors = []
    ranges = {"age": (18, 100), "mean_total_hhgs": (0, 14), "mean_total_oarsi": (0, 24), "mean_total_plm": (0, 8)}
    for name, (lower, upper) in ranges.items():
        value = row.get(name)
        if value is not None and not lower <= float(value) <= upper:
            errors.append(f"{name} outside [{lower}, {upper}]: {value}")
    return errors


def ingest_metadata(root: str | Path) -> tuple[pd.DataFrame, dict]:
    root = Path(root).resolve()
    rows, errors = [], []
    for path in sorted(root.rglob("metadata.xml")):
        participant = infer_participant_id(path, root)
        try:
            raw = flatten_xml(path)
            row = {"participant_id": participant, "metadata_path": path.relative_to(root).as_posix(), **canonicalize_metadata(raw)}
            row_errors = validate_metadata_row(row)
            row["metadata_valid"] = not row_errors
            row["metadata_errors"] = " | ".join(row_errors)
            errors.extend(f"{participant}: {error}" for error in row_errors)
            rows.append(row)
        except (ElementTree.ParseError, ValueError) as error:
            errors.append(f"{path.relative_to(root)}: {type(error).__name__}: {error}")
    frame = pd.DataFrame(rows)
    missingness = {column: int(frame[column].isna().sum()) for column in frame.columns} if not frame.empty else {}
    report = {"metadata_files": len(rows), "valid_rows": int(frame.get("metadata_valid", pd.Series(dtype=bool)).sum()), "missingness": missingness, "errors": errors}
    return frame, report


def ingest_score_csvs(root: str | Path) -> tuple[pd.DataFrame, dict]:
    """Losslessly concatenate raw per-specimen scorer tables and inventory schemas."""
    root = Path(root).resolve()
    frames, schemas, errors = [], {}, []
    candidates = sorted(path for path in root.rglob("*.csv") if "data_summary" in path.name.lower())
    for path in candidates:
        participant = infer_participant_id(path, root)
        site = "Medial" if "medial" in path.name.lower() else "Lateral" if "lateral" in path.name.lower() else "unknown"
        try:
            frame = pd.read_csv(path)
            normalized = [normalize_key(column) for column in frame.columns]
            if len(set(normalized)) != len(normalized):
                raise ValueError("column names collide after normalization")
            frame.columns = normalized
            frame.insert(0, "source_row", range(1, len(frame) + 1))
            frame.insert(0, "source_csv", path.relative_to(root).as_posix())
            frame.insert(0, "site", site)
            frame.insert(0, "participant_id", participant)
            schema_key = "|".join(normalized)
            schemas.setdefault(schema_key, {"columns": normalized, "files": 0, "rows": 0})
            schemas[schema_key]["files"] += 1
            schemas[schema_key]["rows"] += len(frame)
            frames.append(frame)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            errors.append(f"{path.relative_to(root)}: {type(error).__name__}: {error}")
    combined = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    return combined, {"score_csv_files": len(candidates), "rows": len(combined), "schema_variants": list(schemas.values()), "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest participant metadata without silently coercing outcomes.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frame, report = ingest_metadata(args.root)
    scores, score_report = ingest_score_csvs(args.root)
    report["score_tables"] = score_report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    scores.to_csv(args.output.with_name(args.output.stem + ".scores_raw.csv"), index=False)
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
