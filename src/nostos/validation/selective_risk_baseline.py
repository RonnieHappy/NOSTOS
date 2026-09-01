"""Retrospective learned-comparator audit for NOSTOS selective validity.

The audit consumes already frozen development and confirmation evidence rows.
It never decodes source microscopy and never changes a historical threshold or
decision.  Its sole purpose is to compare input-only score rankings against two
fixed learned invalidity predictors on the same untouched confirmation rows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


PROTOCOL_VERSION = "nostos-selective-risk-baseline-audit/1.0"
SEED = 260831


@dataclass(frozen=True)
class DomainSpec:
    name: str
    development: str
    confirmation: str
    nostos_score: str
    acquisition_score: str
    endpoint_score: str | None
    feature_source: str
    bootstrap_group_field: str
    historical_accepted: int
    endpoint_filter: str | None = None
    excluded_features: tuple[str, ...] = ()
    caution: str | None = None


DOMAIN_SPECS: tuple[DomainSpec, ...] = (
    DomainSpec(
        name="biosr_f_actin",
        development="outputs/nostos0-biosr-tensor-v9-scale-conditioned-development/development_tensor_cases_v9.jsonl",
        confirmation="outputs/nostos0-biosr-tensor-v9-scale-conditioned-confirmation/tensor_cases.jsonl",
        nostos_score="full_contract",
        acquisition_score="conventional_acquisition_qc",
        endpoint_score=None,
        feature_source="support_components",
        bootstrap_group_field="reference_group_id",
        historical_accepted=931,
        endpoint_filter="tensor_coherence",
        excluded_features=("scale_conditioned_acquisition_support",),
    ),
    DomainSpec(
        name="fmd_widefield",
        development="outputs/nostos0-fmd-widefield-v1-3-development/development_rows.jsonl",
        confirmation="outputs/nostos0-fmd-widefield-v1-3-confirmation/confirmation_rows.jsonl",
        nostos_score="declared_capture_stability_contract",
        acquisition_score="conventional_acquisition_qc",
        endpoint_score=None,
        feature_source="support_components",
        bootstrap_group_field="reference_group_id",
        historical_accepted=68,
        endpoint_filter="tensor_coherence",
    ),
    DomainSpec(
        name="pshg_tiss_breast",
        development="outputs/nostos0-pshg-acquisition-shift-v1-development/development_rows.jsonl",
        confirmation="outputs/nostos0-pshg-acquisition-shift-v1-confirmation/confirmation_rows.jsonl",
        nostos_score="full_contract",
        acquisition_score="acquisition_qc",
        endpoint_score="endpoint_qc",
        feature_source="diagnostics.components",
        bootstrap_group_field="reference_group_id",
        historical_accepted=230,
    ),
    DomainSpec(
        name="tendon_pshg_xrd",
        development="outputs/nostos0-tlt-pshg-xrd-v1-locked-development/development_rows.jsonl",
        confirmation="outputs/nostos0-tlt-pshg-xrd-v1-confirmation/confirmation_rows.jsonl",
        nostos_score="full_contract",
        acquisition_score="acquisition_qc",
        endpoint_score="endpoint_qc",
        feature_source="diagnostics.components",
        bootstrap_group_field="sample",
        historical_accepted=229,
        caution="Only two independent confirmation specimens; intervals are descriptive.",
    ),
    DomainSpec(
        name="heaton_in_vivo_shg",
        development="outputs/nostos0-heaton-in-vivo-shg-v1-risk-development/development_perturbation_rows.jsonl",
        confirmation="outputs/nostos0-heaton-in-vivo-shg-v1-confirmation/confirmation_perturbation_rows.jsonl",
        nostos_score="full_contract",
        acquisition_score="acquisition_qc",
        endpoint_score="endpoint_qc",
        feature_source="risk_components",
        bootstrap_group_field="mouse",
        historical_accepted=120,
        caution=(
            "Development and confirmation are separate acquisition experiments on the same mouse cohort; "
            "this is not population transfer."
        ),
    ),
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not an object")
            rows.append(value)
    if not rows:
        raise ValueError(f"No rows in {path}")
    return rows


def _eligible(rows: Sequence[Mapping[str, Any]], endpoint_filter: str | None) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if not bool(row.get("pair_registration_eligible", False)):
            continue
        if not bool(row.get("reference_eligible", False)):
            continue
        endpoint = str(row.get("endpoint_family") or row.get("endpoint") or "")
        if endpoint_filter is not None and endpoint != endpoint_filter:
            continue
        output.append(dict(row))
    if not output:
        raise ValueError("No eligible rows after applying the frozen endpoint filter")
    output.sort(key=lambda row: str(row["case_id"]))
    return output


def _nested_mapping(row: Mapping[str, Any], source: str) -> Mapping[str, Any]:
    current: Any = row
    for key in source.split("."):
        if not isinstance(current, Mapping) or key not in current:
            raise ValueError(f"Row {row.get('case_id')} lacks feature source {source!r}")
        current = current[key]
    if not isinstance(current, Mapping):
        raise ValueError(f"Feature source {source!r} is not a mapping")
    return current


def _endpoint_name(row: Mapping[str, Any]) -> str:
    return str(row.get("endpoint_family") or row.get("endpoint") or "primary")


def _feature_schema(
    development: Sequence[Mapping[str, Any]],
    confirmation: Sequence[Mapping[str, Any]],
    spec: DomainSpec,
) -> tuple[list[str], list[str]]:
    excluded = set(spec.excluded_features)
    dev_keys = {
        str(key)
        for row in development
        for key, value in _nested_mapping(row, spec.feature_source).items()
        if key not in excluded and isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    if not dev_keys:
        raise ValueError(f"{spec.name} exposes no numerical comparator features")
    for row in (*development, *confirmation):
        mapping = _nested_mapping(row, spec.feature_source)
        missing = dev_keys - set(mapping)
        if missing:
            raise ValueError(f"{spec.name} row {row['case_id']} lacks features {sorted(missing)}")
        values = np.asarray([float(mapping[key]) for key in sorted(dev_keys)], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{spec.name} row {row['case_id']} has a non-finite feature")
    endpoints = sorted({_endpoint_name(row) for row in development})
    unseen = sorted({_endpoint_name(row) for row in confirmation} - set(endpoints))
    if unseen:
        raise ValueError(f"{spec.name} confirmation has unseen endpoints {unseen}")
    return sorted(dev_keys), endpoints


def _feature_matrix(
    rows: Sequence[Mapping[str, Any]],
    spec: DomainSpec,
    numeric_names: Sequence[str],
    endpoint_names: Sequence[str],
) -> tuple[np.ndarray, list[str]]:
    numeric = np.asarray(
        [
            [float(_nested_mapping(row, spec.feature_source)[name]) for name in numeric_names]
            for row in rows
        ],
        dtype=float,
    )
    encoded = np.asarray(
        [[float(_endpoint_name(row) == endpoint) for endpoint in endpoint_names] for row in rows],
        dtype=float,
    )
    matrix = np.concatenate([numeric, encoded], axis=1)
    names = [f"component:{name}" for name in numeric_names] + [
        f"endpoint:{name}" for name in endpoint_names
    ]
    return matrix, names


def _feature_fingerprint(rows: Sequence[Mapping[str, Any]], names: Sequence[str], matrix: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(list(names), separators=(",", ":")).encode("utf-8"))
    digest.update(json.dumps([str(row["case_id"]) for row in rows], separators=(",", ":")).encode("utf-8"))
    digest.update(np.asarray(matrix, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def _group_weights(rows: Sequence[Mapping[str, Any]], group_field: str) -> np.ndarray:
    groups = [str(row[group_field]) for row in rows]
    counts = {group: groups.count(group) for group in sorted(set(groups))}
    weights = np.asarray([1.0 / counts[group] for group in groups], dtype=float)
    return weights / np.mean(weights)


def _group_class_weights(
    rows: Sequence[Mapping[str, Any]], group_field: str, labels: np.ndarray
) -> np.ndarray:
    weights = _group_weights(rows, group_field)
    totals = {value: float(np.sum(weights[labels == value])) for value in (0, 1)}
    if not all(total > 0 for total in totals.values()):
        raise ValueError("Both invalidity classes are required in development")
    target = float(np.sum(weights)) / 2.0
    factors = {value: target / totals[value] for value in (0, 1)}
    output = weights * np.asarray([factors[int(value)] for value in labels], dtype=float)
    return output / np.mean(output)


def _fit_predictors(
    development: Sequence[Mapping[str, Any]],
    confirmation: Sequence[Mapping[str, Any]],
    spec: DomainSpec,
) -> dict[str, Any]:
    numeric_names, endpoint_names = _feature_schema(development, confirmation, spec)
    x_dev, feature_names = _feature_matrix(development, spec, numeric_names, endpoint_names)
    x_conf, repeated_names = _feature_matrix(confirmation, spec, numeric_names, endpoint_names)
    if feature_names != repeated_names:
        raise AssertionError("Feature schema changed between partitions")
    variance = np.var(x_dev, axis=0)
    retained = np.flatnonzero(variance > 0)
    if not len(retained):
        raise ValueError(f"{spec.name} has no nonconstant development features")
    x_dev = x_dev[:, retained]
    x_conf = x_conf[:, retained]
    feature_names = [feature_names[index] for index in retained]
    labels = np.asarray([int(bool(row["invalid"])) for row in development], dtype=int)
    if set(labels.tolist()) != {0, 1}:
        raise ValueError(f"{spec.name} development does not contain both invalidity classes")

    group_weights = _group_weights(development, spec.bootstrap_group_field)
    scaler = StandardScaler()
    scaler.fit(x_dev, sample_weight=group_weights)
    x_dev_scaled = scaler.transform(x_dev)
    x_conf_scaled = scaler.transform(x_conf)
    logistic = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=2000,
        solver="liblinear",
        random_state=SEED,
    )
    logistic.fit(x_dev_scaled, labels, sample_weight=group_weights)
    logistic_score = logistic.predict_proba(x_conf_scaled)[:, 1]

    boosted = HistGradientBoostingClassifier(
        max_iter=100,
        learning_rate=0.05,
        max_depth=3,
        l2_regularization=1.0,
        random_state=SEED,
    )
    boosted.fit(
        x_dev,
        labels,
        sample_weight=_group_class_weights(development, spec.bootstrap_group_field, labels),
    )
    boosted_score = boosted.predict_proba(x_conf)[:, 1]

    dev_fingerprint = _feature_fingerprint(development, feature_names, x_dev)
    conf_fingerprint = _feature_fingerprint(confirmation, feature_names, x_conf)
    complemented = [dict(row, invalid=not bool(row["invalid"])) for row in confirmation]
    complemented_matrix, _ = _feature_matrix(
        complemented,
        spec,
        numeric_names,
        endpoint_names,
    )
    complemented_matrix = complemented_matrix[:, retained]
    complemented_fingerprint = _feature_fingerprint(
        complemented, feature_names, complemented_matrix
    )
    if conf_fingerprint != complemented_fingerprint:
        raise AssertionError("Feature extraction depends on confirmation labels")

    return {
        "feature_names": feature_names,
        "development_feature_sha256": dev_fingerprint,
        "confirmation_feature_sha256": conf_fingerprint,
        "label_complement_feature_sha256": complemented_fingerprint,
        "label_blind": conf_fingerprint == complemented_fingerprint,
        "logistic_coefficients": {
            name: float(value)
            for name, value in zip(feature_names, logistic.coef_[0], strict=True)
        },
        "logistic_intercept": float(logistic.intercept_[0]),
        "logistic_score": logistic_score,
        "boosted_score": boosted_score,
    }


def _risk_coverage_auc(scores: np.ndarray, invalid: np.ndarray) -> float:
    if scores.ndim != 1 or invalid.ndim != 1 or len(scores) != len(invalid) or not len(scores):
        raise ValueError("Aligned nonempty score and invalidity vectors are required")
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_invalid = invalid[order]
    coverage = [0.0]
    risk = [0.0]
    cumulative_invalid = 0
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and sorted_scores[end] == sorted_scores[index]:
            end += 1
        cumulative_invalid += int(np.sum(sorted_invalid[index:end]))
        coverage.append(end / len(order))
        risk.append(cumulative_invalid / end)
        index = end
    return float(np.trapezoid(np.asarray(risk), np.asarray(coverage)))


def _nearest_tied_indices(scores: np.ndarray, target: int) -> np.ndarray:
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    boundaries: list[int] = []
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and sorted_scores[end] == sorted_scores[index]:
            end += 1
        boundaries.append(end)
        index = end
    distances = np.abs(np.asarray(boundaries) - min(max(target, 1), len(order)))
    candidates = np.flatnonzero(distances == np.min(distances))
    chosen = int(candidates[-1])
    return order[: boundaries[chosen]]


def _score_vectors(
    rows: Sequence[Mapping[str, Any]], spec: DomainSpec, learned: Mapping[str, Any]
) -> dict[str, np.ndarray]:
    vectors = {
        "nostos": np.asarray([float(row["scores"][spec.nostos_score]) for row in rows]),
        "acquisition_qc": np.asarray(
            [float(row["scores"][spec.acquisition_score]) for row in rows]
        ),
        "logistic_input_only": np.asarray(learned["logistic_score"], dtype=float),
        "boosted_input_only": np.asarray(learned["boosted_score"], dtype=float),
    }
    if spec.endpoint_score is not None:
        vectors["endpoint_qc"] = np.asarray(
            [float(row["scores"][spec.endpoint_score]) for row in rows]
        )
    if not all(np.isfinite(vector).all() for vector in vectors.values()):
        raise ValueError(f"{spec.name} produced a non-finite score")
    return vectors


def _summaries(
    scores: Mapping[str, np.ndarray], invalid: np.ndarray, target: int
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, vector in scores.items():
        indices = _nearest_tied_indices(vector, target)
        output[name] = {
            "aurc": _risk_coverage_auc(vector, invalid),
            "matched_count": int(len(indices)),
            "matched_coverage": float(len(indices) / len(vector)),
            "matched_invalid": int(np.sum(invalid[indices])),
            "matched_risk": float(np.mean(invalid[indices])),
        }
    return output


def _bootstrap(
    rows: Sequence[Mapping[str, Any]],
    spec: DomainSpec,
    scores: Mapping[str, np.ndarray],
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    invalid = np.asarray([int(bool(row["invalid"])) for row in rows], dtype=int)
    group_values = [str(row[spec.bootstrap_group_field]) for row in rows]
    groups = sorted(set(group_values))
    group_indices = {
        group: np.asarray([index for index, value in enumerate(group_values) if value == group])
        for group in groups
    }
    target_fraction = spec.historical_accepted / len(rows)
    rng = np.random.default_rng(seed)
    differences = {
        name: {"aurc": [], "matched_risk": []}
        for name in scores
        if name != "nostos"
    }
    for _ in range(draws):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([group_indices[str(group)] for group in sampled])
        boot_invalid = invalid[indices]
        boot_scores = {name: vector[indices] for name, vector in scores.items()}
        target = max(1, int(round(target_fraction * len(indices))))
        nostos_auc = _risk_coverage_auc(boot_scores["nostos"], boot_invalid)
        nostos_selected = _nearest_tied_indices(boot_scores["nostos"], target)
        nostos_risk = float(np.mean(boot_invalid[nostos_selected]))
        for name, vector in boot_scores.items():
            if name == "nostos":
                continue
            auc = _risk_coverage_auc(vector, boot_invalid)
            selected = _nearest_tied_indices(vector, target)
            risk = float(np.mean(boot_invalid[selected]))
            differences[name]["aurc"].append(auc - nostos_auc)
            differences[name]["matched_risk"].append(risk - nostos_risk)
    output: dict[str, Any] = {}
    for name, metrics in differences.items():
        output[name] = {}
        for metric, values in metrics.items():
            array = np.asarray(values, dtype=float)
            output[name][metric] = {
                "median": float(np.median(array)),
                "ci95": [float(value) for value in np.percentile(array, [2.5, 97.5])],
                "probability_positive": float(np.mean(array > 0)),
            }
    return {
        "draws": draws,
        "seed": seed,
        "unit": spec.bootstrap_group_field,
        "independent_units": len(groups),
        "contrasts": output,
    }


def _domain_result(root: Path, spec: DomainSpec, *, draws: int, seed: int) -> dict[str, Any]:
    development_path = root / spec.development
    confirmation_path = root / spec.confirmation
    development = _eligible(_read_jsonl(development_path), spec.endpoint_filter)
    confirmation = _eligible(_read_jsonl(confirmation_path), spec.endpoint_filter)
    overlap = sorted(
        {str(row[spec.bootstrap_group_field]) for row in development}
        & {str(row[spec.bootstrap_group_field]) for row in confirmation}
    )
    if overlap and spec.name != "heaton_in_vivo_shg":
        raise ValueError(f"{spec.name} development-confirmation group overlap: {overlap}")
    learned = _fit_predictors(development, confirmation, spec)
    vectors = _score_vectors(confirmation, spec, learned)
    invalid = np.asarray([int(bool(row["invalid"])) for row in confirmation], dtype=int)
    summaries = _summaries(vectors, invalid, spec.historical_accepted)
    predictions = [
        {
            "case_id": str(row["case_id"]),
            "group": str(row[spec.bootstrap_group_field]),
            "invalid": bool(row["invalid"]),
            "scores": {name: float(vector[index]) for name, vector in vectors.items()},
        }
        for index, row in enumerate(confirmation)
    ]
    return {
        "domain": spec.name,
        "development": {
            "path": spec.development,
            "sha256": _sha256_file(development_path),
            "rows": len(development),
            "independent_units": len(
                {str(row[spec.bootstrap_group_field]) for row in development}
            ),
        },
        "confirmation": {
            "path": spec.confirmation,
            "sha256": _sha256_file(confirmation_path),
            "rows": len(confirmation),
            "invalid": int(np.sum(invalid)),
            "independent_units": len(
                {str(row[spec.bootstrap_group_field]) for row in confirmation}
            ),
            "development_group_overlap": overlap,
        },
        "score_keys": {
            "nostos": spec.nostos_score,
            "acquisition_qc": spec.acquisition_score,
            "endpoint_qc": spec.endpoint_score,
        },
        "historical_nostos_accepted_count": spec.historical_accepted,
        "learned_comparator": {
            key: value
            for key, value in learned.items()
            if key not in {"logistic_score", "boosted_score"}
        },
        "summary": summaries,
        "bootstrap": _bootstrap(
            confirmation, spec, vectors, draws=draws, seed=seed
        ),
        "predictions": predictions,
        "caution": spec.caution,
    }


def build_selective_risk_baseline_audit(
    root: Path,
    *,
    draws: int = 5000,
    protocol_path: str = "docs/NOSTOS0_SELECTIVE_RISK_BASELINE_AUDIT_V1_PROTOCOL.md",
) -> dict[str, Any]:
    protocol = root / protocol_path
    if not protocol.is_file():
        raise FileNotFoundError(protocol)
    domains = [
        _domain_result(root, spec, draws=draws, seed=SEED + 1009 * index)
        for index, spec in enumerate(DOMAIN_SPECS)
    ]
    learned_names = ("logistic_input_only", "boosted_input_only")
    aurc_wins = sum(
        all(item["summary"][name]["aurc"] > item["summary"]["nostos"]["aurc"] for name in learned_names)
        for item in domains
    )
    matched_wins = sum(
        all(
            item["summary"][name]["matched_risk"]
            >= item["summary"]["nostos"]["matched_risk"]
            for name in learned_names
        )
        for item in domains
    )
    interval_wins = sum(
        all(
            item["bootstrap"]["contrasts"][name]["aurc"]["ci95"][0] > 0
            for name in learned_names
        )
        for item in domains
    )
    worst_difference = min(
        item["summary"][name]["aurc"] - item["summary"]["nostos"]["aurc"]
        for item in domains
        for name in learned_names
    )
    label_blind = all(item["learned_comparator"]["label_blind"] for item in domains)
    gates = {
        "nostos_aurc_lower_than_both_learned_in_at_least_four_domains": aurc_wins >= 4,
        "nostos_matched_risk_no_higher_than_both_learned_in_at_least_four_domains": matched_wins >= 4,
        "two_domains_have_both_learned_aurc_intervals_above_zero": interval_wins >= 2,
        "no_learned_comparator_aurc_advantage_exceeds_0_02": worst_difference >= -0.02,
        "confirmation_feature_extraction_is_label_blind": label_blind,
    }
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": protocol_path,
        "protocol_sha256": _sha256_file(protocol),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "domains": domains,
        "cross_domain": {
            "domains": len(domains),
            "nostos_aurc_wins_against_both_learned": aurc_wins,
            "nostos_matched_risk_wins_against_both_learned": matched_wins,
            "domains_with_both_learned_aurc_ci_lower_above_zero": interval_wins,
            "worst_learned_minus_nostos_aurc": worst_difference,
        },
        "success_gates_before_repeat": gates,
        "scope": (
            "Retrospective input-only comparator audit on frozen public-data partitions; "
            "not prospective, distribution-free, biological, clinical or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def write_selective_risk_baseline_audit(
    root: Path, output: Path, *, draws: int = 5000
) -> dict[str, Any]:
    payload = build_selective_risk_baseline_audit(root, draws=draws)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload
