from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from nostos.validation.profile_domain_guard import apply_profile_domain_guard
from nostos.validation.validity_profile_compiler import (
    canonical_sha256,
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)


def accepted(row: Mapping[str, Any], threshold: float) -> bool:
    return not bool(row["candidate_hard_abstention"]) and float(
        row["calibrated_risk"]
    ) <= threshold


def summarize(rows: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    emitted = [row for row in rows if accepted(row, threshold)]
    return {
        "rows": len(rows),
        "independent_groups": len({str(row["reference_group_id"]) for row in rows}),
        "accepted": len(emitted),
        "coverage": len(emitted) / len(rows) if rows else 0.0,
        "invalid": sum(bool(row["invalid"]) for row in emitted),
        "risk": (
            sum(bool(row["invalid"]) for row in emitted) / len(emitted)
            if emitted
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the post-failure FMD profile-domain guard development repair."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config_path = args.config.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    inputs = {}
    for key, spec in config["frozen_inputs"].items():
        path = project_root / spec["path"]
        if sha256_file(path) != spec["sha256"]:
            raise ValueError(f"Frozen input hash mismatch: {key}")
        inputs[key] = path
    strict = json.loads(inputs["strict_profile"].read_text(encoding="utf-8"))
    threshold = float(strict["base_predicted_risk_threshold"])
    in_scope = read_jsonl(inputs["in_scope_development_scored"])
    external = read_jsonl(inputs["external_transfer_scored"])
    certified = config["certified_context"]
    required = config["required_context_fields"]
    guarded_in = apply_profile_domain_guard(
        in_scope, certified=certified, required_fields=required
    )
    guarded_external = apply_profile_domain_guard(
        external, certified=certified, required_fields=required
    )
    pre_in = summarize(in_scope, threshold)
    post_in = summarize(guarded_in, threshold)
    pre_external = summarize(external, threshold)
    post_external = summarize(guarded_external, threshold)
    sources = {}
    for source in sorted(
        {str(row["metadata"]["transfer_source_key"]) for row in external}
    ):
        before = [
            row for row in external if row["metadata"]["transfer_source_key"] == source
        ]
        after = [
            row
            for row in guarded_external
            if row["metadata"]["transfer_source_key"] == source
        ]
        sources[source] = {
            "before_guard": summarize(before, threshold),
            "after_guard": summarize(after, threshold),
            "guard_reasons": dict(
                sorted(
                    Counter(
                        reason
                        for row in after
                        for reason in row["profile_domain_guard"]["abstention_reasons"]
                    ).items()
                )
            ),
        }
    checks = {
        "all_in_scope_rows_applicable": all(
            row["profile_domain_guard"]["applicable"] for row in guarded_in
        ),
        "in_scope_decision_identity": all(
            bool(before["candidate_hard_abstention"])
            == bool(after["candidate_hard_abstention"])
            and float(before["calibrated_risk"]) == float(after["calibrated_risk"])
            for before, after in zip(in_scope, guarded_in, strict=True)
        ),
        "all_external_rows_out_of_scope": all(
            not row["profile_domain_guard"]["applicable"] for row in guarded_external
        ),
        "zero_guarded_external_emissions": post_external["accepted"] == 0,
        "zero_guarded_external_invalid_emissions": post_external["invalid"] == 0,
    }
    audit = {
        "schema_version": "nostos-profile-domain-guard-development-audit/1.0",
        "status": "pass_development_only" if all(checks.values()) else "fail",
        "protocol_id": config["protocol_id"],
        "interpretation": "Post-failure engineering repair. Exact claim-boundary matching preserves every in-scope decision and blocks both known out-of-scope transfers; it does not establish a new transferable measurement domain.",
        "threshold": threshold,
        "certified_context": certified,
        "required_context_fields": required,
        "in_scope": {"before_guard": pre_in, "after_guard": post_in},
        "external": {
            "before_guard": pre_external,
            "after_guard": post_external,
            "sources": sources,
        },
        "checks": checks,
        "source_hashes": {
            key: {"path": spec["path"], "sha256": spec["sha256"]}
            for key, spec in config["frozen_inputs"].items()
        },
        "config_sha256": sha256_file(config_path),
    }
    audit["content_sha256"] = canonical_sha256(audit)
    output.mkdir(parents=True)
    write_json(output / "profile_domain_guard_audit.json", audit)
    write_jsonl(output / "external_guarded_scored.jsonl", guarded_external)
    write_jsonl(output / "in_scope_guarded_scored.jsonl", guarded_in)
    print(json.dumps({"status": audit["status"], "checks": checks, "external": audit["external"], "audit_sha256": sha256_file(output / "profile_domain_guard_audit.json")}, indent=2))


if __name__ == "__main__":
    main()

