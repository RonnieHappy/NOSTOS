import base64
import io
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import numpy as np
import tifffile

from nostos.app.server import Analyzer, Handler


def _tiff_uri(array: np.ndarray) -> str:
    stream = io.BytesIO()
    tifffile.imwrite(stream, np.asarray(array, dtype=np.float32))
    return "data:image/tiff;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _payload() -> dict:
    y, x = np.mgrid[:96, :96]
    base = 100.0 + 25.0 * np.sin((x + 2.0 * y) / 6.0)
    files = [
        {"name": f"case_FSHG_p{angle}.tif", "data": _tiff_uri(base + angle / 100.0)}
        for angle in range(0, 181, 20)
    ]
    files.extend(
        [
            {"name": "R2.tif", "data": _tiff_uri(np.ones(base.shape))},
            {"name": "SNR.tif", "data": _tiff_uri(np.full(base.shape, 10.0))},
        ]
    )
    return {"mode": "label_free_pshg", "pixel_size_um": 1.0, "files": files}


def test_http_workstation_exposes_fail_closed_label_free_path() -> None:
    Handler.analyzer = Analyzer()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        root = f"http://127.0.0.1:{server.server_port}"
        health = json.load(opener.open(root + "/api/health", timeout=10))
        assert health["status"] == "ready"
        assert health["label_free_profile"] == "pshg-tiss-unstained-fshg-local-orientation-v1"
        assert health["clinical_decision"] == "withheld"
        request = urllib.request.Request(
            root + "/api/analyze",
            data=json.dumps(_payload()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        result = json.load(opener.open(request, timeout=20))
        assert result["status"] == "complete"
        assert result["measurement_status"] == "review"
        assert result["evidence_status"] == "unvalidated_new_acquisition"
        assert result["clinical_decision"] == "withheld"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
