import json
import zipfile
from pathlib import Path

from nostos.release import build_release


def test_release_is_data_free_sanitized_and_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "outputs/nostos0-evidence-bundle-v1").mkdir(parents=True)
    (root / "src/example.py").write_text("ROOT = r'<DATA_ROOT>\\data'\n", encoding="utf-8")
    (root / "README.md").write_text("project\n", encoding="utf-8")
    (root / "LICENSE").write_text("license\n", encoding="utf-8")
    index = {"entries": [], "nature_readiness": "not_ready"}
    (root / "outputs/nostos0-evidence-bundle-v1/evidence_index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )
    first = build_release(root, tmp_path / "release-a")
    second = build_release(root, tmp_path / "release-b")
    assert first["archive_sha256"] == second["archive_sha256"]
    archive = tmp_path / "release-a/nostos-0.3.0-release-candidate.zip"
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert not any("data/" in name for name in names)
        source = bundle.read("nostos-0.3.0/src/example.py").decode()
        assert "<DATA_ROOT>" not in source
        manifest = json.loads(bundle.read("nostos-0.3.0/release_manifest.json"))
        assert manifest["status"] == "pass"
