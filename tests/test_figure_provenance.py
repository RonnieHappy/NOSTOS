from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_figure1_is_traceable_and_non_generative() -> None:
    manifest_path = ROOT / "figures/nostos0/figure_1_response_geometry_reference.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "generated_from_traceable_sources"
    assert manifest["generative_imagery"] is False
    assert set(manifest["panels"]) == {"a", "b", "c", "d"}
    assert len(manifest["sources"]) == 13
    assert all(len(item["sha256"]) == 64 for item in manifest["sources"])
    for output in manifest["outputs"].values():
        path = ROOT / output["path"]
        assert path.is_file()
        assert _sha256(path) == output["sha256"]
