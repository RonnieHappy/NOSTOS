from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import tempfile
import time
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

from nostos.features.baselines import as_grayscale_float, cooccurrence_features, structure_tensor_features
from nostos.features.response_modules import directional_variogram, hessian_morphology_response
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.intraop.label_free import _unit_image, coherence_visual, load_intraop_profile, orientation_visual
from nostos.intraop.label_free_v1_4 import analyze_unstained_field as analyze_pshg_field
from nostos.intraop.operator import apply_operator_evidence_boundary, verify_public_acquisition_bundle
from nostos.segmentation.weak_labels import proposal_overlay, propose_semantic_mask


ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = ROOT / "microscopy_app"
DEFAULT_CHECKPOINT = ROOT / "outputs" / "segmentation" / "weak_init.pt"
DEFAULT_PSHG_PROFILE = ROOT / "configs" / "intraop_pshg_orientation_profile_v1.locked.json"
DEFAULT_PSHG_PUBLIC_LOCK = ROOT / "manifests" / "intraop_pshg_deployment_v1_4_lock.json"
PALETTE = {
    "0": "background",
    "1": "articular cartilage",
    "2": "calcified cartilage / interface",
    "3": "bone / trabeculae",
    "4": "marrow / void",
    "5": "artifact / unusable",
}


def _png_data(array: np.ndarray) -> str:
    stream = io.BytesIO()
    Image.fromarray(np.asarray(array, dtype=np.uint8)).save(stream, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _decode_image(value: str) -> Image.Image:
    encoded = value.split(",", 1)[-1]
    raw = base64.b64decode(encoded, validate=True)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image.load()
    if image.width * image.height > 80_000_000:
        raise ValueError("Image exceeds the 80 megapixel local safety limit")
    return image


def _decode_tiff(value: str) -> tuple[np.ndarray, bytes]:
    encoded = value.split(",", 1)[-1]
    raw = base64.b64decode(encoded, validate=True)
    if not raw or len(raw) > 64_000_000:
        raise ValueError("Invalid or oversized TIFF input")
    array = np.asarray(tifffile.imread(io.BytesIO(raw)))
    if array.ndim != 2 or min(array.shape) < 32 or array.size > 80_000_000:
        raise ValueError(f"Each PSHG input must be one 2-D field at least 32 x 32; received {array.shape}")
    return array.astype(np.float64), raw


def _tile_features(
    image: np.ndarray,
    mask: np.ndarray,
    pixel_size_um: float,
    *,
    minimum_cartilage_fraction: float = 0.72,
) -> tuple[list[dict], list[str]]:
    if not 0 < minimum_cartilage_fraction <= 1:
        raise ValueError("minimum_cartilage_fraction must be in (0, 1]")
    tile_size = min(256, image.shape[0], image.shape[1])
    tile_size -= tile_size % 2
    if tile_size < 64:
        raise ValueError("Image is too small for spatial analysis")
    stride = max(32, tile_size // 2)
    rows: list[dict] = []
    for top in range(0, max(1, image.shape[0] - tile_size + 1), stride):
        for left in range(0, max(1, image.shape[1] - tile_size + 1), stride):
            region = mask[top : top + tile_size, left : left + tile_size]
            fraction = float(np.mean(region == 1))
            if fraction < minimum_cartilage_fraction:
                continue
            tile = image[top : top + tile_size, left : left + tile_size]
            try:
                fft = extract_spatial_fft(tile, pixel_size_um=pixel_size_um)
                tensor = structure_tensor_features(tile)
                glcm = cooccurrence_features(tile)
                grayscale = as_grayscale_float(tile)
                response_scales = tuple(pixel_size_um * value for value in (2.0, 4.0, 8.0))
                hessian = hessian_morphology_response(
                    grayscale, spacing_um=(pixel_size_um, pixel_size_um), scales_um=response_scales
                )
                separations = tuple(pixel_size_um * value for value in (2.0, 4.0, 8.0, 16.0))
                spatial = directional_variogram(
                    grayscale, spacing_um=(pixel_size_um, pixel_size_um), separations_um=separations
                )
            except ValueError:
                continue
            response_values = {}
            for index, pixels in enumerate((2, 4, 8)):
                response_values[f"hessian_blob_scale_{pixels}px"] = hessian.blob[index]
                response_values[f"hessian_tube_scale_{pixels}px"] = hessian.tube[index]
                response_values[f"hessian_sheet_scale_{pixels}px"] = hessian.sheet[index]
            for index, pixels in enumerate((2, 4, 8, 16)):
                response_values[f"variogram_horizontal_sep_{pixels}px"] = spatial.horizontal[index]
                response_values[f"variogram_vertical_sep_{pixels}px"] = spatial.vertical[index]
            rows.append({
                "x": left,
                "y": top,
                "cartilage_fraction": fraction,
                **asdict(fft),
                "tensor_coherence": tensor.coherence,
                "glcm_contrast": glcm.contrast,
                "glcm_homogeneity": glcm.homogeneity,
                **response_values,
            })
    warnings: list[str] = []
    if len(rows) < 3:
        warnings.append("Fewer than three cartilage-dominant tiles passed QC; spatial metrics are unstable.")
    return rows, warnings


def _spectrum_preview(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    points = np.argwhere(mask == 1)
    if points.size:
        y0, x0 = points.min(0)
        y1, x1 = points.max(0) + 1
        crop = image[y0:y1, x0:x1]
    else:
        crop = image
    preview = Image.fromarray(crop).convert("L")
    preview.thumbnail((512, 512), Image.Resampling.BOX)
    array = np.asarray(preview, dtype=np.float64)
    array -= array.mean()
    window = np.outer(np.hanning(array.shape[0]), np.hanning(array.shape[1]))
    log_power = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(array * window))) ** 2)
    low, high = np.quantile(log_power, [0.05, 0.995])
    normalized = np.clip((log_power - low) / max(high - low, 1e-9), 0, 1)
    # Cyan instrument palette without adding a plotting dependency to each request.
    rgb = np.zeros((*normalized.shape, 3), dtype=np.uint8)
    rgb[..., 0] = np.rint(18 + 36 * normalized).astype(np.uint8)
    rgb[..., 1] = np.rint(28 + 205 * normalized).astype(np.uint8)
    rgb[..., 2] = np.rint(33 + 215 * normalized).astype(np.uint8)
    return rgb


class Analyzer:
    def __init__(self, checkpoint: Path | None = None) -> None:
        self.device = "cpu"
        self.model = None
        self.supervision = "classical_stain_aware_segmentation"
        self.pshg_profile = load_intraop_profile(DEFAULT_PSHG_PROFILE)
        if not DEFAULT_PSHG_PUBLIC_LOCK.is_file():
            raise FileNotFoundError(f"PSHG public deployment lock not found: {DEFAULT_PSHG_PUBLIC_LOCK}")
        if checkpoint is not None:
            import torch
            from nostos.segmentation.infer import load_model

            if not checkpoint.is_file():
                raise FileNotFoundError(f"Segmentation checkpoint not found: {checkpoint}")
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = load_model(checkpoint, self.device)
            checkpoint_data = torch.load(checkpoint, map_location="cpu", weights_only=True)
            self.supervision = checkpoint_data.get("supervision", "unknown")

    def _analyze_label_free_pshg(self, payload: dict, started: float) -> dict:
        pixel_size_um = float(payload.get("pixel_size_um", 1.0))
        if not 0.05 <= pixel_size_um <= 100:
            raise ValueError("Pixel size must be between 0.05 and 100 µm/pixel")
        uploaded = payload.get("files")
        if not isinstance(uploaded, list) or not uploaded:
            raise ValueError("PSHG mode requires a folder containing ten FSHG frames, R2.tif and SNR.tif")

        arrays: dict[str, np.ndarray] = {}
        records: dict[str, dict] = {}
        for item in uploaded:
            if not isinstance(item, dict) or "name" not in item or "data" not in item:
                raise ValueError("Each uploaded PSHG file requires name and data fields")
            name = Path(str(item["name"])).name
            key = name.lower()
            if key in arrays:
                raise ValueError(f"Duplicate PSHG filename: {name}")
            array, raw = _decode_tiff(str(item["data"]))
            arrays[key] = array
            records[key] = {
                "name": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

        frame_by_angle: dict[int, np.ndarray] = {}
        frame_keys: list[str] = []
        for key, array in arrays.items():
            matched = re.search(r"_fshg_p(\d+)\.tiff?$", key)
            if matched is None:
                continue
            angle = int(matched.group(1))
            if angle in frame_by_angle:
                raise ValueError(f"Duplicate PSHG polarization angle: {angle}")
            frame_by_angle[angle] = array
            frame_keys.append(key)
        expected_angles = list(range(0, 181, 20))
        if sorted(frame_by_angle) != expected_angles:
            raise ValueError(f"PSHG mode requires polarization angles 0:20:180; found {sorted(frame_by_angle)}")
        r2_key = next((key for key in ("r2.tif", "r2.tiff") if key in arrays), None)
        snr_key = next((key for key in ("snr.tif", "snr.tiff") if key in arrays), None)
        fi_key = next((key for key in ("fi.tif", "fi.tiff") if key in arrays), None)
        if r2_key is None or snr_key is None:
            raise ValueError("PSHG mode requires R2.tif and SNR.tif")
        allowed = set(frame_keys) | {r2_key, snr_key}
        if fi_key is not None:
            allowed.add(fi_key)
        unexpected = sorted(set(arrays) - allowed)
        if unexpected:
            raise ValueError(f"Unexpected files in PSHG bundle: {unexpected}")
        shapes = {array.shape for array in arrays.values()}
        if len(shapes) != 1:
            raise ValueError(f"PSHG frames and maps must be shape matched; received {sorted(shapes)}")

        frames = np.stack([frame_by_angle[angle] for angle in expected_angles])
        mean_image = np.mean(frames, axis=0)
        result = analyze_pshg_field(
            mean_image,
            pixel_size_um=pixel_size_um,
            modality=str(self.pshg_profile["modality"]),
            profile=self.pshg_profile,
            verified_stack_frame_count=10,
            r2_map=arrays[r2_key],
            snr_map=arrays[snr_key],
            reference_fi_map=None if fi_key is None else arrays[fi_key],
        )
        deployment_records = [records[key] for key in frame_keys] + [records[r2_key], records[snr_key]]
        provenance = verify_public_acquisition_bundle(deployment_records, DEFAULT_PSHG_PUBLIC_LOCK)
        bounded = apply_operator_evidence_boundary(result.payload, provenance)
        summary = bounded["measurement"]["summary"]
        reference = bounded.get("reference_evaluation")
        warnings = []
        if provenance["verified"]:
            warnings.append("Archived public acquisition identity verified against the locked release evidence.")
        else:
            warnings.append("New acquisition: file structure matches the PSHG profile, but instrument transfer is not validated.")
        if bounded["status"] != "valid":
            warnings.append(f"Measurement requires {bounded['status']}: {', '.join(bounded['validity_reasons']) or 'acquisition review'}.")
        warnings.append("Clinical output is withheld. This endpoint does not provide diagnosis, margins, mechanics or treatment guidance.")
        source_rgb = np.repeat(_unit_image(result.source_image)[..., None], 3, axis=-1)
        support_rgb = np.repeat((255 * result.eligible.astype(np.uint8))[..., None], 3, axis=-1)
        return {
            "status": "complete",
            "analysis_mode": "label_free_pshg",
            "measurement_status": bounded["status"],
            "evidence_status": bounded["measurement"]["evidence_status"],
            "specimen_state": "unstained",
            "pixel_size_um": pixel_size_um,
            "device": "cpu",
            "intended_use": "research_only_intraoperative_integration",
            "clinical_decision": "withheld",
            "profile": {
                "profile_id": self.pshg_profile["profile_id"],
                "endpoint": self.pshg_profile["measurement_contract"]["endpoint"],
                "provenance": provenance,
                "claim_boundary": self.pshg_profile["claim_boundary"],
            },
            "qc": {
                "status": bounded["status"],
                "acquisition": bounded["acquisition_qc"],
                "validity_reasons": bounded["validity_reasons"],
            },
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "image": {"width": int(mean_image.shape[1]), "height": int(mean_image.shape[0])},
            "metrics": {
                "mean_axial_orientation_degrees": summary["mean_axial_orientation_degrees"],
                "axial_resultant": summary["axial_resultant"],
                "median_coherence": summary["median_coherence"],
                "eligible_fraction": summary["eligible_fraction"],
                "eligible_pixels": summary["eligible_pixels"],
                "reference_median_error_degrees": None if reference is None else reference["median_axial_error_degrees"],
            },
            "source_files": deployment_records,
            "evaluation_reference_supplied": fi_key is not None,
            "warnings": warnings,
            "source_png": _png_data(source_rgb),
            "orientation_png": _png_data(orientation_visual(result)),
            "coherence_png": _png_data(coherence_visual(result)),
            "support_png": _png_data(support_rgb),
            "receipt": bounded,
        }

    def analyze(self, payload: dict) -> dict:
        started = time.perf_counter()
        mode = str(payload.get("mode", "cartilage"))
        if mode == "label_free_pshg":
            return self._analyze_label_free_pshg(payload, started)
        stain = str(payload.get("stain", "SafO"))
        pixel_size_um = float(payload.get("pixel_size_um", 5.16))
        if mode not in {"generic", "cartilage"}:
            raise ValueError("Unsupported analysis mode")
        if stain not in {"HE", "SafO", "PLM"}:
            raise ValueError("Unsupported stain")
        if not 0.05 <= pixel_size_um <= 100:
            raise ValueError("Pixel size must be between 0.05 and 100 µm/pixel")
        source = _decode_image(str(payload["image_data"]))
        image = np.asarray(source)
        if mode == "generic":
            mask = np.ones(image.shape[:2], dtype=np.uint8)
        elif self.model is None:
            mask = propose_semantic_mask(image, stain)
        else:
            from nostos.segmentation.infer import predict_section

            with tempfile.TemporaryDirectory(prefix="nostos_case_") as folder:
                image_path = Path(folder) / "input.png"
                source.save(image_path)
                mask = predict_section(
                    self.model,
                    image_path,
                    stain,
                    tile_size=256,
                    context=32,
                    input_pixel_size_um=pixel_size_um,
                    model_pixel_size_um=5.16,
                    device=self.device,
                )
        rows, warnings = _tile_features(image, mask, pixel_size_um)
        proportions = {PALETTE[str(index)]: float(np.mean(mask == index)) for index in range(6)}
        roi_fraction = proportions[PALETTE["1"]]
        if mode == "cartilage" and roi_fraction < 0.02:
            warnings.append("Very little cartilage was detected. Check stain, calibration, focus, and field selection.")
        if mode == "cartilage" and roi_fraction > 0.85:
            warnings.append("Cartilage occupies most of the frame. Confirm that bone/background boundaries are visible.")
        if mode == "cartilage" and stain == "PLM":
            warnings.append("PLM segmentation is experimental and lacks reviewed reference-mask validation.")
        if mode == "generic":
            warnings.append("Generic mode measures the complete field. Supply a reviewed mask through the CLI for ROI-dependent geometry and network responses.")
        warnings.append("Research-use-only model. Do not use this output as an intraoperative diagnostic decision.")
        evaluable = len(rows) >= 3 and (mode == "generic" or (0.02 <= roi_fraction <= 0.85 and stain != "PLM"))
        review_required = len(rows) >= 1 and not evaluable
        metrics: dict[str, float | int | None] = {"analyzed_tiles": len(rows)}
        metric_names = [
            "orientation_degrees", "anisotropy", "angular_entropy", "spectral_slope",
            "characteristic_frequency_cycles_per_mm", "tensor_coherence", "glcm_contrast", "glcm_homogeneity",
        ]
        if rows:
            metric_names.extend(sorted(name for name in rows[0] if name.startswith(("hessian_", "variogram_"))))
        for name in metric_names:
            values = np.asarray([row[name] for row in rows], dtype=float)
            metrics[name] = float(np.median(values)) if values.size else None
        overlay = proposal_overlay(image, mask, alpha=0.48)
        return {
            "status": "complete",
            "analysis_mode": mode,
            "stain": stain,
            "pixel_size_um": pixel_size_um,
            "device": str(self.device),
            "model_supervision": self.supervision,
            "intended_use": "research_only",
            "clinical_decision": "withheld",
            "qc": {
                "evaluable": evaluable,
                "status": "pass" if evaluable else ("review_required" if review_required else "fail"),
                "minimum_tiles": 3,
                "cartilage_fraction_range": [0.02, 0.85] if mode == "cartilage" else None,
            },
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "image": {"width": source.width, "height": source.height},
            "class_proportions": proportions,
            "metrics": metrics,
            "warnings": warnings,
            "tiles": rows,
            "overlay_png": _png_data(overlay),
            "mask_png": _png_data(mask),
            "spectrum_png": _png_data(_spectrum_preview(image, mask)),
        }


class Handler(SimpleHTTPRequestHandler):
    analyzer: Analyzer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._json({
                "status": "ready",
                "device": str(self.analyzer.device),
                "model_supervision": self.analyzer.supervision,
                "label_free_profile": self.analyzer.pshg_profile["profile_id"],
                "clinical_decision": "withheld",
            })
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 120_000_000:
                raise ValueError("Invalid or oversized request")
            payload = json.loads(self.rfile.read(length))
            self._json(self.analyzer.analyze(payload))
        except Exception as error:
            self._json({"status": "error", "error": f"{type(error).__name__}: {error}"}, HTTPStatus.BAD_REQUEST)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local NOSTOS microscopy workstation")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--learned-checkpoint",
        type=Path,
        help="Optional learned segmentation model. Omit for the CPU-first classical pipeline.",
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    Handler.analyzer = Analyzer(args.learned_checkpoint.resolve() if args.learned_checkpoint else None)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(json.dumps({"url": url, "device": str(Handler.analyzer.device), "web_root": str(WEB_ROOT)}), flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
