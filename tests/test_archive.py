from pathlib import Path
import zipfile

import pytest

from nostos.data.archive import extract_transactionally, identify_archive, validate_archive


def test_zip_is_validated_and_extracted_transactionally(tmp_path: Path):
    archive = tmp_path / "data.part"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("P001/metadata.xml", "<metadata/>")
    assert identify_archive(archive) == "zip"
    assert validate_archive(archive)["member_count"] == 1
    destination = tmp_path / "raw"
    receipt = extract_transactionally(archive, destination)
    assert (destination / "P001" / "metadata.xml").is_file()
    assert len(receipt["archive_sha256"]) == 64


def test_archive_path_traversal_is_rejected(tmp_path: Path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape.txt", "unsafe")
    with pytest.raises(ValueError, match="unsafe"):
        validate_archive(archive)
