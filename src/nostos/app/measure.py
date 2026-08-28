"""Sample-agnostic file I/O for the typed NOSTOS response geometry."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from nostos.features.universal import analyze_response_geometry
from nostos.features.dynamic import analyze_dense_deformation, analyze_time_series
from nostos.features.tracking import track_instance_series


def _is_nifti(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".nii") or name.endswith(".nii.gz")


def load_array(path: Path) -> np.ndarray:
    """Load a 2-D image or 2-D/3-D scientific array without changing its scale."""
    if not path.is_file():
        raise FileNotFoundError(f"Input does not exist: {path}")
    name = path.name.lower()
    if name.endswith(".npy"):
        array = np.load(path, allow_pickle=False)
    elif _is_nifti(path):
        import nibabel as nib

        array = np.asanyarray(nib.load(str(path)).dataobj)
    elif path.suffix.lower() in {".tif", ".tiff"}:
        import tifffile

        array = tifffile.imread(path)
    else:
        with Image.open(path) as opened:
            array = np.asarray(opened)
    data = np.asarray(array)
    if data.ndim == 3 and data.shape[-1] in {3, 4} and not _is_nifti(path) and not name.endswith(".npy"):
        rgb = data[..., :3].astype(np.float64)
        data = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    if data.ndim not in {2, 3}:
        raise ValueError(f"NOSTOS measure accepts one 2-D image or 3-D volume; received shape {data.shape}.")
    if min(data.shape) < 8:
        raise ValueError(f"Every spatial dimension must contain at least 8 samples; received shape {data.shape}.")
    if not (np.issubdtype(data.dtype, np.number) or np.issubdtype(data.dtype, np.bool_)) or not np.isfinite(data).all():
        raise ValueError("Input must contain only finite numeric values.")
    return data


def load_series_array(path: Path) -> np.ndarray:
    """Load an explicit 2-D+t array without treating the time axis as spatial."""
    if not path.is_file():
        raise FileNotFoundError(f"Input does not exist: {path}")
    if path.suffix.lower() == ".npy":
        data = np.load(path, allow_pickle=False)
    elif path.suffix.lower() in {".tif", ".tiff"}:
        import tifffile
        data = tifffile.imread(path)
    else:
        raise ValueError("Time series input must be a NumPy .npy or multipage TIFF file.")
    series = np.asarray(data)
    if series.ndim != 3 or series.shape[0] < 2 or min(series.shape[1:]) < 8:
        raise ValueError(f"A 2-D+t series requires shape (time>=2, y>=8, x>=8); received {series.shape}.")
    if not np.issubdtype(series.dtype, np.number) or not np.isfinite(series).all():
        raise ValueError("Time-series input must contain only finite numeric values.")
    return series


def parse_spacing(value: str, dimensions: int) -> tuple[float, ...]:
    try:
        items = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise ValueError("Spacing must be one number or a comma-separated list of numbers.") from error
    if len(items) == 1:
        items = items * dimensions
    if len(items) != dimensions:
        raise ValueError(f"Expected one spacing value or {dimensions} values; received {len(items)}.")
    if any(not np.isfinite(item) or item <= 0 for item in items):
        raise ValueError("Spacing values must be finite and positive.")
    return items


def measure_file(
    input_path: Path,
    output: Path,
    *,
    spacing: str,
    spatial_unit: str,
    mask_path: Path | None = None,
    specimen_reference: float | None = None,
    specimen_direction_degrees: float = 0.0,
) -> dict:
    image = load_array(input_path)
    mask = None
    if mask_path is not None:
        mask = load_array(mask_path) != 0
        if mask.shape != image.shape:
            raise ValueError(f"Mask shape {mask.shape} does not match image shape {image.shape}.")
    spacing_values = parse_spacing(spacing, image.ndim)
    geometry = analyze_response_geometry(
        image,
        spacing_um=spacing_values,
        mask=mask,
        specimen_reference_um=specimen_reference,
        specimen_direction_degrees=specimen_direction_degrees,
        spatial_unit=spatial_unit,
    )
    payload = geometry.to_dict()
    payload["source"] = {
        "image": input_path.name,
        "mask": None if mask_path is None else mask_path.name,
        "format": "nifti" if _is_nifti(input_path) else input_path.suffix.lower().lstrip("."),
    }
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "response_geometry.json"
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {
        "status": payload["status"],
        "output": str(destination.resolve()),
        "input_dimensions": list(image.shape),
        "spacing": list(spacing_values),
        "spatial_unit": spatial_unit,
        "responses": len(payload["responses"]),
        "abstentions": len(payload["abstentions"]),
        "modules": sorted({item["module"] for item in payload["responses"]}),
    }


def measure_series_file(
    input_path: Path,
    output: Path,
    *,
    spacing: str,
    spatial_unit: str,
    temporal_spacing: float,
    temporal_unit: str,
    dense: bool = False,
) -> dict:
    """Measure an explicitly declared time series; the first array axis is time."""
    series = load_series_array(input_path)
    spacing_values = parse_spacing(spacing, series.ndim - 1)
    analyzer = analyze_dense_deformation if dense else analyze_time_series
    geometry = analyzer(series, spacing=spacing_values, temporal_spacing=temporal_spacing,
                        spatial_unit=spatial_unit, temporal_unit=temporal_unit)
    payload = geometry.to_dict()
    payload["source"] = {"image": input_path.name, "format": input_path.suffix.lower().lstrip("."), "axis_order": "tyx"}
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "dynamic_response_geometry.json"
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {
        "status": payload["status"], "output": str(destination.resolve()),
        "input_dimensions": list(series.shape), "responses": len(payload["responses"]),
        "abstentions": len(payload["abstentions"]),
        "endpoint": "frame_to_frame_dense_deformation" if dense else "frame_to_frame_bulk_translation",
    }


def track_series_files(
    mask_directory: Path,
    output: Path,
    *,
    spacing: str,
    spatial_unit: str,
    temporal_spacing: float,
    temporal_unit: str,
    image_directory: Path | None = None,
    experimental_divisions: bool = False,
) -> dict:
    """Link a directory of framewise instance masks into calibrated trajectories."""
    mask_paths = sorted(mask_directory.glob("*.tif")) + sorted(mask_directory.glob("*.tiff"))
    if len(mask_paths) < 2:
        raise ValueError("Tracking requires at least two TIFF instance masks.")
    masks = np.stack([load_array(path) for path in mask_paths])
    images = None
    image_paths: list[Path] = []
    if image_directory is not None:
        image_paths = sorted(image_directory.glob("*.tif")) + sorted(image_directory.glob("*.tiff"))
        if len(image_paths) != len(mask_paths):
            raise ValueError("Image and mask directories must contain the same number of TIFF frames.")
        images = np.stack([load_array(path) for path in image_paths])
    spacing_values = parse_spacing(spacing, 2)
    division_parameters = None
    if experimental_divisions:
        division_parameters = {
            "division_combined_area_range": (0.4, 1.5), "division_child_area_range": (0.05, 1.3),
            "division_balance_max": 8.0, "division_distance_radii": 2.0, "division_separation_radii": 3.0,
        }
    result = track_instance_series(
        masks, spacing=spacing_values, temporal_spacing=temporal_spacing,
        images=images, weights=(1, 0, 0), use_flow=False,
        allow_divisions=experimental_divisions, division_parameters=division_parameters,
        spatial_unit=spatial_unit, temporal_unit=temporal_unit,
    )
    result["source"] = {"mask_files": [path.name for path in mask_paths], "image_files": [path.name for path in image_paths]}
    result["scope"] = {
        "continuation_tracking": "confirmed_on_simulated_and_real_ctc_training_sequences",
        "division_tracking": "experimental_failed_pristine_transfer_gate" if experimental_divisions else "not_requested",
        "automatic_segmentation": False,
    }
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "tracking.json"
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"status": result["status"], "output": str(destination.resolve()), "frames": len(mask_paths),
            "edges": len(result["edges"]), "experimental_divisions": experimental_divisions}
