"""Audit PyRadiomics texture features against the official IBSI digital phantom.

The workbook is parsed read-only from OOXML so each reference retains its sheet
and cell provenance.  Only PyRadiomics' documented 3-D aggregation conventions
are compared; unsupported or definitionally different features are reported as
not comparable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

FAMILIES = {
    "glcm": "Co-occurrence matrix (3D, averaged)",
    "glrlm": "Run length matrix (3D, averaged)",
    "glszm": "Size zone matrix (3D)",
    "ngtdm": "Neighbourhood grey tone difference matrix (3D)",
    "gldm": "Neighbouring grey level dependence matrix (3D)",
}

# IBSI display name -> PyRadiomics feature name. Dissimilarity is intentionally
# absent because PyRadiomics marks it deprecated and does not calculate it.
MAP = {
    "glcm": {
        "Joint maximum": "MaximumProbability", "Joint average": "JointAverage",
        "Joint variance": "SumSquares", "Joint entropy": "JointEntropy",
        "Difference average": "DifferenceAverage", "Difference variance": "DifferenceVariance",
        "Difference entropy": "DifferenceEntropy", "Sum average": "SumAverage",
        "Sum variance": "ClusterTendency", "Sum entropy": "SumEntropy",
        "Angular second moment": "JointEnergy", "Contrast": "Contrast",
        "Inverse difference": "Id", "Normalised inverse difference": "Idn",
        "Inverse difference moment": "Idm", "Normalised inverse difference moment": "Idmn",
        "Inverse variance": "InverseVariance", "Correlation": "Correlation",
        "Autocorrelation": "Autocorrelation", "Cluster tendency": "ClusterTendency",
        "Cluster shade": "ClusterShade", "Cluster prominence": "ClusterProminence",
        "Information correlation 1": "Imc1", "Information correlation 2": "Imc2",
    },
    "glrlm": {
        "Short runs emphasis": "ShortRunEmphasis", "Long runs emphasis": "LongRunEmphasis",
        "Low grey level run emphasis": "LowGrayLevelRunEmphasis", "High grey level run emphasis": "HighGrayLevelRunEmphasis",
        "Short run low grey level emphasis": "ShortRunLowGrayLevelEmphasis", "Short run high grey level emphasis": "ShortRunHighGrayLevelEmphasis",
        "Long run low grey level emphasis": "LongRunLowGrayLevelEmphasis", "Long run high grey level emphasis": "LongRunHighGrayLevelEmphasis",
        "Grey level non-uniformity": "GrayLevelNonUniformity", "Normalised grey level non-uniformity": "GrayLevelNonUniformityNormalized",
        "Run length non-uniformity": "RunLengthNonUniformity", "Normalised run length non-uniformity": "RunLengthNonUniformityNormalized",
        "Run percentage": "RunPercentage", "Grey level variance": "GrayLevelVariance",
        "Run length variance": "RunVariance", "Run entropy": "RunEntropy",
    },
    "glszm": {
        "Small zone emphasis": "SmallAreaEmphasis", "Large zone emphasis": "LargeAreaEmphasis",
        "Low grey level emphasis": "LowGrayLevelZoneEmphasis", "High grey level emphasis": "HighGrayLevelZoneEmphasis",
        "Small zone low grey level emphasis": "SmallAreaLowGrayLevelEmphasis", "Small zone high grey level emphasis": "SmallAreaHighGrayLevelEmphasis",
        "Large zone low grey level emphasis": "LargeAreaLowGrayLevelEmphasis", "Large zone high grey level emphasis": "LargeAreaHighGrayLevelEmphasis",
        "Grey level non-uniformity": "GrayLevelNonUniformity", "Normalised grey level non-uniformity": "GrayLevelNonUniformityNormalized",
        "Zone size non-uniformity": "SizeZoneNonUniformity", "Normalised zone size non-uniformity": "SizeZoneNonUniformityNormalized",
        "Zone percentage": "ZonePercentage", "Grey level variance": "GrayLevelVariance",
        "Zone size variance": "ZoneVariance", "Zone size entropy": "ZoneEntropy",
    },
    "ngtdm": {x: x for x in ("Coarseness", "Contrast", "Busyness", "Complexity", "Strength")},
    "gldm": {
        "Low dependence emphasis": "SmallDependenceEmphasis", "High dependence emphasis": "LargeDependenceEmphasis",
        "Low grey level count emphasis": "LowGrayLevelEmphasis", "High grey level count emphasis": "HighGrayLevelEmphasis",
        "Low dependence low grey level emphasis": "SmallDependenceLowGrayLevelEmphasis", "Low dependence high grey level emphasis": "SmallDependenceHighGrayLevelEmphasis",
        "High dependence low grey level emphasis": "LargeDependenceLowGrayLevelEmphasis", "High dependence high grey level emphasis": "LargeDependenceHighGrayLevelEmphasis",
        "Grey level non-uniformity": "GrayLevelNonUniformity", "Normalised grey level non-uniformity": "GrayLevelNonUniformityNormalized",
        "Dependence count non-uniformity": "DependenceNonUniformity", "Normalised dependence count non-uniformity": "DependenceNonUniformityNormalized",
        "Dependence count percentage": None, "Grey level variance": "GrayLevelVariance",
        "Dependence count variance": "DependenceVariance", "Dependence count entropy": "DependenceEntropy",
        "Dependence count energy": None,
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def workbook_rows(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in shared_root.findall(NS + "si")]
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    output = []
    for row in root.iter(NS + "row"):
        values = {}
        for cell in row.findall(NS + "c"):
            column = re.match(r"[A-Z]+", cell.attrib["r"]).group()
            node = cell.find(NS + "v")
            value = "" if node is None else node.text
            if cell.attrib.get("t") == "s" and value:
                value = shared[int(value)]
            values[column] = value
        if values.get("A") == "digital phantom":
            output.append({"row": int(row.attrib["r"]), "family": values.get("B"), "feature": values.get("C"),
                           "reference": float(values["E"]) if values.get("E") else None,
                           "tolerance": float(values["F"]) if values.get("F") else None,
                           "tag": values.get("J")})
    return output


def main() -> None:
    import radiomics
    from radiomics import featureextractor

    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--workbook-url", required=True)
    parser.add_argument("--ibsi-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    extractor = featureextractor.RadiomicsFeatureExtractor(binWidth=1, distances=[1], force2D=False)
    extractor.disableAllFeatures()
    for family in FAMILIES:
        extractor.enableFeatureClassByName(family)
    raw = extractor.execute(str(args.image), str(args.mask))
    refs = workbook_rows(args.workbook)
    results = []
    for family, ibsi_family in FAMILIES.items():
        for row in (r for r in refs if r["family"] == ibsi_family):
            py_name = MAP[family].get(row["feature"])
            key = f"original_{family}_{py_name}" if py_name else None
            if not key or key not in raw:
                results.append({**row, "sheet": "digital phantom", "reference_cell": f"E{row['row']}",
                                "pyradiomics_feature": key, "status": "not_comparable",
                                "reason": "unsupported or no definitionally equivalent emitted feature"})
                continue
            observed = float(raw[key])
            # Workbook tolerance is zero for the exact phantom. Published values
            # are rounded, so compare at the significant precision represented.
            passed = float(f"{observed:.3g}") == float(f"{row['reference']:.3g}")
            results.append({**row, "sheet": "digital phantom", "reference_cell": f"E{row['row']}",
                            "pyradiomics_feature": key, "observed": observed,
                            "comparison": "three_significant_digits", "status": "pass" if passed else "fail"})
    counts = {status: sum(r["status"] == status for r in results) for status in ("pass", "fail", "not_comparable")}
    payload = {
        "protocol_version": "nostos-pyradiomics-ibsi-texture/1.0",
        "status": "pass" if counts["fail"] == 0 and counts["pass"] else "fail",
        "implementation": "PyRadiomics", "pyradiomics_version": radiomics.__version__,
        "ibsi_data_commit": args.ibsi_commit,
        "reference_workbook": {"url": args.workbook_url, "sha256": sha256(args.workbook),
                               "worksheet": "digital phantom", "parser": "stdlib OOXML read-only"},
        "settings": {"binWidth": 1, "distances": [1], "force2D": False,
                     "aggregation": "PyRadiomics default; matched to IBSI 3D averaged or 3D matrix by family"},
        "scope": "IBSI digital phantom texture families emitted with equivalent 3D conventions",
        "counts": counts, "features": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
