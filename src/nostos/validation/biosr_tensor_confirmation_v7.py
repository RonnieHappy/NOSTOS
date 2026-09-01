"""Frozen-layout BioSR indexing and evaluation for NOSTOS tensor v7."""

from __future__ import annotations

import hashlib
import re
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from nostos.validation.paired_acquisition_support import (
    BioSRPairRecord,
    _mrc_header_from_bytes,
)
from nostos.validation.tensor_contract_audit_v7 import (
    incremental_comparator,
    summarize_policy,
)
from nostos.validation.tensor_evidence_v7 import (
    COHERENCE_FAMILY,
    clustered_coherence_aurc_difference,
)


SELECTION_SALT = "NOSTOS-v7-initial-confirmation"


def select_confirmation_cells_v7(
    cell_ids: Sequence[str],
    *,
    structure: str,
    count: int,
    salt: str = SELECTION_SALT,
) -> list[str]:
    """Select fields by a pixel- and outcome-independent hash ranking."""

    cells = sorted({str(cell) for cell in cell_ids})
    if count < 1:
        raise ValueError("Confirmation field count must be positive.")
    if len(cells) < count:
        raise ValueError(
            f"{structure} contains only {len(cells)} fields; {count} were frozen."
        )
    return sorted(
        cells,
        key=lambda cell: hashlib.sha256(
            f"{salt}|{structure}|{structure}|{cell}".encode("utf-8")
        ).hexdigest(),
    )[:count]


def archive_layout_from_central_directory(
    archive: Path,
    *,
    structure: str,
    expected_level_count: int,
    reference_basename: str,
    excluded_reference_basenames: Sequence[str] = (),
) -> dict[str, Any]:
    """Inspect only ZIP names and sizes; do not open any image member."""

    input_pattern = re.compile(
        r"^[^/]+/(?P<cell>Cell_\d+)/RawSIMData_level_(?P<level>\d{2})\.mrc$",
        re.I,
    )
    reference_pattern = re.compile(
        rf"^[^/]+/(?P<cell>Cell_\d+)/{re.escape(reference_basename)}$",
        re.I,
    )
    excluded_patterns = [
        re.compile(
            rf"^[^/]+/(?P<cell>Cell_\d+)/{re.escape(name)}$",
            re.I,
        )
        for name in excluded_reference_basenames
    ]
    levels: dict[str, set[int]] = defaultdict(set)
    references: dict[str, str] = {}
    excluded: dict[str, list[str]] = defaultdict(list)
    with zipfile.ZipFile(archive) as opened:
        for info in opened.infolist():
            match = input_pattern.match(info.filename)
            if match:
                levels[match.group("cell")].add(int(match.group("level")))
                continue
            match = reference_pattern.match(info.filename)
            if match:
                cell = match.group("cell")
                if cell in references:
                    raise ValueError(f"Duplicate primary reference for {cell}.")
                references[cell] = info.filename
                continue
            for pattern in excluded_patterns:
                match = pattern.match(info.filename)
                if match:
                    excluded[match.group("cell")].append(info.filename)
                    break
    expected = set(range(1, expected_level_count + 1))
    cells = sorted(set(levels) | set(references))
    failures: dict[str, Any] = {}
    for cell in cells:
        reasons = []
        if levels.get(cell, set()) != expected:
            reasons.append(
                {
                    "level_set": sorted(levels.get(cell, set())),
                    "expected": sorted(expected),
                }
            )
        if cell not in references:
            reasons.append({"missing_primary_reference": reference_basename})
        if reasons:
            failures[cell] = reasons
    if failures:
        raise ValueError(f"BioSR central-directory layout failed: {failures}")
    return {
        "structure": structure,
        "cells": cells,
        "cell_count": len(cells),
        "expected_levels": sorted(expected),
        "primary_reference_basename": reference_basename,
        "excluded_reference_basenames": list(excluded_reference_basenames),
        "excluded_references_present": {
            cell: sorted(excluded.get(cell, [])) for cell in cells
        },
        "member_bytes_opened": 0,
        "pixel_arrays_decoded": 0,
    }


def index_biosr_tensor_archive_v7(
    archive: Path,
    *,
    structure: str,
    expected_raw_spacing_um: float,
    upscaling_factor: int,
    expected_level_count: int,
    expected_input_frames: int,
    reference_basename: str,
    spacing_absolute_tolerance_um: float = 1e-6,
    field_of_view_relative_tolerance: float = 1e-6,
) -> list[BioSRPairRecord]:
    """Index the frozen F-actin layouts by reading MRC headers, never pixels."""

    if upscaling_factor not in {2, 3}:
        raise ValueError("BioSR upscaling_factor must be two or three.")
    if expected_level_count < 1 or expected_input_frames < 1:
        raise ValueError("Expected levels and input frames must be positive.")
    if expected_raw_spacing_um <= 0:
        raise ValueError("Expected raw spacing must be positive.")
    input_pattern = re.compile(
        r"^[^/]+/(?P<cell>Cell_\d+)/RawSIMData_level_(?P<level>\d{2})\.mrc$",
        re.I,
    )
    reference_pattern = re.compile(
        rf"^[^/]+/(?P<cell>Cell_\d+)/{re.escape(reference_basename)}$",
        re.I,
    )
    references: dict[str, tuple[str, Any]] = {}
    inputs: list[tuple[str, str, int, Any]] = []
    with zipfile.ZipFile(archive) as opened:
        for info in opened.infolist():
            reference_match = reference_pattern.match(info.filename)
            input_match = input_pattern.match(info.filename)
            if reference_match:
                with opened.open(info, "r") as stream:
                    header = _mrc_header_from_bytes(stream.read(1024))
                cell = reference_match.group("cell")
                if cell in references:
                    raise ValueError(f"Duplicate primary reference for {cell}.")
                references[cell] = (info.filename, header)
            elif input_match:
                with opened.open(info, "r") as stream:
                    header = _mrc_header_from_bytes(stream.read(1024))
                inputs.append(
                    (
                        input_match.group("cell"),
                        info.filename,
                        int(input_match.group("level")),
                        header,
                    )
                )
    records: list[BioSRPairRecord] = []
    for cell, member, level, input_header in sorted(inputs):
        if cell not in references:
            raise ValueError(f"Missing {reference_basename} for {cell}.")
        reference_member, reference_header = references[cell]
        if (
            input_header.nz != expected_input_frames
            or reference_header.nz != 1
            or input_header.mode not in {1, 2, 6}
            or reference_header.mode not in {1, 2, 6}
        ):
            raise ValueError(f"Unexpected BioSR MRC layout for {cell}, level {level:02d}.")
        ratios = (
            reference_header.ny / input_header.ny,
            reference_header.nx / input_header.nx,
        )
        if not np.allclose(ratios, upscaling_factor, rtol=0, atol=1e-12):
            raise ValueError(
                f"Declared {upscaling_factor}x factor disagrees with dimensions for {cell}: {ratios}."
            )
        input_spacing = np.asarray(input_header.spacing_yx_um, dtype=float)
        reference_spacing = np.asarray(reference_header.spacing_yx_um, dtype=float)
        expected_reference_spacing = expected_raw_spacing_um / upscaling_factor
        if not np.allclose(
            input_spacing,
            expected_raw_spacing_um,
            rtol=0,
            atol=spacing_absolute_tolerance_um,
        ):
            raise ValueError(
                f"Raw spacing mismatch for {cell}, level {level:02d}: {input_spacing.tolist()}."
            )
        if not np.allclose(
            reference_spacing,
            expected_reference_spacing,
            rtol=0,
            atol=spacing_absolute_tolerance_um,
        ):
            raise ValueError(
                f"Reference spacing mismatch for {cell}: {reference_spacing.tolist()}."
            )
        input_fov = input_spacing * np.asarray(
            (input_header.ny, input_header.nx), dtype=float
        )
        reference_fov = reference_spacing * np.asarray(
            (reference_header.ny, reference_header.nx), dtype=float
        )
        if not np.allclose(
            input_fov,
            reference_fov,
            rtol=field_of_view_relative_tolerance,
            atol=0,
        ):
            raise ValueError(
                f"Raw/reference field of view mismatch for {cell}, level {level:02d}."
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
                input_frames=input_header.nz,
                input_shape_yx=(input_header.ny, input_header.nx),
                reference_shape_yx=(reference_header.ny, reference_header.nx),
                input_grid_spacing_um=float(expected_raw_spacing_um),
                effective_input_spacing_um=float(expected_raw_spacing_um),
                reference_spacing_um=float(expected_reference_spacing),
                input_header_spacing_yx_um=tuple(
                    float(value) for value in input_spacing
                ),
                reference_header_spacing_yx_um=tuple(
                    float(value) for value in reference_spacing
                ),
                physical_field_of_view_yx_um=tuple(
                    float(value) for value in input_fov
                ),
                archive_layout=(
                    "flat_shared_reference_linear"
                    if upscaling_factor == 2
                    else "flat_shared_reference_nonlinear_primary_a"
                ),
            )
        )
    expected_levels = set(range(1, expected_level_count + 1))
    by_cell: dict[str, set[int]] = defaultdict(set)
    for record in records:
        by_cell[record.cell_id].add(record.signal_level)
    if set(by_cell) != set(references):
        raise ValueError("Input and reference cell sets differ.")
    incomplete = {
        cell: sorted(levels)
        for cell, levels in by_cell.items()
        if levels != expected_levels
    }
    if incomplete:
        raise ValueError(
            f"BioSR cells do not contain exactly levels 01-{expected_level_count:02d}: {incomplete}"
        )
    return records


def evaluate_v7_confirmation(
    rows: Sequence[Mapping[str, Any]],
    *,
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate safety and incremental coherence utility as separate claims."""

    full = summarize_policy(rows, condition="full_contract")
    qc = summarize_policy(rows, condition="conventional_acquisition_qc")
    safety = bool(
        full["coverage"] >= float(rules["minimum_overall_coverage"])
        and full["risk"] is not None
        and full["risk"] <= float(rules["target_observed_risk"])
        and full["cluster_bootstrap_risk_upper95"] is not None
        and full["cluster_bootstrap_risk_upper95"]
        <= float(rules["maximum_cluster_bootstrap_risk_upper95"])
        and all(
            item["coverage"]
            >= float(rules["minimum_structure_family_coverage"])
            and item["risk"] is not None
            and item["risk"] <= float(rules["target_observed_risk"])
            and item["cluster_bootstrap_risk_upper95"] is not None
            and item["cluster_bootstrap_risk_upper95"]
            <= float(rules["maximum_cluster_bootstrap_risk_upper95"])
            for item in full["combinations"]
        )
    )
    coherence = [
        row for row in rows if str(row["endpoint_family"]) == COHERENCE_FAMILY
    ]
    comparator = incremental_comparator(coherence)
    evidence = clustered_coherence_aurc_difference(
        coherence,
        draws=int(rules["bootstrap_replicates"]),
        seed=int(rules["bootstrap_seed"]),
    )
    comparator_invalid = sum(
        bool(row["invalid"])
        for row in coherence
        if bool(row["pair_registration_eligible"])
        and bool(row["reference_eligible"])
        and float(row["scores"]["conventional_acquisition_qc"]) <= 1.0
        and "acquisition_qc_abstain" not in set(row["hard_abstention_reasons"])
    )
    if comparator_invalid == 0:
        utility_status = "not_assessable_no_invalid_comparator_emissions"
        utility_passes = None
    else:
        bootstrap = evidence["bootstrap"]
        enrichment = comparator[
            "invalid_enrichment_among_comparator_only_rejections"
        ]
        utility_passes = bool(
            comparator["full_minus_comparator_risk"]
            <= float(rules["maximum_full_minus_qc_risk"])
            and comparator["coverage_loss_vs_comparator"]
            <= float(rules["maximum_full_coverage_loss_vs_qc"])
            and enrichment is not None
            and enrichment
            >= float(rules["minimum_invalid_enrichment_among_qc_only_rejections"])
            and evidence["observed"]["comparator_minus_full"] > 0
            and bootstrap["probability_full_better"] is not None
            and bootstrap["probability_full_better"]
            >= float(rules["minimum_bootstrap_probability_full_better"])
            and bootstrap["ci95"][0] is not None
            and bootstrap["ci95"][0] > 0
        )
        utility_status = "confirmed" if utility_passes else "failed"
    if not safety:
        status = "measurement_safety_failed"
    elif utility_passes is True:
        status = "measurement_safety_and_incremental_coherence_utility_confirmed"
    elif utility_passes is None:
        status = "measurement_safety_confirmed_incremental_utility_not_assessable"
    else:
        status = "measurement_safety_confirmed_incremental_utility_failed"
    return {
        "status": status,
        "measurement_safety": {
            "passes": safety,
            "full_contract": full,
            "conventional_acquisition_qc": qc,
        },
        "incremental_coherence_utility": {
            "status": utility_status,
            "passes": utility_passes,
            "comparator_invalid_emissions": comparator_invalid,
            "operating_point": comparator,
            "risk_coverage_evidence": evidence,
        },
    }

