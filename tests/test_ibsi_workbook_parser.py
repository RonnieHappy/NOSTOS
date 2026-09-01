from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path


def _module(project_root: Path):
    path = project_root / "scripts" / "benchmark_pyradiomics_ibsi_texture.py"
    spec = importlib.util.spec_from_file_location("ibsi_texture_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workbook_parser_preserves_reference_provenance(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    module = _module(project_root)
    workbook = tmp_path / "reference.xlsx"
    shared = """<?xml version='1.0' encoding='UTF-8'?>
    <sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
      <si><t>digital phantom</t></si><si><t>Size zone matrix (3D)</t></si>
      <si><t>Zone percentage</t></si><si><t>szm_z_perc_3D</t></si>
    </sst>"""
    sheet = """<?xml version='1.0' encoding='UTF-8'?>
    <worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>
      <row r='371'><c r='A371' t='s'><v>0</v></c><c r='B371' t='s'><v>1</v></c>
      <c r='C371' t='s'><v>2</v></c><c r='E371'><v>0.0676</v></c>
      <c r='F371'><v>0</v></c><c r='J371' t='s'><v>3</v></c></row>
    </sheetData></worksheet>"""
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", shared)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    assert module.workbook_rows(workbook) == [{
        "row": 371, "family": "Size zone matrix (3D)", "feature": "Zone percentage",
        "reference": 0.0676, "tolerance": 0.0, "tag": "szm_z_perc_3D",
    }]
