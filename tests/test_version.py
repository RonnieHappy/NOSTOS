from pathlib import Path
import tomllib

import nostos


def test_runtime_version_matches_project_metadata():
    project = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert nostos.__version__ == project["project"]["version"]
