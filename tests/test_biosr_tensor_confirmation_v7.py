from __future__ import annotations

import struct
import zipfile
from pathlib import Path

from nostos.validation.biosr_tensor_confirmation_v7 import (
    archive_layout_from_central_directory,
    index_biosr_tensor_archive_v7,
    select_confirmation_cells_v7,
)


def _header(nx: int, ny: int, nz: int, spacing: float) -> bytes:
    payload = bytearray(1024)
    struct.pack_into("<4i", payload, 0, nx, ny, nz, 1)
    struct.pack_into("<3i", payload, 28, nx, ny, nz)
    struct.pack_into(
        "<3f", payload, 40, spacing * nx, spacing * ny, spacing * nz
    )
    struct.pack_into("<i", payload, 92, 0)
    return bytes(payload)


def _archive(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as opened:
        for cell in ("Cell_001", "Cell_002"):
            opened.writestr(
                f"F-actin_Nonlinear/{cell}/SIM_gt_a.mrc",
                _header(96, 96, 1, 0.02),
            )
            opened.writestr(
                f"F-actin_Nonlinear/{cell}/SIM_gt_b.mrc",
                _header(96, 96, 1, 0.02),
            )
            for level in range(1, 3):
                opened.writestr(
                    f"F-actin_Nonlinear/{cell}/RawSIMData_level_{level:02d}.mrc",
                    _header(32, 32, 25, 0.06),
                )


def test_hash_selection_is_order_independent() -> None:
    first = select_confirmation_cells_v7(
        ["Cell_003", "Cell_001", "Cell_002"],
        structure="F-actin_linear",
        count=2,
    )
    second = select_confirmation_cells_v7(
        ["Cell_002", "Cell_003", "Cell_001"],
        structure="F-actin_linear",
        count=2,
    )
    assert first == second


def test_central_layout_does_not_open_member_bytes(tmp_path: Path) -> None:
    archive = tmp_path / "nonlinear.zip"
    _archive(archive)
    result = archive_layout_from_central_directory(
        archive,
        structure="F-actin_nonlinear",
        expected_level_count=2,
        reference_basename="SIM_gt_a.mrc",
        excluded_reference_basenames=("SIM_gt_b.mrc",),
    )
    assert result["cell_count"] == 2
    assert result["member_bytes_opened"] == 0
    assert all(result["excluded_references_present"].values())


def test_nonlinear_index_uses_primary_a_and_25_frames(tmp_path: Path) -> None:
    archive = tmp_path / "nonlinear.zip"
    _archive(archive)
    records = index_biosr_tensor_archive_v7(
        archive,
        structure="F-actin_nonlinear",
        expected_raw_spacing_um=0.06,
        upscaling_factor=3,
        expected_level_count=2,
        expected_input_frames=25,
        reference_basename="SIM_gt_a.mrc",
    )
    assert len(records) == 4
    assert all(record.input_frames == 25 for record in records)
    assert all(record.reference_member.endswith("SIM_gt_a.mrc") for record in records)

