from pathlib import Path

import numpy as np
import tifffile

from nostos.data.audit import build_manifest, infer_participant_id, infer_site, read_tiff_header


def test_tiff_header_reads_geometry_and_physical_resolution(tmp_path: Path) -> None:
    path = tmp_path / "image.tif"
    tifffile.imwrite(
        path,
        np.zeros((40, 60), dtype=np.uint16),
        resolution=(10_000 / 2.0, 10_000 / 2.0),
        resolutionunit="CENTIMETER",
    )
    header = read_tiff_header(path)
    assert header["height_pixels"] == 40
    assert header["width_pixels"] == 60
    assert header["dtype"] == "uint16"
    assert abs(header["pixel_size_um_x"] - 2.0) < 1e-6
    assert header["pixel_size_source"] == "tiff_resolution_tags"


def test_participant_id_matches_repository_folder_names(tmp_path: Path) -> None:
    path = tmp_path / "P092" / "Medial" / "HE" / "section.tif"
    assert infer_participant_id(path, tmp_path) == "092"
    assert infer_site(path) == "Medial"


def test_repository_scale_overrides_nominal_dpi_tag(tmp_path: Path) -> None:
    root = tmp_path
    (root / "image_information.xml").write_text(
        '<image_information><HE_Image_scale type="float" unit="microns_per_pixel" value="1.72"/></image_information>',
        encoding="utf-8",
    )
    image = root / "P001" / "Medial" / "HE" / "section.tif"
    image.parent.mkdir(parents=True)
    tifffile.imwrite(image, np.zeros((40, 60), dtype=np.uint8), resolution=(72, 72), resolutionunit="INCH")
    manifest = build_manifest(root)
    assert manifest["participant_count"] == 1
    assert manifest["records"][0]["pixel_size_um_x"] == 1.72
    assert manifest["records"][0]["pixel_size_source"] == "image_information.xml"
    assert manifest["participant_inventory"]["001"]["modality_counts"]["HE"] == 1
