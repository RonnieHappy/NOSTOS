import base64
import io

import numpy as np
from PIL import Image

from nostos.app.server import Analyzer


def _data_uri(array: np.ndarray) -> str:
    stream = io.BytesIO()
    Image.fromarray(array.astype(np.uint8)).save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def test_browser_analyzer_generic_mode_uses_complete_field() -> None:
    y, x = np.mgrid[:384, :384]
    image = np.clip(127 + 100 * np.sin((x + 2 * y) / 12), 0, 255).astype(np.uint8)
    rgb = np.repeat(image[..., None], 3, axis=-1)
    result = Analyzer().analyze({
        "image_data": _data_uri(rgb),
        "mode": "generic",
        "stain": "SafO",
        "pixel_size_um": 2.0,
    })
    assert result["analysis_mode"] == "generic"
    assert result["qc"]["status"] == "pass"
    assert result["metrics"]["analyzed_tiles"] >= 3
    assert result["clinical_decision"] == "withheld"
    assert any("complete field" in warning for warning in result["warnings"])
