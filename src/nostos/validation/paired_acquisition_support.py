"""Prospective paired-acquisition measurement-support validation.

The module deliberately separates three objects:

* a frozen structural estimator applied identically to an input and reference;
* input-only evidence used to decide whether the estimator is supported; and
* reference-only error labels used exclusively for evaluation.

No restoration model or biological label is used.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import ndimage
from skimage.registration import phase_cross_correlation
from skimage.transform import resize

from nostos.core.qc import acquisition_qc
from nostos.features.response_modules import (
    directional_variogram,
    structure_tensor_response,
)
from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees, normalized_curve_distance


PROTOCOL_VERSION = "nostos-paired-acquisition-support/5.0"
ENDPOINT_KINDS = {
    "tensor_orientation": "axial",
    "tensor_coherence": "absolute",
    "spectral_anisotropy": "absolute",
    "spectral_entropy": "absolute",
    "spectral_scale": "relative",
    "hessian_blob_curve": "curve",
    "hessian_tube_curve": "curve",
    "hessian_blob_scale": "log2_scale",
    "hessian_tube_scale": "log2_scale",
    "variogram_horizontal_curve": "curve",
    "variogram_vertical_curve": "curve",
    "variogram_range_horizontal": "relative",
    "variogram_range_vertical": "relative",
}


@dataclass(frozen=True)
class PairRegistration:
    eligible: bool
    shift_reference_pixels_yx: tuple[float, float]
    shift_effective_input_pixels_yx: tuple[float, float]
    peak_ratio: float
    error: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ThresholdSelection:
    status: str
    threshold: float | None
    accepted: int
    eligible: int
    coverage: float
    risk: float | None
    risk_upper95: float | None
    candidate_count: int
    target_risk: float
    maximum_risk_upper95: float


@dataclass(frozen=True)
class BioSRPairRecord:
    structure: str
    cell_id: str
    signal_level: int
    pair_id: str
    reference_group_id: str
    input_member: str
    reference_member: str
    input_frames: int
    input_shape_yx: tuple[int, int]
    reference_shape_yx: tuple[int, int]
    input_grid_spacing_um: float
    effective_input_spacing_um: float
    reference_spacing_um: float
    input_header_spacing_yx_um: tuple[float, float]
    reference_header_spacing_yx_um: tuple[float, float]
    physical_field_of_view_yx_um: tuple[float, float]
    archive_layout: str


@dataclass(frozen=True)
class MRCHeader:
    nx: int
    ny: int
    nz: int
    mode: int
    extended_bytes: int
    spacing_yx_um: tuple[float, float]


def _robust_unit(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 32 or not np.isfinite(data).all():
        raise ValueError("A finite 2-D image of at least 32 x 32 pixels is required.")
    low, high = np.percentile(data, (1.0, 99.0))
    if high <= low:
        raise ValueError("The image has no robust intensity range.")
    return np.clip((data - low) / (high - low), 0.0, 1.0)


def _normalise_curve(values: Sequence[float]) -> np.ndarray:
    curve = np.asarray(values, dtype=np.float64)
    norm = float(np.linalg.norm(curve))
    if not np.isfinite(curve).all() or norm <= np.finfo(float).eps:
        return np.zeros_like(curve)
    return curve / norm


def _log2_scale_error(estimate: float, reference: float) -> float:
    if estimate <= 0 or reference <= 0:
        return float("inf")
    return float(abs(math.log2(estimate / reference)))


def _streaming_hessian_2d(
    image: np.ndarray,
    *,
    spacing_um: float,
    scales_um: Sequence[float],
) -> dict[str, Any]:
    """Return the frozen 2-D Hessian summaries without retaining scale maps.

    This is algebraically equivalent to the two-dimensional branch of
    ``hessian_morphology_response`` but bounds peak memory to one scale.
    """

    data = np.asarray(image, dtype=np.float64)
    blob_curve: list[float] = []
    tube_curve: list[float] = []
    eps = np.finfo(float).eps
    for scale in scales_um:
        sigma = float(scale / spacing_um)
        normalization = float(scale**2 / spacing_um**2)
        hyy = ndimage.gaussian_filter(data, sigma=(sigma, sigma), order=(2, 0), mode="reflect")
        hyy *= normalization
        hxx = ndimage.gaussian_filter(data, sigma=(sigma, sigma), order=(0, 2), mode="reflect")
        hxx *= normalization
        hxy = ndimage.gaussian_filter(data, sigma=(sigma, sigma), order=(1, 1), mode="reflect")
        hxy *= normalization
        half_trace = 0.5 * (hxx + hyy)
        radius = np.sqrt((0.5 * (hxx - hyy)) ** 2 + hxy**2)
        first = np.abs(half_trace - radius)
        second = np.abs(half_trace + radius)
        small = np.minimum(first, second)
        large = np.maximum(first, second)
        tube = (1.0 - np.exp(-(large / (small + eps)) ** 2 / 2.0)) * large
        blob = np.exp(-((large - small) / (large + small + eps)) ** 2 / 0.25) * (large + small) / 2.0
        tube_curve.append(float(np.percentile(tube, 99)))
        blob_curve.append(float(np.percentile(blob, 99)))
    blob_values = np.asarray(blob_curve, dtype=float)
    tube_values = np.asarray(tube_curve, dtype=float)
    scales = np.asarray(scales_um, dtype=float)
    return {
        "blob_curve": _normalise_curve(blob_values).tolist(),
        "tube_curve": _normalise_curve(tube_values).tolist(),
        "blob_energy": float(np.linalg.norm(blob_values)),
        "tube_energy": float(np.linalg.norm(tube_values)),
        "blob_scale": float(scales[int(np.argmax(blob_values))]),
        "tube_scale": float(scales[int(np.argmax(tube_values))]),
    }


def _relative_error(estimate: float, reference: float) -> float:
    denominator = max(abs(reference), np.finfo(float).eps)
    return float(abs(estimate - reference) / denominator)


def shared_spectral_band_cycles_per_mm(
    config: Mapping[str, Any],
    effective_input_spacing_um: float,
) -> tuple[float, float]:
    """Return one physical FFT band shared by an input/reference pair.

    Fractions are defined against the effective input Nyquist limit and then
    applied unchanged to both grids. Pixel spacing therefore cannot silently
    change the physical estimand.
    """

    if effective_input_spacing_um <= 0:
        raise ValueError("effective_input_spacing_um must be positive.")
    specification = config["spectral_analysis"]
    low = float(specification["minimum_fraction_of_effective_input_nyquist"])
    high = float(specification["maximum_fraction_of_effective_input_nyquist"])
    if not 0 <= low < high <= 1:
        raise ValueError("Spectral analysis fractions must satisfy 0 <= low < high <= 1.")
    nyquist_cycles_per_mm = 500.0 / effective_input_spacing_um
    return low * nyquist_cycles_per_mm, high * nyquist_cycles_per_mm


def read_mrc_bytes(payload: bytes) -> np.ndarray:
    """Read a little-endian MRC image without importing a mutable external reader."""

    if len(payload) < 1024:
        raise ValueError("MRC payload is shorter than its 1024-byte header.")
    header = np.frombuffer(payload[:1024], dtype="<i4", count=256)
    nx, ny, nz, mode = (int(header[index]) for index in range(4))
    extended_bytes = int(header[23])
    if nx <= 0 or ny <= 0 or nz <= 0 or extended_bytes < 0:
        raise ValueError("Invalid MRC dimensions or extended-header length.")
    dtypes = {0: np.dtype("i1"), 1: np.dtype("<i2"), 2: np.dtype("<f4"), 6: np.dtype("<u2")}
    if mode not in dtypes:
        raise ValueError(f"Unsupported MRC mode {mode}; supported modes are 0, 1, 2 and 6.")
    offset = 1024 + extended_bytes
    count = nx * ny * nz
    expected = offset + count * dtypes[mode].itemsize
    if len(payload) < expected:
        raise ValueError(f"Truncated MRC payload: expected at least {expected} bytes, received {len(payload)}.")
    array = np.frombuffer(payload, dtype=dtypes[mode], count=count, offset=offset).reshape((nz, ny, nx))
    return np.asarray(array[0] if nz == 1 else array)


def read_mrc(path: Path) -> np.ndarray:
    return read_mrc_bytes(path.read_bytes())


def _mrc_header_from_bytes(payload: bytes) -> MRCHeader:
    if len(payload) < 1024:
        raise ValueError("MRC header is shorter than 1024 bytes.")
    integer_header = np.frombuffer(payload[:40], dtype="<i4", count=10)
    nx, ny, nz, mode = integer_header[:4].tolist()
    mx, my, _ = integer_header[7:10].tolist()
    xlen, ylen, _ = np.frombuffer(payload[40:52], dtype="<f4", count=3).tolist()
    extended = int(np.frombuffer(payload[92:96], dtype="<i4", count=1)[0])
    if min(int(nx), int(ny), int(nz), int(mx), int(my)) <= 0:
        raise ValueError("MRC dimensions and x/y sampling-grid counts must be positive.")
    spacing_x = float(xlen) / int(mx)
    spacing_y = float(ylen) / int(my)
    if not np.isfinite([spacing_y, spacing_x]).all() or min(spacing_y, spacing_x) <= 0:
        raise ValueError("MRC x/y physical spacing must be finite and positive.")
    return MRCHeader(
        int(nx),
        int(ny),
        int(nz),
        int(mode),
        extended,
        (spacing_y, spacing_x),
    )


def index_biosr_archive(
    archive: Path,
    *,
    structure: str,
    expected_raw_spacing_um: float,
    upscaling_factor: int,
    expected_level_count: int,
    spacing_absolute_tolerance_um: float = 1e-6,
    field_of_view_relative_tolerance: float = 1e-6,
) -> list[BioSRPairRecord]:
    """Index a BioSR archive without decoding biological pixels."""

    if upscaling_factor not in {2, 3}:
        raise ValueError("BioSR upscaling_factor must be two or three.")
    if expected_level_count < 1:
        raise ValueError("expected_level_count must be positive.")
    if expected_raw_spacing_um <= 0 or spacing_absolute_tolerance_um < 0:
        raise ValueError("Expected raw spacing must be positive and spacing tolerance nonnegative.")
    if field_of_view_relative_tolerance < 0:
        raise ValueError("Field-of-view tolerance must be nonnegative.")
    flat_input = re.compile(r"^(?P<root>[^/]+)/(?P<cell>Cell_\d+)/RawSIMData_level_(?P<level>\d{2})\.mrc$", re.I)
    flat_reference = re.compile(r"^(?P<root>[^/]+)/(?P<cell>Cell_\d+)/SIM_gt\.mrc$", re.I)
    nested_input = re.compile(
        r"^(?P<root>[^/]+)/(?P<cell>Cell_\d+)/RawSIMData/RawSIMData_level_(?P<level>\d{2})\.mrc$",
        re.I,
    )
    nested_reference = re.compile(
        r"^(?P<root>[^/]+)/(?P<cell>Cell_\d+)/GTSIM/GTSIM_level_(?P<level>\d{2})\.mrc$",
        re.I,
    )
    with zipfile.ZipFile(archive) as opened:
        references: dict[tuple[str, int | None], tuple[str, MRCHeader, str]] = {}
        inputs: list[tuple[str, str, int, MRCHeader, str]] = []
        for info in opened.infolist():
            reference_match = flat_reference.match(info.filename)
            input_match = flat_input.match(info.filename)
            layout = "shared_reference_flat"
            reference_level: int | None = None
            if reference_match is None:
                reference_match = nested_reference.match(info.filename)
                if reference_match is not None:
                    layout = "level_matched_nested"
                    reference_level = int(reference_match.group("level"))
            if input_match is None:
                input_match = nested_input.match(info.filename)
                if input_match is not None:
                    layout = "level_matched_nested"
            if reference_match:
                with opened.open(info, "r") as stream:
                    header = _mrc_header_from_bytes(stream.read(1024))
                references[(reference_match.group("cell"), reference_level)] = (info.filename, header, layout)
            elif input_match:
                with opened.open(info, "r") as stream:
                    header = _mrc_header_from_bytes(stream.read(1024))
                inputs.append((input_match.group("cell"), info.filename, int(input_match.group("level")), header, layout))
    records: list[BioSRPairRecord] = []
    for cell, member, level, input_header, layout in sorted(inputs):
        reference_key = (cell, level) if layout == "level_matched_nested" else (cell, None)
        if reference_key not in references:
            raise ValueError(f"Missing reference for {cell}, level {level:02d}, layout {layout}.")
        reference_member, reference_header, reference_layout = references[reference_key]
        if reference_layout != layout:
            raise ValueError(f"Input/reference layout mismatch for {cell}, level {level:02d}.")
        in_x, in_y, in_z, in_mode = input_header.nx, input_header.ny, input_header.nz, input_header.mode
        ref_x, ref_y, ref_z, ref_mode = (
            reference_header.nx,
            reference_header.ny,
            reference_header.nz,
            reference_header.mode,
        )
        if in_z != 9 or ref_z != 1 or in_mode not in {1, 2, 6} or ref_mode not in {1, 2, 6}:
            raise ValueError(f"Unexpected BioSR MRC layout for {cell}, level {level:02d}.")
        ratios = (ref_y / in_y, ref_x / in_x)
        if not np.allclose(ratios, upscaling_factor, rtol=0, atol=1e-12):
            raise ValueError(
                f"Declared {upscaling_factor}x factor disagrees with array dimensions for {cell}: {ratios}."
            )
        input_spacing = np.asarray(input_header.spacing_yx_um, dtype=float)
        reference_spacing = np.asarray(reference_header.spacing_yx_um, dtype=float)
        expected_reference_spacing_um = expected_raw_spacing_um / upscaling_factor
        if not np.allclose(
            input_spacing,
            expected_raw_spacing_um,
            rtol=0,
            atol=spacing_absolute_tolerance_um,
        ):
            raise ValueError(
                f"Raw MRC spacing disagrees with the BioSR workbook for {cell}, level {level:02d}: "
                f"observed {input_spacing.tolist()}, expected {expected_raw_spacing_um}."
            )
        if not np.allclose(
            reference_spacing,
            expected_reference_spacing_um,
            rtol=0,
            atol=spacing_absolute_tolerance_um,
        ):
            raise ValueError(
                f"Reference MRC spacing disagrees with raw spacing / upscaling factor for {cell}, "
                f"level {level:02d}: observed {reference_spacing.tolist()}, "
                f"expected {expected_reference_spacing_um}."
            )
        input_fov = input_spacing * np.asarray((in_y, in_x), dtype=float)
        reference_fov = reference_spacing * np.asarray((ref_y, ref_x), dtype=float)
        if not np.allclose(
            input_fov,
            reference_fov,
            rtol=field_of_view_relative_tolerance,
            atol=0,
        ):
            raise ValueError(
                f"Raw/reference physical fields of view disagree for {cell}, level {level:02d}: "
                f"raw {input_fov.tolist()}, reference {reference_fov.tolist()}."
            )
        group = f"{structure}|{cell}"
        records.append(
            BioSRPairRecord(
                structure=structure,
                cell_id=cell,
                signal_level=level,
                pair_id=f"{group}|level_{level:02d}",
                reference_group_id=group,
                input_member=member,
                reference_member=reference_member,
                input_frames=in_z,
                input_shape_yx=(in_y, in_x),
                reference_shape_yx=(ref_y, ref_x),
                input_grid_spacing_um=float(expected_raw_spacing_um),
                effective_input_spacing_um=float(expected_raw_spacing_um),
                reference_spacing_um=float(expected_reference_spacing_um),
                input_header_spacing_yx_um=tuple(float(value) for value in input_spacing),
                reference_header_spacing_yx_um=tuple(float(value) for value in reference_spacing),
                physical_field_of_view_yx_um=(
                    float(in_y * expected_raw_spacing_um),
                    float(in_x * expected_raw_spacing_um),
                ),
                archive_layout=layout,
            )
        )
    expected_levels = set(range(1, expected_level_count + 1))
    by_cell: dict[str, set[int]] = {}
    for record in records:
        by_cell.setdefault(record.cell_id, set()).add(record.signal_level)
    incomplete = {cell: sorted(levels) for cell, levels in by_cell.items() if levels != expected_levels}
    if incomplete:
        raise ValueError(
            f"BioSR cells do not contain exactly levels 01-{expected_level_count:02d}: {incomplete}"
        )
    return records


def read_biosr_pair(opened: zipfile.ZipFile, record: BioSRPairRecord) -> tuple[np.ndarray, np.ndarray]:
    """Decode a frozen arithmetic-mean input and its per-cell reference."""

    raw = read_mrc_bytes(opened.read(record.input_member))
    reference = read_mrc_bytes(opened.read(record.reference_member))
    if raw.shape != (record.input_frames, *record.input_shape_yx):
        raise ValueError(f"Decoded input shape mismatch for {record.pair_id}: {raw.shape}.")
    if reference.shape != record.reference_shape_yx:
        raise ValueError(f"Decoded reference shape mismatch for {record.pair_id}: {reference.shape}.")
    return np.mean(raw.astype(np.float64), axis=0), np.asarray(reference)


def image_sha256(image: np.ndarray) -> str:
    data = np.ascontiguousarray(np.asarray(image))
    descriptor = f"{data.dtype.str}|{','.join(map(str, data.shape))}|".encode("ascii")
    return hashlib.sha256(descriptor + data.tobytes()).hexdigest()


def development_partition(structure: str, reference_group_id: str) -> str:
    token = f"BioSR-v9|{structure}|{reference_group_id}".encode("utf-8")
    remainder = int.from_bytes(hashlib.sha256(token).digest()[:8], "big") % 4
    return "score_design" if remainder in {0, 1} else "threshold_calibration"


def _fft_cross_correlation_peak_ratio(reference: np.ndarray, moving: np.ndarray) -> float:
    a = reference - float(np.mean(reference))
    b = moving - float(np.mean(moving))
    cross = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    cross /= np.maximum(np.abs(cross), np.finfo(float).eps)
    correlation = np.abs(np.fft.ifft2(cross))
    first_index = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
    peak = float(correlation[first_index])
    masked = correlation.copy()
    yy, xx = np.ogrid[: correlation.shape[0], : correlation.shape[1]]
    dy = np.minimum(abs(yy - first_index[0]), correlation.shape[0] - abs(yy - first_index[0]))
    dx = np.minimum(abs(xx - first_index[1]), correlation.shape[1] - abs(xx - first_index[1]))
    masked[(dy <= 2) & (dx <= 2)] = 0.0
    second = float(np.max(masked))
    return peak / max(second, np.finfo(float).eps)


def audit_pair_registration(
    input_image: np.ndarray,
    reference_image: np.ndarray,
    *,
    reference_spacing_um: float,
    effective_input_spacing_um: float,
    maximum_shift_input_pixels: float = 2.0,
    minimum_peak_ratio: float = 1.2,
) -> PairRegistration:
    """Audit residual translation after resizing the input to the reference grid."""

    moving = _robust_unit(input_image)
    fixed = _robust_unit(reference_image)
    if moving.shape != fixed.shape:
        moving = resize(moving, fixed.shape, order=1, mode="reflect", anti_aliasing=True, preserve_range=True)
    shift, error, _ = phase_cross_correlation(fixed, moving, upsample_factor=10, normalization="phase")
    peak_ratio = _fft_cross_correlation_peak_ratio(fixed, moving)
    shift_ref = (float(shift[0]), float(shift[1]))
    scale = reference_spacing_um / effective_input_spacing_um
    shift_input = (shift_ref[0] * scale, shift_ref[1] * scale)
    reasons: list[str] = []
    if max(abs(value) for value in shift_input) > maximum_shift_input_pixels:
        reasons.append("residual_translation_exceeds_two_effective_input_pixels")
    if peak_ratio < minimum_peak_ratio:
        reasons.append("registration_peak_ratio_below_1.2")
    return PairRegistration(not reasons, shift_ref, shift_input, float(peak_ratio), float(error), tuple(reasons))


def measure_structural_endpoints(
    image: np.ndarray,
    *,
    grid_spacing_um: float,
    scales_um: Sequence[float],
    spectral_band_cycles_per_mm: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Apply the frozen image estimator without using support or reference labels."""

    data = _robust_unit(image)
    scales = tuple(float(value) for value in scales_um)
    if not scales or any(value <= 0 for value in scales):
        raise ValueError("scales_um must be a nonempty positive sequence.")
    qc = acquisition_qc(data)
    tensor = structure_tensor_response(data, spacing_um=(grid_spacing_um, grid_spacing_um), scales_um=scales)
    hessian = _streaming_hessian_2d(data, spacing_um=grid_spacing_um, scales_um=scales)
    fft = extract_spatial_fft(
        data,
        pixel_size_um=grid_spacing_um,
        frequency_band_cycles_per_mm=spectral_band_cycles_per_mm,
    )
    separations = tuple(value for value in scales if value / grid_spacing_um < min(data.shape) - 1)
    if len(separations) < 2:
        raise ValueError("The image extent cannot support two requested variogram separations.")
    variogram = directional_variogram(
        data,
        spacing_um=(grid_spacing_um, grid_spacing_um),
        separations_um=separations,
    )
    horizontal_raw = np.asarray(variogram.horizontal, dtype=float)
    vertical_raw = np.asarray(variogram.vertical, dtype=float)
    spectral_scale_um = 1000.0 / fft.characteristic_frequency_cycles_per_mm
    return {
        "shape": list(data.shape),
        "grid_spacing_um": float(grid_spacing_um),
        "scales_um": list(scales),
        "qc": qc,
        "tensor_orientation": list(tensor.orientation_degrees),
        "tensor_coherence": list(tensor.coherency),
        "tensor_orientation_resultant": list(tensor.orientation_resultant),
        "spectral_orientation": float(fft.orientation_degrees),
        "spectral_anisotropy": float(fft.anisotropy),
        "spectral_entropy": float(fft.angular_entropy),
        "spectral_scale": float(spectral_scale_um),
        "spectral_band_cycles_per_mm": [
            float(fft.analysis_min_frequency_cycles_per_mm),
            float(fft.analysis_max_frequency_cycles_per_mm),
        ],
        "hessian_blob_curve": hessian["blob_curve"],
        "hessian_tube_curve": hessian["tube_curve"],
        "hessian_blob_energy": hessian["blob_energy"],
        "hessian_tube_energy": hessian["tube_energy"],
        "hessian_blob_scale": hessian["blob_scale"],
        "hessian_tube_scale": hessian["tube_scale"],
        "variogram_separations_um": list(separations),
        "variogram_horizontal_curve": _normalise_curve(horizontal_raw).tolist(),
        "variogram_vertical_curve": _normalise_curve(vertical_raw).tolist(),
        "variogram_horizontal_energy": float(np.linalg.norm(horizontal_raw)),
        "variogram_vertical_energy": float(np.linalg.norm(vertical_raw)),
        "variogram_range_horizontal": float(variogram.estimated_range_horizontal_um),
        "variogram_range_vertical": float(variogram.estimated_range_vertical_um),
    }


def _probe_images(image: np.ndarray, *, grid_spacing_um: float, effective_spacing_um: float) -> Iterable[tuple[str, float, np.ndarray]]:
    data = _robust_unit(image)
    for angle in (-3.0, 3.0):
        yield "rotation", angle, ndimage.rotate(data, angle, reshape=False, order=1, mode="reflect")
    sigma = 0.5 * effective_spacing_um / grid_spacing_um
    yield "blur", 0.5, ndimage.gaussian_filter(data, sigma=sigma, mode="reflect")
    shift = effective_spacing_um / grid_spacing_um
    yield "translation", 1.0, ndimage.shift(data, shift=(shift, -shift), order=1, mode="reflect")
    for gamma in (0.9, 1.1):
        yield "gamma", gamma, np.power(data, gamma)


def measure_with_mild_probes(
    image: np.ndarray,
    *,
    grid_spacing_um: float,
    effective_spacing_um: float,
    scales_um: Sequence[float],
    spectral_band_cycles_per_mm: tuple[float, float] | None = None,
) -> tuple[dict[str, Any], list[tuple[str, float, dict[str, Any]]]]:
    base = measure_structural_endpoints(
        image,
        grid_spacing_um=grid_spacing_um,
        scales_um=scales_um,
        spectral_band_cycles_per_mm=spectral_band_cycles_per_mm,
    )
    probes = [
        (
            name,
            magnitude,
            measure_structural_endpoints(
                candidate,
                grid_spacing_um=grid_spacing_um,
                scales_um=scales_um,
                spectral_band_cycles_per_mm=spectral_band_cycles_per_mm,
            ),
        )
        for name, magnitude, candidate in _probe_images(
            image,
            grid_spacing_um=grid_spacing_um,
            effective_spacing_um=effective_spacing_um,
        )
    ]
    return base, probes


def _endpoint_value(measurement: Mapping[str, Any], endpoint: str, scale_index: int | None) -> float | np.ndarray:
    value = measurement[endpoint]
    if endpoint in {"tensor_orientation", "tensor_coherence"}:
        if scale_index is None:
            raise ValueError(f"{endpoint} requires scale_index.")
        return float(value[scale_index])
    if endpoint.endswith("_curve"):
        return np.asarray(value, dtype=float)
    return float(value)


def _endpoint_error(endpoint: str, estimate: float | np.ndarray, reference: float | np.ndarray) -> float:
    kind = ENDPOINT_KINDS[endpoint]
    if kind == "axial":
        return axial_angular_error_degrees(float(estimate), float(reference))
    if kind == "absolute":
        return float(abs(float(estimate) - float(reference)))
    if kind == "relative":
        return _relative_error(float(estimate), float(reference))
    if kind == "log2_scale":
        return _log2_scale_error(float(estimate), float(reference))
    if kind == "curve":
        return normalized_curve_distance(np.asarray(reference), np.asarray(estimate))
    raise KeyError(endpoint)


def _correct_probe_value(endpoint: str, value: float | np.ndarray, probe_name: str, magnitude: float) -> float | np.ndarray:
    if probe_name == "rotation" and ENDPOINT_KINDS[endpoint] == "axial":
        return float((float(value) + magnitude) % 180.0)
    return value


def _probe_instability(
    endpoint: str,
    scale_index: int | None,
    base: Mapping[str, Any],
    probes: Sequence[tuple[str, float, Mapping[str, Any]]],
) -> float:
    reference = _endpoint_value(base, endpoint, scale_index)
    distances = []
    for name, magnitude, probe in probes:
        value = _endpoint_value(probe, endpoint, scale_index)
        value = _correct_probe_value(endpoint, value, name, magnitude)
        distances.append(_endpoint_error(endpoint, value, reference))
    return float(max(distances, default=0.0))


def _qc_risk(qc: Mapping[str, Any]) -> float:
    if qc["status"] == "abstain":
        return 2.0
    endpoint_risk = float(qc["observed_endpoint_fraction"]) / 0.20
    residual_risk = 3.0 / max(float(qc["contrast_to_residual"]), np.finfo(float).eps)
    focus = max(float(qc["tenengrad_focus_v2"]), 0.0)
    focus_risk = 1.0 / (1.0 + 20.0 * math.sqrt(focus))
    return float(max(endpoint_risk, residual_risk, focus_risk))


def _curve_roughness(values: Sequence[float]) -> float:
    curve = np.asarray(values, dtype=float)
    if len(curve) < 3:
        return 0.0
    return float(np.linalg.norm(np.diff(curve, n=2)) / max(np.linalg.norm(curve), np.finfo(float).eps))


def _cross_scale_risk(endpoint: str, scale_index: int | None, measurement: Mapping[str, Any]) -> float:
    if endpoint == "tensor_orientation":
        orientations = [float(value) for value in measurement[endpoint]]
        local = max(
            axial_angular_error_degrees(orientations[index], orientations[index + 1])
            for index in range(len(orientations) - 1)
        ) / 15.0
        if scale_index is not None:
            estimator = axial_angular_error_degrees(
                orientations[scale_index], float(measurement["spectral_orientation"])
            ) / 20.0
            return float(max(local, estimator))
        return float(local)
    if endpoint == "tensor_coherence":
        values = np.asarray(measurement[endpoint], dtype=float)
        return float(np.max(np.abs(np.diff(values))) / 0.20)
    if endpoint in {"hessian_blob_curve", "hessian_tube_curve"}:
        return _curve_roughness(measurement[endpoint]) / 0.25
    if endpoint in {"hessian_blob_scale", "hessian_tube_scale"}:
        curve_name = endpoint.replace("_scale", "_curve")
        curve = np.asarray(measurement[curve_name], dtype=float)
        ordered = np.sort(curve)
        margin = float(ordered[-1] - ordered[-2]) if len(ordered) > 1 else 0.0
        return float(max(0.0, 1.0 - margin / max(float(ordered[-1]), np.finfo(float).eps)))
    if endpoint == "spectral_scale":
        candidates = [float(measurement["hessian_blob_scale"]), float(measurement["hessian_tube_scale"])]
        return min(_log2_scale_error(float(measurement[endpoint]), value) for value in candidates)
    if endpoint == "spectral_anisotropy":
        tensor = float(np.mean(measurement["tensor_coherence"]))
        spectral_order = float(measurement["spectral_anisotropy"])
        return abs(tensor - spectral_order) / 0.25
    if endpoint == "spectral_entropy":
        tensor = float(np.mean(measurement["tensor_coherence"]))
        spectral_order = 1.0 - float(measurement["spectral_entropy"])
        return abs(tensor - spectral_order) / 0.25
    if endpoint.startswith("variogram_"):
        curve_name = endpoint if endpoint.endswith("_curve") else endpoint.replace("range_", "") + "_curve"
        curve = np.asarray(measurement[curve_name], dtype=float)
        monotonic_violation = float(np.sum(np.clip(-np.diff(curve), 0.0, None)))
        return monotonic_violation / 0.20
    return 0.0


def _endpoint_tolerance(endpoint: str, tolerances: Mapping[str, float]) -> float:
    mapping = {
        "tensor_orientation": "tensor_orientation_degrees",
        "tensor_coherence": "tensor_coherence_absolute",
        "spectral_anisotropy": "spectral_anisotropy_absolute",
        "spectral_entropy": "spectral_entropy_absolute",
        "spectral_scale": "spectral_scale_relative",
        "hessian_blob_curve": "normalized_response_curve_distance",
        "hessian_tube_curve": "normalized_response_curve_distance",
        "hessian_blob_scale": "winning_scale_log2_absolute",
        "hessian_tube_scale": "winning_scale_log2_absolute",
        "variogram_horizontal_curve": "normalized_variogram_curve_distance",
        "variogram_vertical_curve": "normalized_variogram_curve_distance",
        "variogram_range_horizontal": "variogram_range_relative",
        "variogram_range_vertical": "variogram_range_relative",
    }
    return float(tolerances[mapping[endpoint]])


def _reference_eligible(
    endpoint: str,
    scale_index: int | None,
    reference: Mapping[str, Any],
    reference_probes: Sequence[tuple[str, float, Mapping[str, Any]]],
    config: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...], float]:
    rules = config["reference_eligibility"]
    reasons: list[str] = []
    instability = _probe_instability(endpoint, scale_index, reference, reference_probes)
    if endpoint == "tensor_orientation":
        index = int(scale_index)
        if float(reference["tensor_orientation_resultant"][index]) < float(
            rules["minimum_orientation_resultant"]
        ):
            reasons.append("reference_orientation_resultant_below_minimum")
        if float(reference["spectral_anisotropy"]) < float(
            rules["minimum_spectral_orientation_anisotropy"]
        ):
            reasons.append("reference_spectral_orientation_anisotropy_below_minimum")
        estimator_disagreement = axial_angular_error_degrees(
            float(reference["tensor_orientation"][index]),
            float(reference["spectral_orientation"]),
        )
        if estimator_disagreement > float(
            rules["maximum_cross_estimator_orientation_disagreement_degrees"]
        ):
            reasons.append("reference_orientation_estimators_disagree")
        if instability > float(rules["maximum_reference_orientation_probe_drift_degrees"]):
            reasons.append("reference_orientation_probe_drift")
    elif endpoint in {"hessian_blob_scale", "hessian_tube_scale"}:
        curve_name = endpoint.replace("_scale", "_curve")
        peak_index = int(np.argmax(np.asarray(reference[curve_name], dtype=float)))
        if peak_index in {0, len(reference[curve_name]) - 1}:
            reasons.append("reference_scale_peak_at_search_boundary")
        if instability > float(rules["maximum_reference_scalar_probe_drift"]):
            reasons.append("reference_scalar_probe_drift")
    elif endpoint.endswith("_curve"):
        energy_name = endpoint.replace("_curve", "_energy")
        if float(reference[energy_name]) <= float(rules["minimum_normalized_curve_energy"]):
            reasons.append("reference_curve_energy_below_minimum")
        if instability > float(rules["maximum_reference_scalar_probe_drift"]):
            reasons.append("reference_curve_probe_drift")
    elif instability > float(rules["maximum_reference_scalar_probe_drift"]):
        reasons.append("reference_scalar_probe_drift")
    return not reasons, tuple(reasons), instability


def _endpoint_iter(scales: Sequence[float]) -> Iterable[tuple[str, int | None, float | None]]:
    for index, scale in enumerate(scales):
        yield "tensor_orientation", index, float(scale)
        yield "tensor_coherence", index, float(scale)
    for endpoint in (
        "spectral_anisotropy",
        "spectral_entropy",
        "spectral_scale",
        "hessian_blob_curve",
        "hessian_tube_curve",
        "hessian_blob_scale",
        "hessian_tube_scale",
        "variogram_horizontal_curve",
        "variogram_vertical_curve",
        "variogram_range_horizontal",
        "variogram_range_vertical",
    ):
        yield endpoint, None, None


def evaluate_registered_pair(
    input_image: np.ndarray,
    reference_image: np.ndarray,
    *,
    pair_id: str,
    reference_group_id: str,
    structure: str,
    input_grid_spacing_um: float,
    effective_input_spacing_um: float,
    reference_spacing_um: float,
    config: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Create endpoint-level cases while keeping support and error evidence separate."""

    scales = tuple(float(value) for value in config["physical_scales_um"])
    registration = audit_pair_registration(
        input_image,
        reference_image,
        reference_spacing_um=reference_spacing_um,
        effective_input_spacing_um=effective_input_spacing_um,
    )
    input_base, input_probes = measure_with_mild_probes(
        input_image,
        grid_spacing_um=input_grid_spacing_um,
        effective_spacing_um=effective_input_spacing_um,
        scales_um=scales,
        spectral_band_cycles_per_mm=shared_spectral_band_cycles_per_mm(
            config, effective_input_spacing_um
        ),
    )
    reference_base, reference_probes = measure_with_mild_probes(
        reference_image,
        grid_spacing_um=reference_spacing_um,
        effective_spacing_um=reference_spacing_um,
        scales_um=scales,
        spectral_band_cycles_per_mm=shared_spectral_band_cycles_per_mm(
            config, effective_input_spacing_um
        ),
    )
    return evaluate_precomputed_pair(
        pair_id=pair_id,
        reference_group_id=reference_group_id,
        structure=structure,
        effective_input_spacing_um=effective_input_spacing_um,
        registration=registration,
        input_base=input_base,
        input_probes=input_probes,
        reference_base=reference_base,
        reference_probes=reference_probes,
        config=config,
        metadata=metadata,
    )


def evaluate_precomputed_pair(
    *,
    pair_id: str,
    reference_group_id: str,
    structure: str,
    effective_input_spacing_um: float,
    registration: PairRegistration,
    input_base: Mapping[str, Any],
    input_probes: Sequence[tuple[str, float, Mapping[str, Any]]],
    reference_base: Mapping[str, Any],
    reference_probes: Sequence[tuple[str, float, Mapping[str, Any]]],
    config: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate cached estimator outputs without exposing the reference to support scoring."""

    scales = tuple(float(value) for value in config["physical_scales_um"])
    tolerances = config["invalidity_tolerances"]
    minimum_samples = float(config["minimum_samples_per_scale"])
    minimum_orientation_resultant = float(config["reference_eligibility"]["minimum_orientation_resultant"])
    qc_risk = _qc_risk(input_base["qc"])
    rows: list[dict[str, Any]] = []
    for endpoint, scale_index, requested_scale in _endpoint_iter(scales):
        reference_ok, reference_reasons, reference_instability = _reference_eligible(
            endpoint, scale_index, reference_base, reference_probes, config
        )
        estimate = _endpoint_value(input_base, endpoint, scale_index)
        truth = _endpoint_value(reference_base, endpoint, scale_index)
        error = _endpoint_error(endpoint, estimate, truth)
        tolerance = _endpoint_tolerance(endpoint, tolerances)
        perturbation = _probe_instability(endpoint, scale_index, input_base, input_probes)
        perturbation_risk = perturbation / max(tolerance, np.finfo(float).eps)
        identifiability_risk = 0.0
        orientation_resultant_risk = 0.0
        spectral_orientation_anisotropy_risk = 0.0
        orientation_estimator_disagreement_risk = 0.0
        if endpoint == "tensor_orientation":
            index = int(scale_index)
            resultant = float(input_base["tensor_orientation_resultant"][index])
            spectral_anisotropy = float(input_base["spectral_anisotropy"])
            orientation_resultant_risk = minimum_orientation_resultant / max(
                resultant, np.finfo(float).eps
            )
            minimum_spectral_anisotropy = float(
                config["reference_eligibility"]["minimum_spectral_orientation_anisotropy"]
            )
            spectral_orientation_anisotropy_risk = minimum_spectral_anisotropy / max(
                spectral_anisotropy, np.finfo(float).eps
            )
            maximum_disagreement = float(
                config["reference_eligibility"]
                ["maximum_cross_estimator_orientation_disagreement_degrees"]
            )
            orientation_estimator_disagreement_risk = axial_angular_error_degrees(
                float(input_base["tensor_orientation"][index]),
                float(input_base["spectral_orientation"]),
            ) / maximum_disagreement
            identifiability_risk = max(
                orientation_resultant_risk,
                spectral_orientation_anisotropy_risk,
                orientation_estimator_disagreement_risk,
            )
        scale_for_sampling = requested_scale
        if scale_for_sampling is None and endpoint.endswith("_scale"):
            scale_for_sampling = float(estimate)
        if scale_for_sampling is None and endpoint == "spectral_scale":
            scale_for_sampling = float(estimate)
        if scale_for_sampling is None:
            scale_for_sampling = min(scales)
        samples_per_scale = float(scale_for_sampling / effective_input_spacing_um)
        sampling_risk = max(0.0, (minimum_samples - samples_per_scale) / minimum_samples)
        hard_reasons: list[str] = []
        if samples_per_scale < minimum_samples:
            hard_reasons.append("fewer_than_four_effective_samples_per_requested_scale")
        if input_base["qc"]["status"] == "abstain":
            hard_reasons.append("acquisition_qc_abstain")
        if endpoint == "tensor_orientation":
            if orientation_resultant_risk > 1.0:
                hard_reasons.append("input_orientation_resultant_below_minimum")
            if spectral_orientation_anisotropy_risk > 1.0:
                hard_reasons.append("input_spectral_orientation_anisotropy_below_minimum")
            if orientation_estimator_disagreement_risk > 1.0:
                hard_reasons.append("input_orientation_estimators_disagree")
        if endpoint in {"hessian_blob_scale", "hessian_tube_scale"}:
            curve_name = endpoint.replace("_scale", "_curve")
            peak_index = int(np.argmax(np.asarray(input_base[curve_name], dtype=float)))
            if peak_index in {0, len(input_base[curve_name]) - 1}:
                hard_reasons.append("input_scale_peak_at_search_boundary")
        cross_scale_risk = _cross_scale_risk(endpoint, scale_index, input_base)
        full_score = float(max(qc_risk, sampling_risk, perturbation_risk, identifiability_risk))
        exploratory_cross_scale_score = float(max(full_score, cross_scale_risk))
        score_map = {
            "always_emit": 0.0,
            "conventional_acquisition_qc": qc_risk,
            "physical_sampling_only": sampling_risk,
            "perturbation_stability_only": perturbation_risk,
            "cross_scale_diagnostic_only": cross_scale_risk,
            "full_contract": full_score,
            "full_contract_without_qc": float(
                max(sampling_risk, perturbation_risk, identifiability_risk)
            ),
            "full_contract_without_sampling": float(
                max(qc_risk, perturbation_risk, identifiability_risk)
            ),
            "full_contract_without_perturbation": float(
                max(qc_risk, sampling_risk, identifiability_risk)
            ),
            "exploratory_full_contract_with_cross_scale_diagnostic": exploratory_cross_scale_score,
            "full_contract_without_identifiability": float(
                max(qc_risk, sampling_risk, perturbation_risk)
            ),
        }
        case_id = f"{pair_id}|{endpoint}|{requested_scale if requested_scale is not None else 'global'}"
        rows.append(
            {
                "case_id": case_id,
                "pair_id": pair_id,
                "reference_group_id": reference_group_id,
                "structure": structure,
                "development_partition": development_partition(structure, reference_group_id),
                "endpoint": endpoint,
                "requested_scale_um": requested_scale,
                "pair_registration_eligible": registration.eligible,
                "pair_registration": asdict(registration),
                "reference_eligible": bool(reference_ok),
                "reference_eligibility_reasons": list(reference_reasons),
                "reference_probe_instability": float(reference_instability),
                "error": float(error),
                "invalidity_tolerance": float(tolerance),
                "invalid": bool(error > tolerance),
                "hard_abstention": bool(hard_reasons),
                "hard_abstention_reasons": hard_reasons,
                "support_components": {
                    "acquisition_qc": float(qc_risk),
                    "physical_sampling": float(sampling_risk),
                    "perturbation_stability": float(perturbation_risk),
                    "cross_scale_agreement": float(cross_scale_risk),
                    "measurement_identifiability": float(identifiability_risk),
                    "orientation_resultant_risk": float(orientation_resultant_risk),
                    "spectral_orientation_anisotropy_risk": float(
                        spectral_orientation_anisotropy_risk
                    ),
                    "orientation_estimator_disagreement_risk": float(
                        orientation_estimator_disagreement_risk
                    ),
                    "samples_per_scale": samples_per_scale,
                    "raw_probe_instability": float(perturbation),
                },
                "scores": score_map,
                "input_measurement": np.asarray(estimate).tolist(),
                "reference_measurement": np.asarray(truth).tolist(),
                "metadata": dict(metadata or {}),
            }
        )
    return rows


def eligible_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])]


def risk_coverage_curve(rows: Sequence[Mapping[str, Any]], condition: str) -> list[dict[str, float]]:
    cases = eligible_rows(rows)
    if not cases:
        return []
    ordered = sorted(cases, key=lambda row: (float(row["scores"][condition]), str(row["case_id"])))
    curve: list[dict[str, float]] = []
    invalid = 0
    index = 0
    while index < len(ordered):
        score = float(ordered[index]["scores"][condition])
        end = index
        while end < len(ordered) and float(ordered[end]["scores"][condition]) == score:
            invalid += int(bool(ordered[end]["invalid"]))
            end += 1
        curve.append(
            {
                "threshold": score,
                "accepted": float(end),
                "coverage": float(end / len(ordered)),
                "risk": float(invalid / end),
            }
        )
        index = end
    return curve


def aurc(rows: Sequence[Mapping[str, Any]], condition: str) -> float:
    curve = risk_coverage_curve(rows, condition)
    if not curve:
        return float("nan")
    area = 0.0
    previous = 0.0
    for point in curve:
        area += (point["coverage"] - previous) * point["risk"]
        previous = point["coverage"]
    return float(area)


def _risk_at_threshold(rows: Sequence[Mapping[str, Any]], threshold: float, condition: str) -> tuple[int, int, float, float | None]:
    cases = eligible_rows(rows)
    accepted = [
        row
        for row in cases
        if not bool(row["hard_abstention"]) and float(row["scores"][condition]) <= threshold
    ]
    coverage = len(accepted) / len(cases) if cases else 0.0
    risk = float(np.mean([bool(row["invalid"]) for row in accepted])) if accepted else None
    return len(accepted), len(cases), coverage, risk


def cluster_bootstrap_risk_upper(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    condition: str,
    draws: int,
    seed: int,
) -> float | None:
    cases = eligible_rows(rows)
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in cases:
        groups.setdefault(str(row["reference_group_id"]), []).append(row)
    identifiers = sorted(groups)
    if not identifiers:
        return None
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sampled = rng.choice(identifiers, size=len(identifiers), replace=True)
        accepted_invalid: list[bool] = []
        for identifier in sampled:
            for row in groups[str(identifier)]:
                if not bool(row["hard_abstention"]) and float(row["scores"][condition]) <= threshold:
                    accepted_invalid.append(bool(row["invalid"]))
        if accepted_invalid:
            estimates.append(float(np.mean(accepted_invalid)))
    return float(np.quantile(estimates, 0.95)) if estimates else None


def select_operating_threshold(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition: str = "full_contract",
    target_risk: float = 0.10,
    maximum_risk_upper95: float = 0.15,
    draws: int = 10_000,
    seed: int = 26_082_801,
) -> ThresholdSelection:
    cases = eligible_rows(rows)
    candidates = sorted(
        {
            float(row["scores"][condition])
            for row in cases
            if not bool(row["hard_abstention"])
        }
    )
    selected: ThresholdSelection | None = None
    for threshold in candidates:
        accepted, total, coverage, risk = _risk_at_threshold(cases, threshold, condition)
        if accepted == 0 or risk is None or risk > target_risk:
            continue
        upper = cluster_bootstrap_risk_upper(
            cases,
            threshold=threshold,
            condition=condition,
            draws=draws,
            seed=seed,
        )
        if upper is None or upper > maximum_risk_upper95:
            continue
        candidate = ThresholdSelection(
            "operating_point_selected",
            threshold,
            accepted,
            total,
            coverage,
            risk,
            upper,
            len(candidates),
            target_risk,
            maximum_risk_upper95,
        )
        if selected is None or candidate.coverage > selected.coverage:
            selected = candidate
    if selected is not None:
        return selected
    return ThresholdSelection(
        "no_operating_point",
        None,
        0,
        len(cases),
        0.0,
        None,
        None,
        len(candidates),
        target_risk,
        maximum_risk_upper95,
    )


def write_rows_jsonl(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
