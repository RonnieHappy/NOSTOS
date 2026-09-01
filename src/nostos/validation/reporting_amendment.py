"""Non-analytical amendments for immutable NOSTOS audit artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from nostos.validation.validity_profile_compiler import canonical_sha256


LEGACY_AURC_LABEL = (
    "acquisition_qc_AURC_minus_full_contract_AURC; positive favors NOSTOS"
)
PRIMARY_CANDIDATE_AURC_LABEL = (
    "acquisition_qc_AURC_minus_primary_candidate_AURC; positive favors NOSTOS"
)


def verify_content_hash(payload: Mapping[str, Any]) -> None:
    expected = str(payload.get("content_sha256", ""))
    content = dict(payload)
    content.pop("content_sha256", None)
    if not expected or canonical_sha256(content) != expected:
        raise ValueError("Source audit content hash mismatch.")


def amend_primary_candidate_aurc_label(
    source: Mapping[str, Any],
    *,
    source_file_sha256: str,
) -> dict[str, Any]:
    """Correct one legacy label without recomputing a statistic or gate."""

    verify_content_hash(source)
    output = deepcopy(dict(source))
    difference = output["risk_coverage"]["cluster_bootstrap_aurc_difference"]
    if difference.get("definition") != LEGACY_AURC_LABEL:
        raise ValueError("Source audit does not contain the recognized legacy AURC label.")
    source_content_sha256 = str(output.pop("content_sha256"))
    output["schema_version"] = (
        "nostos-validity-profile-confirmation-audit/1.2-reporting-amendment"
    )
    difference["definition"] = PRIMARY_CANDIDATE_AURC_LABEL
    output["reporting_amendment"] = {
        "source_audit_file_sha256": str(source_file_sha256),
        "source_audit_content_sha256": source_content_sha256,
        "changed_paths": [
            "schema_version",
            "risk_coverage.cluster_bootstrap_aurc_difference.definition",
            "reporting_amendment",
        ],
        "reason": (
            "The legacy label named full_contract even when the frozen profile selected "
            "a different primary candidate. The AURC values always compared acquisition "
            "QC with profile.primary_score."
        ),
        "statistical_values_recomputed": False,
        "confirmation_rows_reprocessed": False,
        "profile_refit": False,
        "gate_decisions_changed": False,
    }
    output["content_sha256"] = canonical_sha256(output)
    return output
