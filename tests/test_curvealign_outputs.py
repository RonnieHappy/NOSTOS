from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nostos.validation.curvealign_outputs import (
    parse_ctfire_values,
    parse_curvealign_stats,
    parse_field_outputs,
)


def test_curvealign_stats_and_detected_fraction(tmp_path: Path) -> None:
    path = tmp_path / "field_stats.csv"
    path.write_text(
        "Coef of Alignment\t0.53\nred pixels\t10\nyellow pixels\t20\ngreen pixels\t30\ntotal pixels\t100\n",
        encoding="utf-8",
    )
    values = parse_curvealign_stats(path)
    assert values["coefficient_of_alignment"] == 0.53
    assert values["detected_pixel_fraction"] == 0.60


def test_ctfire_parser_ignores_header_and_rejects_empty(tmp_path: Path) -> None:
    path = tmp_path / "values.csv"
    path.write_text("width\n1.0\n2.0\n3.0\n", encoding="utf-8")
    assert np.array_equal(parse_ctfire_values(path), np.asarray([1.0, 2.0, 3.0]))
    empty = tmp_path / "empty.csv"
    empty.write_text("width\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_ctfire_values(empty)


def test_field_output_conversion_to_physical_units(tmp_path: Path) -> None:
    (tmp_path / "sample_stats.csv").write_text(
        "Coef of Alignment\t0.75\nred pixels\t5\nyellow pixels\t10\ngreen pixels\t5\ntotal pixels\t100\n",
        encoding="utf-8",
    )
    (tmp_path / "HistLEN_ctFIRE_sample.csv").write_text("10\n20\n30\n", encoding="utf-8")
    (tmp_path / "HistSTR_ctFIRE_sample.csv").write_text("0.8\n0.9\n1.0\n", encoding="utf-8")
    (tmp_path / "HistWID_ctFIRE_sample.csv").write_text("2\n4\n6\n", encoding="utf-8")
    output = parse_field_outputs(tmp_path, field_stem="sample", pixel_spacing_um=0.5)
    assert output["median_length_um"] == 10.0
    assert output["median_width_um"] == 2.0
    assert output["median_straightness"] == 0.9

