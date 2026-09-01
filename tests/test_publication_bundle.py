from pathlib import Path
from nostos.reporting.publication_bundle import OUTCOMES, _sha256

def test_sha256_is_content_stable(tmp_path: Path) -> None:
    path = tmp_path / "artifact.txt"; path.write_text("NOSTOS", encoding="utf-8")
    assert len(_sha256(path)) == 64 and _sha256(path) == _sha256(path)

def test_all_manuscript_outcomes_have_labels() -> None:
    assert set(OUTCOMES.values()) == {"PLM", "OARSI", "HHGS"}
