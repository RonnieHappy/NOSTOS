import json
import zipfile
from pathlib import Path

import pytest

import nostos.release as release_module
from nostos.release import build_release


def test_release_is_data_free_sanitized_and_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src/nostos/data").mkdir(parents=True)
    (root / "outputs/nostos0-evidence-bundle-v30").mkdir(parents=True)
    release_output = root / "outputs/nostos0-release-candidate-v30"
    release_output.mkdir(parents=True)
    separator = chr(92)
    private_root = "E:" + separator + "NOSTOS"
    (root / "src/example.py").write_text(
        f"ROOT = r'{private_root}{separator}data'\n", encoding="utf-8"
    )
    (root / "src/nostos/data/__init__.py").write_text(
        '"""Public source package; not research input data."""\n', encoding="utf-8"
    )
    (root / "src/escaped.json").write_text(
        json.dumps(
            {
                "project": str(root),
                "data": f"{private_root}{separator}data",
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("project\n", encoding="utf-8")
    (root / "LICENSE").write_text("license\n", encoding="utf-8")
    receipt = release_output / "release_receipt.json"
    receipt.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    index = {
        "entries": [{"path": "outputs/nostos0-release-candidate-v30/release_receipt.json"}],
        "nature_readiness": "not_ready",
    }
    (root / "outputs/nostos0-evidence-bundle-v30/evidence_index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )
    first = build_release(root, tmp_path / "release-a")
    second = build_release(root, tmp_path / "release-b")
    assert first["archive_sha256"] == second["archive_sha256"]
    archive = tmp_path / "release-a/nostos-0.3.0-release-candidate.zip"
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert not any(name.startswith("nostos-0.3.0/data/") for name in names)
        assert "nostos-0.3.0/src/nostos/data/__init__.py" in names
        assert not any(name.endswith("release_receipt.json") for name in names)
        source = bundle.read("nostos-0.3.0/src/example.py").decode()
        assert private_root not in source
        assert "<DATA_ROOT>" in source
        escaped = bundle.read("nostos-0.3.0/src/escaped.json").decode()
        assert "Users" not in escaped
        assert "NOSTOS" not in escaped
        assert "<PROJECT_ROOT>" in escaped
        assert "<DATA_ROOT>" in escaped
        manifest = json.loads(bundle.read("nostos-0.3.0/release_manifest.json"))
        assert manifest["status"] == "pass"


def test_release_cleans_staging_directory_after_copy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src/example.py").write_text("VALUE = 1\n", encoding="utf-8")
    output = tmp_path / "release-output"

    def fail_copy(*args, **kwargs):
        raise OSError("simulated staging failure")

    monkeypatch.setattr(release_module, "_copy_file", fail_copy)
    with pytest.raises(OSError, match="simulated staging failure"):
        build_release(root, output)

    work_root = output.parent / ".nostos-release-tmp"
    assert not work_root.exists()
