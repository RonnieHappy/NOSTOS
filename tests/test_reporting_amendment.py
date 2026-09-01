from __future__ import annotations

from copy import deepcopy

import pytest

from nostos.validation.reporting_amendment import (
    LEGACY_AURC_LABEL,
    PRIMARY_CANDIDATE_AURC_LABEL,
    amend_primary_candidate_aurc_label,
)
from nostos.validation.validity_profile_compiler import canonical_sha256


def _audit() -> dict:
    payload = {
        "schema_version": "nostos-validity-profile-confirmation-audit/1.1",
        "status": "pass",
        "risk_coverage": {
            "cluster_bootstrap_aurc_difference": {
                "definition": LEGACY_AURC_LABEL,
                "observed": 0.2,
                "bootstrap_ci95": [0.1, 0.3],
            }
        },
        "checks": {"gate": True},
    }
    payload["content_sha256"] = canonical_sha256(payload)
    return payload


def test_reporting_amendment_changes_no_statistic_or_gate() -> None:
    source = _audit()
    amended = amend_primary_candidate_aurc_label(
        source, source_file_sha256="a" * 64
    )
    assert amended["status"] == source["status"]
    assert amended["checks"] == source["checks"]
    assert (
        amended["risk_coverage"]["cluster_bootstrap_aurc_difference"]["observed"]
        == 0.2
    )
    assert (
        amended["risk_coverage"]["cluster_bootstrap_aurc_difference"]["definition"]
        == PRIMARY_CANDIDATE_AURC_LABEL
    )
    assert amended["reporting_amendment"]["statistical_values_recomputed"] is False


def test_reporting_amendment_rejects_tampered_source() -> None:
    source = _audit()
    damaged = deepcopy(source)
    damaged["status"] = "fail"
    with pytest.raises(ValueError, match="content hash mismatch"):
        amend_primary_candidate_aurc_label(damaged, source_file_sha256="b" * 64)
