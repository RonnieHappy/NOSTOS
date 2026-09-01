"""Operator-facing evidence boundary for unstained PSHG execution."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from nostos.intraop.label_free_v1_4 import analyze_pshg_directory as analyze_pshg_directory_v1_4


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_records(paths: list[Path]) -> list[dict[str, Any]]:
    return [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in paths
    ]


def verify_public_acquisition_bundle(
    records: list[dict[str, Any]],
    lock_path: Path,
) -> dict[str, Any]:
    """Match a deployment input to a complete hash-locked public acquisition bundle."""

    observed = {
        str(item["name"]).lower(): (int(item["bytes"]), str(item["sha256"]))
        for item in records
    }
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    grouped: dict[str, dict[str, tuple[int, str]]] = {}
    for item in lock["selected_source_files"]:
        relative = Path(item["relative_path"])
        if relative.name.lower() == "fi.tif":
            continue
        grouped.setdefault(relative.parent.as_posix(), {})[relative.name.lower()] = (
            int(item["bytes"]),
            str(item["sha256"]),
        )
    matches = [group for group, expected in grouped.items() if expected == observed]
    return {
        "status": "verified_public_bundle" if len(matches) == 1 else "unverified_new_acquisition",
        "verified": len(matches) == 1,
        "matched_group": matches[0] if len(matches) == 1 else None,
        "lock_file": lock_path.name,
        "lock_sha256": _sha256(lock_path),
        "required_files": len(observed),
        "policy": "Hash identity can confirm archived public inputs; formatting alone cannot validate a new instrument or acquisition.",
    }


def apply_operator_evidence_boundary(
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed when a format-compatible acquisition lacks validated provenance."""

    bounded = copy.deepcopy(payload)
    bounded["operator_provenance"] = provenance
    bounded["clinical_output"]["status"] = "withheld"
    if provenance["verified"]:
        return bounded
    if bounded["status"] != "abstain":
        bounded["status"] = "review"
    bounded["measurement"]["evidence_status"] = "unvalidated_new_acquisition"
    reasons = set(bounded.get("validity_reasons", []))
    reasons.add("acquisition_provenance_not_independently_verified")
    bounded["validity_reasons"] = sorted(reasons)
    bounded["profile"]["evidence_scope"] = (
        "The algorithmic input shape matches the public PSHG profile, but the instrument, "
        "calibration and acquisition family have not been independently bridged."
    )
    return bounded


def analyze_operator_pshg_directory(
    directory: Path,
    output: Path,
    *,
    profile_path: Path,
    public_lock_path: Path,
    pixel_size_um: float = 1.0,
    include_reference_evaluation: bool = False,
) -> dict[str, Any]:
    payload = analyze_pshg_directory_v1_4(
        directory,
        output,
        profile_path=profile_path,
        pixel_size_um=pixel_size_um,
        include_reference_evaluation=include_reference_evaluation,
    )
    provenance = verify_public_acquisition_bundle(payload["source_files"], public_lock_path)
    bounded = apply_operator_evidence_boundary(payload, provenance)
    (output / "intraop_result.json").write_text(
        json.dumps(bounded, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return bounded
