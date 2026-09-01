"""Parsers for official CurveAlign and CT-FIRE command-line outputs."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


def parse_curvealign_stats(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            fields = [field.strip() for field in row if field.strip()]
            if len(fields) != 2:
                continue
            try:
                values[fields[0].casefold()] = float(fields[1])
            except ValueError:
                continue
    required = {"coef of alignment", "red pixels", "yellow pixels", "green pixels", "total pixels"}
    missing = sorted(required - set(values))
    if missing:
        raise ValueError(f"CurveAlign statistics are missing {missing}: {path}")
    total = values["total pixels"]
    if not np.isfinite(total) or total <= 0:
        raise ValueError(f"CurveAlign total-pixel count is invalid: {path}")
    detected = values["red pixels"] + values["yellow pixels"] + values["green pixels"]
    return {
        "coefficient_of_alignment": float(values["coef of alignment"]),
        "detected_pixel_fraction": float(detected / total),
        "detected_pixels": float(detected),
        "total_pixels": float(total),
    }


def parse_ctfire_values(path: Path) -> np.ndarray:
    values: list[float] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row or not row[0].strip():
                continue
            try:
                value = float(row[0])
            except ValueError:
                continue
            if np.isfinite(value):
                values.append(value)
    if not values:
        raise ValueError(f"CT-FIRE output contains no finite values: {path}")
    return np.asarray(values, dtype=float)


def _one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected one {pattern!r} below {root}; found {len(matches)}.")
    return matches[0]


def parse_field_outputs(
    root: Path,
    *,
    field_stem: str,
    pixel_spacing_um: float,
    curvealign_root: Path | None = None,
    ctfire_root: Path | None = None,
) -> dict[str, object]:
    if not np.isfinite(pixel_spacing_um) or pixel_spacing_um <= 0:
        raise ValueError("pixel_spacing_um must be finite and positive.")
    ca_search = curvealign_root if curvealign_root is not None else root
    ctfire_search = ctfire_root if ctfire_root is not None else root
    stats_path = _one(ca_search, f"{field_stem}_stats.csv")
    length_path = _one(ctfire_search, f"HistLEN_ctFIRE_{field_stem}.csv")
    straightness_path = _one(ctfire_search, f"HistSTR_ctFIRE_{field_stem}.csv")
    width_path = _one(ctfire_search, f"HistWID_ctFIRE_{field_stem}.csv")
    stats = parse_curvealign_stats(stats_path)
    length = parse_ctfire_values(length_path)
    straightness = parse_ctfire_values(straightness_path)
    width = parse_ctfire_values(width_path)
    return {
        "field_stem": field_stem,
        "coefficient_of_alignment": stats["coefficient_of_alignment"],
        "detected_pixel_fraction": stats["detected_pixel_fraction"],
        "median_length_pixels": float(np.median(length)),
        "median_length_um": float(np.median(length) * pixel_spacing_um),
        "median_straightness": float(np.median(straightness)),
        "median_width_pixels": float(np.median(width)),
        "median_width_um": float(np.median(width) * pixel_spacing_um),
        "fiber_counts": {
            "length": int(length.size),
            "straightness": int(straightness.size),
            "width": int(width.size),
        },
        "source_files": {
            "curvealign_stats": str(stats_path),
            "ctfire_length": str(length_path),
            "ctfire_straightness": str(straightness_path),
            "ctfire_width": str(width_path),
        },
    }


__all__ = ["parse_ctfire_values", "parse_curvealign_stats", "parse_field_outputs"]
