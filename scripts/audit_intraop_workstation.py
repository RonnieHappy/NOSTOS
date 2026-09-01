"""Exercise the NOSTOS workstation HTTP boundary and verify fail-closed output."""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image

from nostos.app.server import Analyzer, Handler


def _tiff_uri(array: np.ndarray) -> str:
    stream = io.BytesIO()
    tifffile.imwrite(stream, np.asarray(array, dtype=np.float32))
    return "data:image/tiff;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _synthetic_new_acquisition() -> dict[str, Any]:
    y, x = np.mgrid[:128, :128]
    base = 100.0 + 30.0 * np.sin((x + 2.0 * y) / 7.0)
    files = [
        {
            "name": f"unseen_operator_case_FSHG_p{angle}.tif",
            "data": _tiff_uri(base + 3.0 * np.cos(np.radians(angle))),
        }
        for angle in range(0, 181, 20)
    ]
    files.extend(
        [
            {"name": "R2.tif", "data": _tiff_uri(np.ones(base.shape))},
            {"name": "SNR.tif", "data": _tiff_uri(np.full(base.shape, 10.0))},
        ]
    )
    return {"mode": "label_free_pshg", "pixel_size_um": 1.0, "files": files}


def _png_shape(data_uri: str) -> list[int]:
    prefix = "data:image/png;base64,"
    if not data_uri.startswith(prefix):
        raise ValueError("Workstation image is not a PNG data URI.")
    decoded = base64.b64decode(data_uri[len(prefix) :], validate=True)
    with Image.open(io.BytesIO(decoded)) as image:
        image.verify()
    with Image.open(io.BytesIO(decoded)) as image:
        return [image.height, image.width, len(image.getbands())]


def audit(root: Path, output: Path) -> dict[str, Any]:
    Handler.analyzer = Analyzer()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.perf_counter()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        health = json.load(opener.open(base_url + "/api/health", timeout=10))
        request = urllib.request.Request(
            base_url + "/api/analyze",
            data=json.dumps(_synthetic_new_acquisition()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = json.load(opener.open(request, timeout=30))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    elapsed = time.perf_counter() - started

    image_fields = ("source_png", "orientation_png", "coherence_png", "support_png")
    image_shapes: dict[str, list[int]] = {}
    image_decode_ok = True
    for field in image_fields:
        try:
            image_shapes[field] = _png_shape(response[field])
        except Exception:
            image_decode_ok = False

    safe_response = {key: value for key, value in response.items() if key not in image_fields}
    response_text = json.dumps(safe_response, sort_keys=True)
    path_leak = re.search(
        r"(?i)(?:[a-z]:[\\/]|(?:^|[\\s\"'])/(?:home|users|mnt|tmp)/)",
        response_text,
    )
    index_text = (root / "microscopy_app" / "index.html").read_text(encoding="utf-8")
    script_text = (root / "microscopy_app" / "app.js").read_text(encoding="utf-8")
    checks = {
        "health_ready": health.get("status") == "ready",
        "locked_profile_exposed": health.get("label_free_profile")
        == "pshg-tiss-unstained-fshg-local-orientation-v1",
        "clinical_default_withheld": health.get("clinical_decision") == "withheld",
        "http_analysis_completed": response.get("status") == "complete",
        "unstained_mode_reported": response.get("analysis_mode") == "label_free_pshg"
        and response.get("specimen_state") == "unstained",
        "new_acquisition_not_promoted": response.get("measurement_status") == "review"
        and response.get("evidence_status") == "unvalidated_new_acquisition",
        "clinical_decision_withheld": response.get("clinical_decision") == "withheld",
        "measurement_support_nonempty": int(response.get("metrics", {}).get("eligible_pixels", 0))
        >= 1000,
        "four_visual_outputs_decode": image_decode_ok
        and set(image_shapes) == set(image_fields)
        and all(shape[:2] == [128, 128] for shape in image_shapes.values()),
        "no_absolute_local_paths": path_leak is None,
        "operator_controls_present": all(
            token in index_text
            for token in (
                'id="file"',
                'id="analyze"',
                'id="export"',
                'data-view="source"',
                'data-view="orientation"',
            )
        ),
        "client_requires_support_maps": "R2.tif" in script_text and "SNR.tif" in script_text,
    }
    payload = {
        "schema_version": "nostos-intraop-workstation-http-audit/1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "verified_pass" if all(checks.values()) else "audit_fail",
        "checks": checks,
        "observed": {
            "health": health,
            "measurement_status": response.get("measurement_status"),
            "evidence_status": response.get("evidence_status"),
            "clinical_decision": response.get("clinical_decision"),
            "eligible_pixels": response.get("metrics", {}).get("eligible_pixels"),
            "image_shapes": image_shapes,
            "end_to_end_http_seconds": float(elapsed),
            "acquisition_time_included": False,
        },
        "claim_boundary": (
            "This author-operated local HTTP audit verifies software routing, visual-product decoding "
            "and fail-closed evidence semantics for a deterministic synthetic acquisition. It is not "
            "a human-factors study, independent operator test, clinical validation or browser-compatibility matrix."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/nostos0-intraop-workstation-audit-v1/workstation_audit.json"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    payload = audit(root, (root / args.output).resolve())
    print(json.dumps({"status": payload["status"], "checks": payload["checks"]}, indent=2))
    if payload["status"] != "verified_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
