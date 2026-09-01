"""Executable claim-boundary guard for measurement-validity profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


PROFILE_DOMAIN_GUARD_VERSION = "nostos-profile-domain-guard/1.0"


def assess_profile_context(
    observed: Mapping[str, Any],
    *,
    certified: Mapping[str, Any],
    required_fields: Sequence[str],
) -> dict[str, Any]:
    """Return an input-only applicability decision for a serialized profile."""

    missing = [str(key) for key in required_fields if key not in observed]
    mismatches = [
        {
            "field": str(key),
            "expected": certified.get(str(key)),
            "observed": observed.get(str(key)),
        }
        for key in required_fields
        if key in observed and observed.get(str(key)) != certified.get(str(key))
    ]
    applicable = not missing and not mismatches
    reasons = [f"profile_claim_boundary:missing:{key}" for key in missing]
    reasons.extend(
        f"profile_claim_boundary:mismatch:{item['field']}" for item in mismatches
    )
    return {
        "guard_version": PROFILE_DOMAIN_GUARD_VERSION,
        "applicable": applicable,
        "required_fields": [str(key) for key in required_fields],
        "missing_fields": missing,
        "mismatches": mismatches,
        "abstention_reasons": reasons,
    }


def row_profile_context(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata", {})
    return {
        "acquisition_modality": metadata.get("acquisition_modality"),
        "sample": metadata.get("sample"),
        "calibration_status": row.get("calibration_status"),
    }


def apply_profile_domain_guard(
    rows: Sequence[Mapping[str, Any]],
    *,
    certified: Mapping[str, Any],
    required_fields: Sequence[str],
) -> list[dict[str, Any]]:
    """Fail closed outside the certified profile context without changing inputs."""

    guarded: list[dict[str, Any]] = []
    for row in rows:
        clone = deepcopy(dict(row))
        decision = assess_profile_context(
            row_profile_context(row),
            certified=certified,
            required_fields=required_fields,
        )
        clone["profile_domain_guard"] = decision
        clone["pre_guard_candidate_hard_abstention"] = bool(
            row["candidate_hard_abstention"]
        )
        clone["pre_guard_calibrated_risk"] = float(row["calibrated_risk"])
        if not decision["applicable"]:
            clone["candidate_hard_abstention"] = True
            clone["calibrated_risk"] = 1.0
            clone["profile_domain_guard_hard_abstention"] = True
        else:
            clone["profile_domain_guard_hard_abstention"] = False
        guarded.append(clone)
    return guarded

