import json
from pathlib import Path

import numpy as np
import nibabel  # noqa: F401 - regression guard for NumPy import-order promotion
import pytest
import tifffile

from nostos.app.measure import load_array, measure_file, measure_series_file, parse_spacing, track_series_files


def test_parse_spacing_broadcasts_or_requires_dimensional_match() -> None:
    assert parse_spacing("2.5", 3) == (2.5, 2.5, 2.5)
    assert parse_spacing("1, 2,3", 3) == (1.0, 2.0, 3.0)
    with pytest.raises(ValueError, match="Expected"):
        parse_spacing("1,2", 3)


def test_measure_generic_2d_tiff_writes_typed_geometry(tmp_path: Path) -> None:
    y, x = np.mgrid[:96, :96]
    image = (127 + 100 * np.sin((x + y) / 7)).astype(np.uint8)
    source = tmp_path / "source.tif"
    tifffile.imwrite(source, image)
    result = measure_file(source, tmp_path / "result", spacing="2.0", spatial_unit="um")
    payload = json.loads((tmp_path / "result/response_geometry.json").read_text(encoding="utf-8"))
    assert result["status"] == "review"
    assert {"spectral", "tensor", "hessian", "spatial"}.issubset(result["modules"])
    assert payload["calibration"]["spacing"] == [2.0, 2.0]
    assert any(item["code"] == "MASK_NOT_SUPPLIED" for item in payload["abstentions"])


def test_measure_3d_npy_with_mask_exposes_geometry_and_network(tmp_path: Path) -> None:
    z, y, x = np.mgrid[:24, :24, :24]
    mask = (x - 12) ** 2 + (y - 12) ** 2 + (z - 12) ** 2 <= 8 ** 2
    image = np.where(mask, 1.0, 0.0)
    image_path, mask_path = tmp_path / "volume.npy", tmp_path / "mask.npy"
    np.save(image_path, image)
    np.save(mask_path, mask)
    result = measure_file(image_path, tmp_path / "result", spacing="1,1,2", spatial_unit="um", mask_path=mask_path)
    assert result["status"] == "valid"
    assert {"hessian", "geometry", "network"}.issubset(result["modules"])
    assert result["input_dimensions"] == [24, 24, 24]


def test_load_array_rejects_nonspatial_table(tmp_path: Path) -> None:
    source = tmp_path / "table.npy"
    np.save(source, np.zeros((2, 4)))
    with pytest.raises(ValueError, match="at least 8"):
        load_array(source)


def test_measure_series_dense_contract_writes_field_geometry(tmp_path: Path) -> None:
    from scipy.ndimage import gaussian_filter, shift
    image = gaussian_filter(np.random.default_rng(42).normal(size=(64, 64)), 1.5)
    source = tmp_path / "series.npy"
    np.save(source, np.stack((image, shift(image, (2, -2), mode="reflect"))))
    result = measure_series_file(
        source, tmp_path / "dense", spacing="2", spatial_unit="um",
        temporal_spacing=0.5, temporal_unit="s", dense=True,
    )
    payload = json.loads((tmp_path / "dense/dynamic_response_geometry.json").read_text(encoding="utf-8"))
    assert result["status"] == "valid"
    assert result["endpoint"] == "frame_to_frame_dense_deformation"
    assert {item["measurement"] for item in payload["responses"]} == {
        "dense_displacement_y", "dense_displacement_x", "dense_displacement_magnitude", "dense_eligible"
    }
    assert payload["provenance"]["uncertainty_offset_pixels"] == pytest.approx(0.3076263275029393)


def test_track_series_file_contract_marks_divisions_experimental(tmp_path: Path) -> None:
    masks = tmp_path / "masks"; masks.mkdir()
    first = np.zeros((32, 32), dtype=np.uint16); second = np.zeros_like(first)
    first[8:13, 8:13] = 9; second[9:14, 10:15] = 77
    tifffile.imwrite(masks / "mask000.tif", first); tifffile.imwrite(masks / "mask001.tif", second)
    result = track_series_files(masks, tmp_path / "tracks", spacing="2", spatial_unit="um", temporal_spacing=5, temporal_unit="min")
    payload = json.loads((tmp_path / "tracks/tracking.json").read_text(encoding="utf-8"))
    assert result["status"] == "valid"
    assert result["edges"] == 1
    assert payload["scope"]["continuation_tracking"].startswith("confirmed")
    assert payload["scope"]["division_tracking"] == "not_requested"
