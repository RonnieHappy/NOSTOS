import base64
import io

import numpy as np
import pytest
import tifffile

from nostos.app.server import Analyzer


def _tiff_uri(array: np.ndarray) -> str:
    stream = io.BytesIO()
    tifffile.imwrite(stream, np.asarray(array, dtype=np.float32))
    return "data:image/tiff;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _bundle() -> list[dict[str, str]]:
    y, x = np.mgrid[:128, :128]
    base = 100.0 + 30.0 * np.sin((x + 2.0 * y) / 7.0)
    files = []
    for angle in range(0, 181, 20):
        frame = base + 3.0 * np.cos(np.radians(angle))
        files.append({"name": f"newcase_FSHG_p{angle}.tif", "data": _tiff_uri(frame)})
    files.extend(
        [
            {"name": "R2.tif", "data": _tiff_uri(np.ones(base.shape))},
            {"name": "SNR.tif", "data": _tiff_uri(np.full(base.shape, 10.0))},
        ]
    )
    return files


def test_browser_pshg_path_maps_new_unstained_acquisition_but_does_not_promote_it() -> None:
    result = Analyzer().analyze(
        {
            "mode": "label_free_pshg",
            "pixel_size_um": 1.0,
            "files": _bundle(),
        }
    )
    assert result["status"] == "complete"
    assert result["analysis_mode"] == "label_free_pshg"
    assert result["specimen_state"] == "unstained"
    assert result["measurement_status"] == "review"
    assert result["evidence_status"] == "unvalidated_new_acquisition"
    assert result["clinical_decision"] == "withheld"
    assert result["metrics"]["eligible_pixels"] > 1000
    assert result["source_png"].startswith("data:image/png;base64,")
    assert result["orientation_png"].startswith("data:image/png;base64,")
    assert result["coherence_png"].startswith("data:image/png;base64,")
    assert result["support_png"].startswith("data:image/png;base64,")


def test_browser_pshg_path_rejects_incomplete_bundle() -> None:
    files = [item for item in _bundle() if item["name"] != "R2.tif"]
    with pytest.raises(ValueError, match="requires R2.tif and SNR.tif"):
        Analyzer().analyze(
            {
                "mode": "label_free_pshg",
                "pixel_size_um": 1.0,
                "files": files,
            }
        )
