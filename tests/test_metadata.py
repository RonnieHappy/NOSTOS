from pathlib import Path

from nostos.data.metadata import canonicalize_metadata, flatten_xml, ingest_metadata, ingest_score_csvs


def test_metadata_xml_is_canonicalized_and_range_checked(tmp_path: Path):
    folder = tmp_path / "P001"
    folder.mkdir()
    path = folder / "metadata.xml"
    path.write_text(
        '<metadata><patient_age value="62"/><gender value="Female"/><surgery_side value="Left"/>'
        '<mean_total_HHGS_score value="5.0"/><mean_total_OARSI_score value="6.5"/>'
        '<mean_total_PLM_score value="3.0"/></metadata>', encoding="utf-8"
    )
    canonical = canonicalize_metadata(flatten_xml(path))
    assert canonical["age"] == 62
    assert canonical["mean_total_plm"] == 3
    frame, report = ingest_metadata(tmp_path)
    assert frame.loc[0, "participant_id"] == "001"
    assert report["valid_rows"] == 1


def test_raw_score_csvs_are_inventoried_without_guessing_columns(tmp_path: Path):
    folder = tmp_path / "P002"
    folder.mkdir()
    (folder / "medial_data_summary.csv").write_text("Scorer,Read,PLM SZ\n1,1,2\n2,1,3\n", encoding="utf-8")
    frame, report = ingest_score_csvs(tmp_path)
    assert len(frame) == 2
    assert frame.loc[0, "site"] == "Medial"
    assert "plmsz" in frame.columns
    assert report["score_csv_files"] == 1
