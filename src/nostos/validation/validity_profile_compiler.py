"""Compile and audit reusable NOSTOS measurement-validity profiles.

The compiler consumes endpoint-level paired-acquisition rows. Reference images
are represented only by eligibility and error labels; every score used at
deployment must be derived from the acquisition image alone. Development and
confirmation are deliberately separate file operations so a serialized profile
can be frozen before confirmation evidence is opened.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from nostos.validation.family_risk_calibration import (
    IsotonicRiskMap,
    brier_score,
    expected_calibration_error,
    fit_isotonic_risk_map,
    logarithmic_loss,
    risk_coverage_auc,
)


PROFILE_SCHEMA_VERSION = "nostos-validity-profile/1.0"
COMPILER_VERSION = "nostos-validity-profile-compiler/1.0"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_number} is not an object.")
            rows.append(value)
    if not rows:
        raise ValueError("The evidence JSONL contains no rows.")
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def _row_is_eligible(row: Mapping[str, Any]) -> bool:
    return bool(row["pair_registration_eligible"]) and bool(row["reference_eligible"])


def _identifiability_reason(reason: str) -> bool:
    return any(
        token in reason
        for token in (
            "orientation_resultant",
            "spectral_orientation_anisotropy",
            "orientation_estimators_disagree",
            "scale_peak_at_search_boundary",
        )
    )


def candidate_hard_abstention(row: Mapping[str, Any], score_key: str) -> bool:
    """Apply only the hard gates available to a score candidate.

    This prevents an acquisition-QC comparator from receiving the benefit of
    NOSTOS identifiability or sampling gates during evaluation.
    """

    reasons = {str(value) for value in row.get("hard_abstention_reasons", [])}
    if score_key == "always_emit":
        return False
    if score_key == "conventional_acquisition_qc":
        return "acquisition_qc_abstain" in reasons
    if score_key == "physical_sampling_only":
        return "fewer_than_four_effective_samples_per_requested_scale" in reasons
    if score_key == "perturbation_stability_only":
        return False
    if "without_qc" in score_key:
        reasons.discard("acquisition_qc_abstain")
    if "without_sampling" in score_key:
        reasons.discard("fewer_than_four_effective_samples_per_requested_scale")
    if "without_identifiability" in score_key:
        reasons = {reason for reason in reasons if not _identifiability_reason(reason)}
    return bool(reasons)


def validate_contract_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_keys: Sequence[str],
) -> None:
    if not rows:
        raise ValueError("At least one contract row is required.")
    required = {
        "case_id",
        "reference_group_id",
        "endpoint_family",
        "pair_registration_eligible",
        "reference_eligible",
        "invalid",
        "scores",
    }
    observed_ids: set[str] = set()
    for index, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            raise ValueError(f"Contract row {index} is missing {sorted(missing)}.")
        case_id = str(row["case_id"])
        if case_id in observed_ids:
            raise ValueError(f"Duplicate case_id: {case_id}")
        observed_ids.add(case_id)
        if not str(row["reference_group_id"]).strip():
            raise ValueError(f"Contract row {case_id} has an empty group identifier.")
        if not str(row["endpoint_family"]).strip():
            raise ValueError(f"Contract row {case_id} has an empty endpoint family.")
        scores = row["scores"]
        if not isinstance(scores, Mapping):
            raise ValueError(f"Contract row {case_id} has no score mapping.")
        for score_key in score_keys:
            if score_key not in scores:
                raise ValueError(f"Contract row {case_id} lacks score {score_key!r}.")
            value = float(scores[score_key])
            if not math.isfinite(value):
                raise ValueError(f"Contract row {case_id} has a non-finite score.")


def _group_stratum(row: Mapping[str, Any]) -> str:
    if "group_stratum" in row:
        return str(row["group_stratum"])
    metadata = row.get("metadata", {})
    if isinstance(metadata, Mapping) and "acquisition_modality" in metadata:
        return str(metadata["acquisition_modality"])
    return "all"


def _declared_acquisition_stratum(
    row: Mapping[str, Any], specification: Mapping[str, Any]
) -> str:
    metadata = row.get("metadata", {})
    key = str(specification["metadata_key"])
    if not isinstance(metadata, Mapping) or key not in metadata:
        raise ValueError(f"Contract row lacks required acquisition-stratum metadata {key!r}.")
    value = str(metadata[key]).strip()
    if not value:
        raise ValueError(f"Contract row has an empty acquisition stratum for {key!r}.")
    return value


def acquisition_stratum_support(
    rows: Sequence[Mapping[str, Any]],
    specification: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if specification is None:
        return None
    minimum = int(specification["minimum_independent_development_groups"])
    if minimum < 2:
        raise ValueError("Acquisition-stratum support requires at least two development groups.")
    groups: dict[str, set[str]] = defaultdict(set)
    group_to_stratum: dict[str, str] = {}
    for row in rows:
        stratum = _declared_acquisition_stratum(row, specification)
        group = str(row["reference_group_id"])
        previous = group_to_stratum.setdefault(group, stratum)
        if previous != stratum:
            raise ValueError(f"Independent group {group!r} spans acquisition strata.")
        groups[stratum].add(group)
    counts = {stratum: len(values) for stratum, values in sorted(groups.items())}
    supported = sorted(stratum for stratum, count in counts.items() if count >= minimum)
    unsupported = sorted(stratum for stratum, count in counts.items() if count < minimum)
    return {
        "metadata_key": str(specification["metadata_key"]),
        "minimum_independent_development_groups": minimum,
        "independent_groups_by_stratum": counts,
        "supported_strata": supported,
        "unsupported_strata": unsupported,
        "unsupported_action": "hard_abstention",
    }


def assign_group_folds(
    rows: Sequence[Mapping[str, Any]],
    *,
    folds: int,
    seed: int,
) -> dict[str, int]:
    """Assign complete independent groups to deterministic stratified folds."""

    if folds < 2:
        raise ValueError("At least two cross-fitting folds are required.")
    group_strata: dict[str, str] = {}
    for row in rows:
        group = str(row["reference_group_id"])
        stratum = _group_stratum(row)
        previous = group_strata.setdefault(group, stratum)
        if previous != stratum:
            raise ValueError(f"Group {group!r} appears in multiple strata.")
    if len(group_strata) < folds:
        raise ValueError("The number of independent groups is smaller than the fold count.")
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for group, stratum in group_strata.items():
        by_stratum[stratum].append(group)
    assignments: dict[str, int] = {}
    global_offset = 0
    for stratum, groups in sorted(by_stratum.items()):
        ordered = sorted(
            groups,
            key=lambda group: hashlib.sha256(
                f"{seed}|{stratum}|{group}".encode("utf-8")
            ).hexdigest(),
        )
        for index, group in enumerate(ordered):
            assignments[group] = (global_offset + index) % folds
        global_offset = (global_offset + len(ordered)) % folds
    if set(assignments.values()) != set(range(folds)):
        raise ValueError("Deterministic fold assignment left at least one fold empty.")
    return assignments


def _risk_map_from_dict(payload: Mapping[str, Any]) -> IsotonicRiskMap:
    return IsotonicRiskMap(
        x_thresholds=tuple(float(value) for value in payload["x_thresholds"]),
        y_thresholds=tuple(float(value) for value in payload["y_thresholds"]),
        training_cases=int(payload["training_cases"]),
        training_invalid=int(payload["training_invalid"]),
        bins=int(payload["bins"]),
        prior_alpha=float(payload["prior_alpha"]),
        prior_beta=float(payload["prior_beta"]),
    )


def cross_fit_score(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_key: str,
    folds: int,
    seed: int,
    bins: int,
    prior_alpha: float,
    prior_beta: float,
) -> tuple[list[dict[str, Any]], dict[str, IsotonicRiskMap]]:
    eligible = [row for row in rows if _row_is_eligible(row)]
    families = sorted({str(row["endpoint_family"]) for row in eligible})
    scored: list[dict[str, Any]] = []
    final_maps: dict[str, IsotonicRiskMap] = {}
    for family in families:
        family_rows = [row for row in eligible if str(row["endpoint_family"]) == family]
        family_group_count = len(
            {str(row["reference_group_id"]) for row in family_rows}
        )
        family_folds = min(folds, family_group_count)
        if family_folds < 2:
            raise ValueError(
                f"Endpoint family {family!r} has fewer than two independent groups."
            )
        assignments = assign_group_folds(
            family_rows,
            folds=family_folds,
            seed=seed,
        )
        for fold in range(family_folds):
            training = [
                row
                for row in family_rows
                if assignments[str(row["reference_group_id"])] != fold
                and not candidate_hard_abstention(row, score_key)
            ]
            held_out = [
                row
                for row in family_rows
                if assignments[str(row["reference_group_id"])] == fold
            ]
            if not training or not held_out:
                raise ValueError(
                    f"Endpoint family {family!r}, fold {fold} lacks training or held-out rows."
                )
            risk_map = fit_isotonic_risk_map(
                [float(row["scores"][score_key]) for row in training],
                [bool(row["invalid"]) for row in training],
                bins=bins,
                prior_alpha=prior_alpha,
                prior_beta=prior_beta,
            )
            for row in held_out:
                hard = candidate_hard_abstention(row, score_key)
                risk = (
                    1.0
                    if hard
                    else float(risk_map.predict([float(row["scores"][score_key])])[0])
                )
                clone = deepcopy(dict(row))
                clone["calibration_fold"] = fold
                clone["calibration_fold_count"] = family_folds
                clone["candidate_hard_abstention"] = hard
                clone["calibrated_risk"] = risk
                scored.append(clone)
        training = [
            row for row in family_rows if not candidate_hard_abstention(row, score_key)
        ]
        if not training:
            raise ValueError(f"Endpoint family {family!r} has no non-abstained training rows.")
        final_maps[family] = fit_isotonic_risk_map(
            [float(row["scores"][score_key]) for row in training],
            [bool(row["invalid"]) for row in training],
            bins=bins,
            prior_alpha=prior_alpha,
            prior_beta=prior_beta,
        )
    scored.sort(key=lambda row: str(row["case_id"]))
    return scored, final_maps


def apply_score_profile(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_key: str,
    risk_maps: Mapping[str, Mapping[str, Any]],
    stratum_support: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    maps = {family: _risk_map_from_dict(payload) for family, payload in risk_maps.items()}
    for source in rows:
        row = deepcopy(dict(source))
        family = str(row["endpoint_family"])
        unsupported_stratum = False
        if stratum_support is not None:
            stratum = _declared_acquisition_stratum(row, stratum_support)
            unsupported_stratum = stratum not in set(stratum_support["supported_strata"])
        if unsupported_stratum:
            row["candidate_hard_abstention"] = True
            row["profile_hard_abstention_reason"] = (
                "acquisition_stratum_underrepresented_in_development"
            )
            row["calibrated_risk"] = 1.0
            output.append(row)
            continue
        if family not in maps:
            raise ValueError(f"Profile has no calibration map for endpoint family {family!r}.")
        hard = candidate_hard_abstention(row, score_key)
        row["candidate_hard_abstention"] = hard
        row["calibrated_risk"] = (
            1.0
            if hard
            else float(maps[family].predict([float(row["scores"][score_key])])[0])
        )
        row["profile_hard_abstention_reason"] = None
        output.append(row)
    output.sort(key=lambda row: str(row["case_id"]))
    return output


def _cluster_bootstrap_risk_upper(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    draws: int,
    seed: int,
) -> float | None:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["reference_group_id"])].append(row)
    identifiers = sorted(groups)
    if not identifiers:
        return None
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sampled = rng.choice(identifiers, size=len(identifiers), replace=True)
        values: list[bool] = []
        for identifier in sampled:
            for row in groups[str(identifier)]:
                if (
                    not bool(row["candidate_hard_abstention"])
                    and float(row["calibrated_risk"]) <= threshold
                ):
                    values.append(bool(row["invalid"]))
        if values:
            estimates.append(float(np.mean(values)))
    return float(np.quantile(estimates, 0.95)) if estimates else None


def _operating_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    accepted = [
        row
        for row in rows
        if not bool(row["candidate_hard_abstention"])
        and float(row["calibrated_risk"]) <= threshold
    ]
    invalid = int(sum(bool(row["invalid"]) for row in accepted))
    return {
        "predicted_risk_threshold": float(threshold),
        "eligible": len(rows),
        "accepted": len(accepted),
        "coverage": float(len(accepted) / len(rows)) if rows else 0.0,
        "invalid": invalid,
        "risk": float(invalid / len(accepted)) if accepted else None,
        "accepted_independent_groups": len(
            {str(row["reference_group_id"]) for row in accepted}
        ),
        "cluster_bootstrap_risk_upper95": _cluster_bootstrap_risk_upper(
            rows,
            threshold=threshold,
            draws=draws,
            seed=seed,
        ),
    }


def select_operating_point(
    rows: Sequence[Mapping[str, Any]],
    *,
    target_risk: float,
    maximum_risk_upper95: float,
    minimum_coverage: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    candidates = sorted(
        {
            float(row["calibrated_risk"])
            for row in rows
            if not bool(row["candidate_hard_abstention"])
        }
    )
    evaluated: list[dict[str, Any]] = []
    passing: list[dict[str, Any]] = []
    for index, threshold in enumerate(candidates):
        summary = _operating_summary(
            rows,
            threshold=threshold,
            draws=draws,
            seed=seed + index,
        )
        checks = {
            "minimum_coverage": summary["coverage"] >= minimum_coverage,
            "target_observed_risk": (
                summary["risk"] is not None and summary["risk"] <= target_risk
            ),
            "maximum_cluster_bootstrap_risk_upper95": (
                summary["cluster_bootstrap_risk_upper95"] is not None
                and summary["cluster_bootstrap_risk_upper95"] <= maximum_risk_upper95
            ),
        }
        candidate = {**summary, "checks": checks, "passes": bool(all(checks.values()))}
        evaluated.append(candidate)
        if candidate["passes"]:
            passing.append(candidate)
    selected = (
        max(passing, key=lambda item: (float(item["coverage"]), float(item["predicted_risk_threshold"])))
        if passing
        else None
    )
    return {
        "status": "operating_point_selected" if selected else "no_operating_point",
        "selection_rule": (
            "Highest cross-fitted coverage satisfying every predeclared development gate."
        ),
        "candidate_count": len(candidates),
        "target_observed_risk": float(target_risk),
        "maximum_cluster_bootstrap_risk_upper95": float(maximum_risk_upper95),
        "minimum_coverage": float(minimum_coverage),
        "selected": selected,
        "candidates": evaluated,
    }


def _prediction_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    return {
        "risk_coverage_auc": risk_coverage_auc(rows, score_key="calibrated_risk"),
        "brier_score": brier_score(rows, score_key="calibrated_risk"),
        "logarithmic_loss": logarithmic_loss(rows, score_key="calibrated_risk"),
        "expected_calibration_error": expected_calibration_error(
            rows, score_key="calibrated_risk"
        ),
    }


def compile_validity_profile(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    compiler = config["compiler"]
    score_candidates = [str(value) for value in compiler["score_candidates"]]
    primary_score = str(compiler["primary_score"])
    if primary_score not in score_candidates:
        raise ValueError("The primary score is absent from score_candidates.")
    validate_contract_rows(rows, score_keys=score_candidates)
    eligible = [row for row in rows if _row_is_eligible(row)]
    if not eligible:
        raise ValueError("No reference-eligible paired cases are available for compilation.")
    groups = sorted({str(row["reference_group_id"]) for row in eligible})
    stratum_specification = compiler.get("acquisition_stratum_support")
    stratum_support = acquisition_stratum_support(eligible, stratum_specification)
    calibration_rows = eligible
    unsupported_case_ids: set[str] = set()
    if stratum_support is not None:
        supported = set(stratum_support["supported_strata"])
        calibration_rows = [
            row
            for row in eligible
            if _declared_acquisition_stratum(row, stratum_support) in supported
        ]
        unsupported_case_ids = {
            str(row["case_id"])
            for row in eligible
            if _declared_acquisition_stratum(row, stratum_support) not in supported
        }
        if not calibration_rows:
            raise ValueError("No acquisition stratum has enough independent development groups.")
    candidates: dict[str, dict[str, Any]] = {}
    combined_rows = {str(row["case_id"]): deepcopy(dict(row)) for row in eligible}
    for score_key in score_candidates:
        scored, final_maps = cross_fit_score(
            calibration_rows,
            score_key=score_key,
            folds=int(compiler["folds"]),
            seed=int(compiler["fold_seed"]),
            bins=int(compiler["calibration_bins"]),
            prior_alpha=float(compiler["prior_alpha"]),
            prior_beta=float(compiler["prior_beta"]),
        )
        scored_with_unsupported = list(scored)
        for row in eligible:
            if str(row["case_id"]) not in unsupported_case_ids:
                continue
            clone = deepcopy(dict(row))
            clone["calibration_fold"] = None
            clone["calibration_fold_count"] = 0
            clone["candidate_hard_abstention"] = True
            clone["profile_hard_abstention_reason"] = (
                "acquisition_stratum_underrepresented_in_development"
            )
            clone["calibrated_risk"] = 1.0
            scored_with_unsupported.append(clone)
        scored_with_unsupported.sort(key=lambda row: str(row["case_id"]))
        candidates[score_key] = {
            "cross_fitted_metrics": _prediction_metrics(scored_with_unsupported),
            "risk_maps": {
                family: risk_map.to_dict() for family, risk_map in sorted(final_maps.items())
            },
        }
        for row in scored_with_unsupported:
            target = combined_rows[str(row["case_id"])]
            target.setdefault("cross_fitted_calibrated_risk", {})[score_key] = float(
                row["calibrated_risk"]
            )
            target.setdefault("candidate_hard_abstention", {})[score_key] = bool(
                row["candidate_hard_abstention"]
            )
            target.setdefault("calibration_fold", {})[score_key] = int(
                row["calibration_fold"]
            ) if row["calibration_fold"] is not None else None
            if row.get("profile_hard_abstention_reason"):
                target["profile_hard_abstention_reason"] = row[
                    "profile_hard_abstention_reason"
                ]
    primary_family = str(config["measurement"]["primary_endpoint_family"])
    primary_rows = []
    for row in combined_rows.values():
        if str(row["endpoint_family"]) != primary_family:
            continue
        clone = deepcopy(row)
        clone["calibrated_risk"] = float(
            row["cross_fitted_calibrated_risk"][primary_score]
        )
        clone["candidate_hard_abstention"] = bool(
            row["candidate_hard_abstention"][primary_score]
        )
        primary_rows.append(clone)
    operating = compiler["operating_point"]
    operating_point = select_operating_point(
        primary_rows,
        target_risk=float(operating["target_observed_risk"]),
        maximum_risk_upper95=float(operating["maximum_cluster_bootstrap_risk_upper95"]),
        minimum_coverage=float(operating["minimum_coverage"]),
        draws=int(operating["bootstrap_replicates"]),
        seed=int(operating["bootstrap_seed"]),
    )
    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "compiler_version": COMPILER_VERSION,
        "protocol_id": str(config["protocol_id"]),
        "status": operating_point["status"],
        "claim_boundary": dict(config["scope"]),
        "measurement": dict(config["measurement"]),
        "primary_score": primary_score,
        "score_candidates": score_candidates,
        "primary_endpoint_family": primary_family,
        "development": {
            "independent_groups": groups,
            "independent_group_count": len(groups),
            "group_set_sha256": canonical_sha256(groups),
            "eligible_cases": len(eligible),
            "calibration_cases": len(calibration_rows),
            "calibration_independent_group_count": len(
                {str(row["reference_group_id"]) for row in calibration_rows}
            ),
            "source_receipt": dict(source_receipt or {}),
        },
        "acquisition_stratum_support": stratum_support,
        "calibration": {
            "folds": int(compiler["folds"]),
            "fold_seed": int(compiler["fold_seed"]),
            "bins": int(compiler["calibration_bins"]),
            "prior_alpha": float(compiler["prior_alpha"]),
            "prior_beta": float(compiler["prior_beta"]),
            "candidates": candidates,
        },
        "operating_point": operating_point,
        "confirmation_gates": dict(config["confirmation_gates"]),
        "config_sha256": canonical_sha256(config),
    }
    profile["content_sha256"] = canonical_sha256(profile)
    scored_rows = sorted(combined_rows.values(), key=lambda row: str(row["case_id"]))
    audit = {
        "schema_version": "nostos-validity-profile-development-audit/1.0",
        "status": profile["status"],
        "profile_content_sha256": profile["content_sha256"],
        "independent_groups": len(groups),
        "eligible_cases": len(eligible),
        "primary_endpoint_family": primary_family,
        "primary_score": primary_score,
        "operating_point": operating_point,
        "candidate_metrics": {
            key: value["cross_fitted_metrics"] for key, value in candidates.items()
        },
    }
    audit["content_sha256"] = canonical_sha256(audit)
    return profile, audit, scored_rows


def verify_profile(profile: Mapping[str, Any]) -> None:
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError("Unsupported validity-profile schema.")
    expected = str(profile.get("content_sha256", ""))
    payload = dict(profile)
    payload.pop("content_sha256", None)
    observed = canonical_sha256(payload)
    if not expected or observed != expected:
        raise ValueError("Validity-profile content hash mismatch.")
    if profile.get("status") != "operating_point_selected":
        raise ValueError("Validity profile has no deployable operating point.")


def _apply_all_candidates(
    rows: Sequence[Mapping[str, Any]], profile: Mapping[str, Any]
) -> list[dict[str, Any]]:
    combined = {str(row["case_id"]): deepcopy(dict(row)) for row in rows}
    candidates = profile["calibration"]["candidates"]
    for score_key in profile["score_candidates"]:
        scored = apply_score_profile(
            rows,
            score_key=str(score_key),
            risk_maps=candidates[str(score_key)]["risk_maps"],
            stratum_support=profile.get("acquisition_stratum_support"),
        )
        for row in scored:
            target = combined[str(row["case_id"])]
            target.setdefault("calibrated_risk", {})[str(score_key)] = float(
                row["calibrated_risk"]
            )
            target.setdefault("candidate_hard_abstention", {})[str(score_key)] = bool(
                row["candidate_hard_abstention"]
            )
    return sorted(combined.values(), key=lambda row: str(row["case_id"]))


def _rows_for_candidate(
    rows: Sequence[Mapping[str, Any]], score_key: str
) -> list[dict[str, Any]]:
    output = []
    for source in rows:
        row = deepcopy(dict(source))
        row["calibrated_risk"] = float(source["calibrated_risk"][score_key])
        row["candidate_hard_abstention"] = bool(
            source["candidate_hard_abstention"][score_key]
        )
        output.append(row)
    return output


def _matched_count_summary(
    rows: Sequence[Mapping[str, Any]], *, accepted_count: int
) -> dict[str, Any]:
    available = [row for row in rows if not bool(row["candidate_hard_abstention"])]
    ordered = sorted(
        available,
        key=lambda row: (float(row["calibrated_risk"]), str(row["case_id"])),
    )
    accepted = ordered[: min(accepted_count, len(ordered))]
    invalid = int(sum(bool(row["invalid"]) for row in accepted))
    boundary_tie_split = bool(
        accepted
        and len(accepted) < len(ordered)
        and float(accepted[-1]["calibrated_risk"])
        == float(ordered[len(accepted)]["calibrated_risk"])
    )
    tie_robust_bounds = None
    if accepted:
        boundary = float(accepted[-1]["calibrated_risk"])
        below = [row for row in available if float(row["calibrated_risk"]) < boundary]
        tied = [row for row in available if float(row["calibrated_risk"]) == boundary]
        needed = len(accepted) - len(below)
        invalid_below = int(sum(bool(row["invalid"]) for row in below))
        invalid_tied = int(sum(bool(row["invalid"]) for row in tied))
        valid_tied = len(tied) - invalid_tied
        best_invalid = invalid_below + max(0, needed - valid_tied)
        worst_invalid = invalid_below + min(needed, invalid_tied)
        tie_robust_bounds = {
            "boundary_calibrated_risk": boundary,
            "strictly_below_boundary": len(below),
            "boundary_tie_cases": len(tied),
            "boundary_tie_invalid": invalid_tied,
            "cases_required_from_boundary_tie": needed,
            "best_case_invalid": int(best_invalid),
            "worst_case_invalid": int(worst_invalid),
            "best_case_risk": float(best_invalid / len(accepted)),
            "worst_case_risk": float(worst_invalid / len(accepted)),
        }
    return {
        "target_accepted": int(accepted_count),
        "accepted": len(accepted),
        "eligible": len(rows),
        "coverage": float(len(accepted) / len(rows)) if rows else 0.0,
        "invalid": invalid,
        "risk": float(invalid / len(accepted)) if accepted else None,
        "deterministic_tie_break": "case_id",
        "boundary_tie_split": boundary_tie_split,
        "tie_robust_risk_bounds": tie_robust_bounds,
    }


def _descriptive_operating_summary(
    rows: Sequence[Mapping[str, Any]], *, threshold: float
) -> dict[str, Any]:
    accepted = [
        row
        for row in rows
        if not bool(row["candidate_hard_abstention"])
        and float(row["calibrated_risk"]) <= threshold
    ]
    invalid = int(sum(bool(row["invalid"]) for row in accepted))
    return {
        "eligible": len(rows),
        "accepted": len(accepted),
        "coverage": float(len(accepted) / len(rows)) if rows else 0.0,
        "invalid": invalid,
        "risk": float(invalid / len(accepted)) if accepted else None,
    }


def _stratified_operating_summaries(
    rows: Sequence[Mapping[str, Any]], *, threshold: float
) -> dict[str, list[dict[str, Any]]]:
    definitions = {
        "acquisition_modality": lambda row: str(
            row.get("metadata", {}).get("acquisition_modality", "not_declared")
        ),
        "independent_group": lambda row: str(row["reference_group_id"]),
        "acquisition_level": lambda row: str(
            row.get("metadata", {}).get("acquisition_level", "not_declared")
        ),
        "requested_scale": lambda row: str(
            row.get("requested_scale_value", "not_declared")
        ),
    }
    output: dict[str, list[dict[str, Any]]] = {}
    for name, extractor in definitions.items():
        values = sorted({extractor(row) for row in rows})
        output[name] = [
            {
                "stratum": value,
                **_descriptive_operating_summary(
                    [row for row in rows if extractor(row) == value],
                    threshold=threshold,
                ),
            }
            for value in values
        ]
    return output


def _cluster_bootstrap_aurc_difference(
    primary: Sequence[Mapping[str, Any]],
    comparator: Sequence[Mapping[str, Any]],
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    comparator_by_id = {str(row["case_id"]): row for row in comparator}
    groups: dict[str, list[str]] = defaultdict(list)
    for row in primary:
        case_id = str(row["case_id"])
        if case_id not in comparator_by_id:
            raise ValueError("Primary and comparator confirmation cases are misaligned.")
        groups[str(row["reference_group_id"])].append(case_id)
    identifiers = sorted(groups)
    observed = risk_coverage_auc(comparator, score_key="calibrated_risk") - risk_coverage_auc(
        primary, score_key="calibrated_risk"
    )
    rng = np.random.default_rng(seed)
    samples: list[float] = []
    primary_by_id = {str(row["case_id"]): row for row in primary}
    for _ in range(draws):
        sampled = rng.choice(identifiers, size=len(identifiers), replace=True)
        p_rows: list[Mapping[str, Any]] = []
        c_rows: list[Mapping[str, Any]] = []
        for replicate_index, group in enumerate(sampled):
            for case_id in groups[str(group)]:
                p = dict(primary_by_id[case_id])
                c = dict(comparator_by_id[case_id])
                p["case_id"] = f"{replicate_index}|{case_id}"
                c["case_id"] = f"{replicate_index}|{case_id}"
                p_rows.append(p)
                c_rows.append(c)
        samples.append(
            risk_coverage_auc(c_rows, score_key="calibrated_risk")
            - risk_coverage_auc(p_rows, score_key="calibrated_risk")
        )
    lower, upper = np.quantile(np.asarray(samples), [0.025, 0.975])
    return {
        "definition": "acquisition_qc_AURC_minus_full_contract_AURC; positive favors NOSTOS",
        "observed": float(observed),
        "bootstrap_ci95": [float(lower), float(upper)],
        "bootstrap_probability_positive": float(np.mean(np.asarray(samples) > 0.0)),
        "independent_groups": len(identifiers),
        "draws": int(draws),
        "seed": int(seed),
    }


def audit_validity_profile(
    rows: Sequence[Mapping[str, Any]],
    *,
    profile: Mapping[str, Any],
    source_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verify_profile(profile)
    score_candidates = [str(value) for value in profile["score_candidates"]]
    validate_contract_rows(rows, score_keys=score_candidates)
    eligible = [row for row in rows if _row_is_eligible(row)]
    if not eligible:
        raise ValueError("No reference-eligible confirmation cases are available.")
    development_groups = set(profile["development"]["independent_groups"])
    confirmation_groups = {str(row["reference_group_id"]) for row in eligible}
    overlap = sorted(development_groups & confirmation_groups)
    if overlap:
        raise ValueError(f"Development-confirmation group leakage detected: {overlap}")
    scored = _apply_all_candidates(eligible, profile)
    primary_family = str(profile["primary_endpoint_family"])
    family_rows = [row for row in scored if str(row["endpoint_family"]) == primary_family]
    primary_score = str(profile["primary_score"])
    primary = _rows_for_candidate(family_rows, primary_score)
    comparator = _rows_for_candidate(family_rows, "conventional_acquisition_qc")
    gates = profile["confirmation_gates"]
    threshold = float(profile["operating_point"]["selected"]["predicted_risk_threshold"])
    primary_summary = _operating_summary(
        primary,
        threshold=threshold,
        draws=int(gates["bootstrap_replicates"]),
        seed=int(gates["bootstrap_seed"]),
    )
    comparator_matched = _matched_count_summary(
        comparator, accepted_count=int(primary_summary["accepted"])
    )
    deterministic_relative_reduction = None
    if (
        primary_summary["risk"] is not None
        and comparator_matched["risk"] is not None
        and float(comparator_matched["risk"]) > 0.0
    ):
        deterministic_relative_reduction = 1.0 - float(primary_summary["risk"]) / float(
            comparator_matched["risk"]
        )
    tie_bounds = comparator_matched["tie_robust_risk_bounds"]
    conservative_relative_reduction = None
    optimistic_relative_reduction = None
    if primary_summary["risk"] is not None and tie_bounds is not None:
        best_comparator_risk = float(tie_bounds["best_case_risk"])
        worst_comparator_risk = float(tie_bounds["worst_case_risk"])
        if best_comparator_risk > 0.0:
            conservative_relative_reduction = 1.0 - float(
                primary_summary["risk"]
            ) / best_comparator_risk
        if worst_comparator_risk > 0.0:
            optimistic_relative_reduction = 1.0 - float(
                primary_summary["risk"]
            ) / worst_comparator_risk
    candidate_metrics = {
        score_key: _prediction_metrics(_rows_for_candidate(family_rows, score_key))
        for score_key in score_candidates
    }
    aurc_difference = _cluster_bootstrap_aurc_difference(
        primary,
        comparator,
        draws=int(gates["bootstrap_replicates"]),
        seed=int(gates["bootstrap_seed"]) + 1,
    )
    checks = {
        "minimum_independent_groups": len(confirmation_groups)
        >= int(gates["minimum_independent_groups"]),
        "minimum_coverage": primary_summary["coverage"] >= float(gates["minimum_coverage"]),
        "maximum_observed_risk": (
            primary_summary["risk"] is not None
            and primary_summary["risk"] <= float(gates["maximum_observed_risk"])
        ),
        "maximum_cluster_bootstrap_risk_upper95": (
            primary_summary["cluster_bootstrap_risk_upper95"] is not None
            and primary_summary["cluster_bootstrap_risk_upper95"]
            <= float(gates["maximum_cluster_bootstrap_risk_upper95"])
        ),
        "minimum_relative_risk_reduction_vs_acquisition_qc": (
            conservative_relative_reduction is not None
            and conservative_relative_reduction
            >= float(gates["minimum_relative_risk_reduction_vs_acquisition_qc"])
        ),
        "minimum_invalid_acquisition_qc_emissions": comparator_matched["invalid"]
        >= int(gates["minimum_invalid_acquisition_qc_emissions"]),
        "positive_aurc_difference": (
            not bool(gates["require_positive_aurc_difference"])
            or aurc_difference["observed"] > 0.0
        ),
        "aurc_bootstrap_ci_lower_above_zero": (
            not bool(gates["require_aurc_bootstrap_ci_lower_above_zero"])
            or aurc_difference["bootstrap_ci95"][0] > 0.0
        ),
    }
    if not checks["minimum_independent_groups"]:
        status = "not_assessable_insufficient_independent_groups"
    elif not checks["minimum_invalid_acquisition_qc_emissions"]:
        status = "not_assessable_insufficient_comparator_failures"
    else:
        status = "pass" if all(checks.values()) else "fail"
    stratified = _stratified_operating_summaries(primary, threshold=threshold)
    modality_risks = [
        float(item["risk"])
        for item in stratified["acquisition_modality"]
        if item["risk"] is not None
    ]
    modality_heterogeneity = bool(
        modality_risks
        and max(modality_risks) > float(gates["maximum_observed_risk"])
    )
    audit: dict[str, Any] = {
        "schema_version": "nostos-validity-profile-confirmation-audit/1.1",
        "status": status,
        "profile_content_sha256": profile["content_sha256"],
        "claim_boundary": profile["claim_boundary"],
        "primary_endpoint_family": primary_family,
        "primary_score": primary_score,
        "confirmation": {
            "source_receipt": dict(source_receipt or {}),
            "independent_groups": sorted(confirmation_groups),
            "independent_group_count": len(confirmation_groups),
            "eligible_cases": len(eligible),
            "development_group_overlap": overlap,
        },
        "primary_operating_point": primary_summary,
        "acquisition_qc_matched_count": comparator_matched,
        "relative_risk_reduction_vs_acquisition_qc": {
            "deterministic_tie_break_estimate": deterministic_relative_reduction,
            "conservative_lower_bound_over_boundary_tie": conservative_relative_reduction,
            "optimistic_upper_bound_over_boundary_tie": optimistic_relative_reduction,
        },
        "risk_coverage": {
            "candidate_metrics": candidate_metrics,
            "cluster_bootstrap_aurc_difference": aurc_difference,
        },
        "stratified_safety_audit": {
            "status": (
                "aggregate_pass_with_acquisition_stratum_heterogeneity"
                if status == "pass" and modality_heterogeneity
                else "no_acquisition_stratum_heterogeneity_detected"
            ),
            "post_confirmation_descriptive_not_a_frozen_primary_gate": True,
            "maximum_observed_risk_gate": float(gates["maximum_observed_risk"]),
            "acquisition_modality_heterogeneity": modality_heterogeneity,
            "summaries": stratified,
        },
        "checks": checks,
    }
    audit["content_sha256"] = canonical_sha256(audit)
    return audit, scored


def compile_profile_files(
    development_rows_path: Path,
    config_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rows = read_jsonl(development_rows_path)
    source_receipt = {
        "name": development_rows_path.name,
        "bytes": development_rows_path.stat().st_size,
        "sha256": sha256_file(development_rows_path),
        "config_name": config_path.name,
        "config_bytes": config_path.stat().st_size,
        "config_file_sha256": sha256_file(config_path),
    }
    profile, audit, scored = compile_validity_profile(
        rows, config=config, source_receipt=source_receipt
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    profile_path = output_directory / "validity_profile.json"
    audit_path = output_directory / "development_audit.json"
    scored_path = output_directory / "development_scored.jsonl"
    write_json(profile_path, profile)
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    return {
        "status": profile["status"],
        "profile": str(profile_path),
        "profile_file_sha256": sha256_file(profile_path),
        "development_audit": str(audit_path),
        "development_scored": str(scored_path),
        "independent_groups": profile["development"]["independent_group_count"],
        "eligible_cases": profile["development"]["eligible_cases"],
    }


def audit_profile_files(
    confirmation_rows_path: Path,
    profile_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    rows = read_jsonl(confirmation_rows_path)
    source_receipt = {
        "name": confirmation_rows_path.name,
        "bytes": confirmation_rows_path.stat().st_size,
        "sha256": sha256_file(confirmation_rows_path),
        "profile_name": profile_path.name,
        "profile_bytes": profile_path.stat().st_size,
        "profile_file_sha256": sha256_file(profile_path),
    }
    audit, scored = audit_validity_profile(
        rows, profile=profile, source_receipt=source_receipt
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    audit_path = output_directory / "confirmation_audit.json"
    scored_path = output_directory / "confirmation_scored.jsonl"
    write_json(audit_path, audit)
    write_jsonl(scored_path, scored)
    return {
        "status": audit["status"],
        "confirmation_audit": str(audit_path),
        "confirmation_scored": str(scored_path),
        "independent_groups": audit["confirmation"]["independent_group_count"],
        "eligible_cases": audit["confirmation"]["eligible_cases"],
        "checks": audit["checks"],
    }
