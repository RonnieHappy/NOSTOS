"""Leave-one-domain-out transfer of a shared NOSTOS input-risk geometry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from nostos.validation.selective_risk_baseline import (
    DOMAIN_SPECS,
    DomainSpec,
    SEED,
    _eligible,
    _nearest_tied_indices,
    _read_jsonl,
    _risk_coverage_auc,
    _sha256_file,
)


PROTOCOL_VERSION = "nostos-cross-domain-risk-transfer/1.0"
CHANNELS = ("acquisition", "identifiability", "scale", "consistency")


def _components(row: Mapping[str, Any], spec: DomainSpec) -> Mapping[str, Any]:
    value: Any = row
    for key in spec.feature_source.split("."):
        value = value[key]
    if not isinstance(value, Mapping):
        raise ValueError("Risk components are not a mapping")
    return value


def _value(mapping: Mapping[str, Any], name: str) -> float:
    value = float(mapping[name])
    if not np.isfinite(value):
        raise ValueError(f"Non-finite component {name}")
    return value


def shared_risk_geometry(row: Mapping[str, Any], spec: DomainSpec) -> np.ndarray:
    """Return the frozen four-channel dimensionless input-risk geometry."""

    c = _components(row, spec)
    if spec.name == "biosr_f_actin":
        raw = (
            _value(c, "acquisition_qc"),
            _value(c, "measurement_identifiability"),
            max(
                _value(c, "physical_sampling"),
                _value(c, "scale_conditioned_acquisition_support"),
            ),
            _value(c, "perturbation_stability"),
        )
    elif spec.name == "fmd_widefield":
        raw = (
            max(
                _value(c, "acquisition_qc"),
                _value(c, "declared_capture_noise_deficit"),
            ),
            max(
                _value(c, "measurement_identifiability"),
                _value(c, "orientation_resultant_risk"),
                _value(c, "orientation_estimator_disagreement_risk"),
                _value(c, "spectral_orientation_anisotropy_risk"),
            ),
            _value(c, "scale_sampling"),
            max(
                _value(c, "perturbation_stability"),
                _value(c, "cross_scale_agreement"),
            ),
        )
    elif spec.name == "pshg_tiss_breast":
        raw = (
            _value(c, "acquisition_qc"),
            _value(c, "coherence"),
            _value(c, "scale_consistency"),
            _value(c, "split_stack"),
        )
    elif spec.name == "tendon_pshg_xrd":
        raw = (
            _value(c, "acquisition_qc"),
            _value(c, "coherence"),
            _value(c, "scale_consistency"),
            _value(c, "estimator_consistency"),
        )
    elif spec.name == "heaton_in_vivo_shg":
        raw = (
            _value(c, "acquisition_qc"),
            _value(c, "endpoint_support"),
            _value(c, "scale_consistency"),
            max(
                _value(c, "threshold_consistency"),
                _value(c, "nested_support_consistency"),
            ),
        )
    else:
        raise ValueError(f"Unmapped domain {spec.name}")
    array = np.asarray(raw, dtype=float)
    if np.any(array < 0):
        raise ValueError(f"Negative risk component in {spec.name}")
    return np.log1p(np.clip(array, 0.0, 20.0))


def _matrix(rows: Sequence[Mapping[str, Any]], spec: DomainSpec) -> np.ndarray:
    matrix = np.asarray([shared_risk_geometry(row, spec) for row in rows], dtype=float)
    if matrix.shape != (len(rows), len(CHANNELS)) or not np.isfinite(matrix).all():
        raise ValueError("Invalid shared risk geometry")
    return matrix


def _fingerprint(rows: Sequence[Mapping[str, Any]], matrix: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(CHANNELS, separators=(",", ":")).encode("utf-8"))
    digest.update(json.dumps([str(row["case_id"]) for row in rows], separators=(",", ":")).encode("utf-8"))
    digest.update(np.asarray(matrix, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def _balanced_weights(
    blocks: Sequence[tuple[DomainSpec, Sequence[Mapping[str, Any]]]],
) -> np.ndarray:
    """Equal domain/class mass, then equal group mass within domain/class."""

    all_weights: list[float] = []
    domain_mass = 1.0 / len(blocks)
    for spec, rows in blocks:
        labels = np.asarray([int(bool(row["invalid"])) for row in rows], dtype=int)
        if set(labels.tolist()) != {0, 1}:
            raise ValueError(f"{spec.name} lacks both development classes")
        weights = np.zeros(len(rows), dtype=float)
        for label in (0, 1):
            label_indices = np.flatnonzero(labels == label)
            groups = sorted({str(rows[index][spec.bootstrap_group_field]) for index in label_indices})
            class_mass = domain_mass / 2.0
            for group in groups:
                indices = np.asarray(
                    [
                        index
                        for index in label_indices
                        if str(rows[index][spec.bootstrap_group_field]) == group
                    ],
                    dtype=int,
                )
                weights[indices] = class_mass / len(groups) / len(indices)
        all_weights.extend(weights.tolist())
    output = np.asarray(all_weights, dtype=float)
    return output / np.mean(output)


def _fit_transfer(
    training: Sequence[tuple[DomainSpec, Sequence[Mapping[str, Any]]]],
    target_rows: Sequence[Mapping[str, Any]],
    target_spec: DomainSpec,
) -> dict[str, Any]:
    blocks = [_matrix(rows, spec) for spec, rows in training]
    x_train = np.concatenate(blocks, axis=0)
    y_train = np.concatenate(
        [np.asarray([int(bool(row["invalid"])) for row in rows]) for _, rows in training]
    )
    weights = _balanced_weights(training)
    x_target = _matrix(target_rows, target_spec)
    scaler = StandardScaler()
    scaler.fit(x_train, sample_weight=weights)
    logistic = LogisticRegression(
        C=1.0,
        solver="liblinear",
        max_iter=2000,
        random_state=SEED,
    )
    logistic.fit(scaler.transform(x_train), y_train, sample_weight=weights)
    logistic_score = logistic.predict_proba(scaler.transform(x_target))[:, 1]
    boosted = HistGradientBoostingClassifier(
        max_iter=100,
        learning_rate=0.05,
        max_depth=3,
        l2_regularization=1.0,
        random_state=SEED,
    )
    boosted.fit(x_train, y_train, sample_weight=weights)
    boosted_score = boosted.predict_proba(x_target)[:, 1]
    target_fingerprint = _fingerprint(target_rows, x_target)
    complemented = [dict(row, invalid=not bool(row["invalid"])) for row in target_rows]
    complemented_matrix = _matrix(complemented, target_spec)
    complemented_fingerprint = _fingerprint(complemented, complemented_matrix)
    if target_fingerprint != complemented_fingerprint:
        raise AssertionError("Shared geometry depends on target invalidity labels")
    return {
        "training_domains": [spec.name for spec, _ in training],
        "training_rows": int(len(x_train)),
        "training_invalid": int(np.sum(y_train)),
        "training_domain_row_counts": {spec.name: len(rows) for spec, rows in training},
        "channels": list(CHANNELS),
        "target_geometry_sha256": target_fingerprint,
        "label_complement_geometry_sha256": complemented_fingerprint,
        "label_blind": target_fingerprint == complemented_fingerprint,
        "logistic_coefficients": {
            name: float(value)
            for name, value in zip(CHANNELS, logistic.coef_[0], strict=True)
        },
        "logistic_intercept": float(logistic.intercept_[0]),
        "logistic_score": logistic_score,
        "boosted_score": boosted_score,
    }


def _summaries(
    scores: Mapping[str, np.ndarray], invalid: np.ndarray, target: int
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, score in scores.items():
        selected = _nearest_tied_indices(score, target)
        output[name] = {
            "aurc": _risk_coverage_auc(score, invalid),
            "matched_count": int(len(selected)),
            "matched_coverage": float(len(selected) / len(score)),
            "matched_invalid": int(np.sum(invalid[selected])),
            "matched_risk": float(np.mean(invalid[selected])),
        }
    return output


def _bootstrap(
    rows: Sequence[Mapping[str, Any]],
    spec: DomainSpec,
    scores: Mapping[str, np.ndarray],
    best: str,
    corresponding_domain_model: str,
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    invalid = np.asarray([int(bool(row["invalid"])) for row in rows], dtype=int)
    group_values = [str(row[spec.bootstrap_group_field]) for row in rows]
    groups = sorted(set(group_values))
    group_indices = {
        group: np.asarray([i for i, value in enumerate(group_values) if value == group])
        for group in groups
    }
    target_fraction = spec.historical_accepted / len(rows)
    comparators = ("nostos", "acquisition_qc", corresponding_domain_model)
    differences = {name: {"aurc": [], "matched_risk": []} for name in comparators}
    rng = np.random.default_rng(seed)
    for _ in range(draws):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([group_indices[str(group)] for group in sampled])
        y = invalid[indices]
        sampled_scores = {name: score[indices] for name, score in scores.items()}
        target = max(1, int(round(target_fraction * len(indices))))
        best_auc = _risk_coverage_auc(sampled_scores[best], y)
        best_selected = _nearest_tied_indices(sampled_scores[best], target)
        best_risk = float(np.mean(y[best_selected]))
        for comparator in comparators:
            comparator_auc = _risk_coverage_auc(sampled_scores[comparator], y)
            comparator_selected = _nearest_tied_indices(sampled_scores[comparator], target)
            comparator_risk = float(np.mean(y[comparator_selected]))
            differences[comparator]["aurc"].append(comparator_auc - best_auc)
            differences[comparator]["matched_risk"].append(comparator_risk - best_risk)
    contrasts: dict[str, Any] = {}
    for comparator, metrics in differences.items():
        contrasts[comparator] = {}
        for metric, values in metrics.items():
            array = np.asarray(values, dtype=float)
            contrasts[comparator][metric] = {
                "median": float(np.median(array)),
                "ci95": [float(value) for value in np.percentile(array, [2.5, 97.5])],
                "probability_positive": float(np.mean(array > 0)),
            }
    return {
        "draws": draws,
        "seed": seed,
        "unit": spec.bootstrap_group_field,
        "independent_units": len(groups),
        "contrast_definition": "comparator minus better pooled transfer; positive favors transfer",
        "contrasts": contrasts,
    }


def build_cross_domain_risk_transfer(
    root: Path,
    *,
    draws: int = 5000,
    protocol_path: str = "docs/NOSTOS0_CROSS_DOMAIN_RISK_TRANSFER_V1_PROTOCOL.md",
    baseline_path: str = "outputs/nostos0-selective-risk-baseline-v1/selective_risk_baseline.json",
) -> dict[str, Any]:
    protocol = root / protocol_path
    baseline_file = root / baseline_path
    baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
    baseline_by_domain = {item["domain"]: item for item in baseline["domains"]}
    development: dict[str, list[dict[str, Any]]] = {}
    confirmation: dict[str, list[dict[str, Any]]] = {}
    for spec in DOMAIN_SPECS:
        development[spec.name] = _eligible(
            _read_jsonl(root / spec.development), spec.endpoint_filter
        )
        confirmation[spec.name] = _eligible(
            _read_jsonl(root / spec.confirmation), spec.endpoint_filter
        )
    results: list[dict[str, Any]] = []
    for fold, target_spec in enumerate(DOMAIN_SPECS):
        target_rows = confirmation[target_spec.name]
        training = [
            (spec, development[spec.name])
            for spec in DOMAIN_SPECS
            if spec.name != target_spec.name
        ]
        transferred = _fit_transfer(training, target_rows, target_spec)
        baseline_predictions = {
            row["case_id"]: row for row in baseline_by_domain[target_spec.name]["predictions"]
        }
        if set(baseline_predictions) != {str(row["case_id"]) for row in target_rows}:
            raise ValueError(f"Baseline predictions do not align for {target_spec.name}")
        scores = {
            "nostos": np.asarray(
                [float(row["scores"][target_spec.nostos_score]) for row in target_rows]
            ),
            "acquisition_qc": np.asarray(
                [float(row["scores"][target_spec.acquisition_score]) for row in target_rows]
            ),
            "transfer_logistic": np.asarray(transferred["logistic_score"], dtype=float),
            "transfer_boosted": np.asarray(transferred["boosted_score"], dtype=float),
            "domain_logistic": np.asarray(
                [
                    float(baseline_predictions[str(row["case_id"])]["scores"]["logistic_input_only"])
                    for row in target_rows
                ]
            ),
            "domain_boosted": np.asarray(
                [
                    float(baseline_predictions[str(row["case_id"])]["scores"]["boosted_input_only"])
                    for row in target_rows
                ]
            ),
        }
        invalid = np.asarray([int(bool(row["invalid"])) for row in target_rows], dtype=int)
        summary = _summaries(scores, invalid, target_spec.historical_accepted)
        transfer_names = ("transfer_logistic", "transfer_boosted")
        best = min(transfer_names, key=lambda name: (summary[name]["aurc"], name))
        corresponding = "domain_logistic" if best == "transfer_logistic" else "domain_boosted"
        predictions = [
            {
                "case_id": str(row["case_id"]),
                "group": str(row[target_spec.bootstrap_group_field]),
                "invalid": bool(row["invalid"]),
                "shared_geometry": {
                    name: float(value)
                    for name, value in zip(CHANNELS, shared_risk_geometry(row, target_spec), strict=True)
                },
                "scores": {name: float(vector[index]) for name, vector in scores.items()},
            }
            for index, row in enumerate(target_rows)
        ]
        results.append(
            {
                "domain": target_spec.name,
                "development_source_sha256": _sha256_file(root / target_spec.development),
                "confirmation_source_sha256": _sha256_file(root / target_spec.confirmation),
                "confirmation_rows": len(target_rows),
                "confirmation_invalid": int(np.sum(invalid)),
                "confirmation_independent_units": len(
                    {str(row[target_spec.bootstrap_group_field]) for row in target_rows}
                ),
                "historical_nostos_accepted_count": target_spec.historical_accepted,
                "held_out_development_absent": target_spec.name not in transferred["training_domains"],
                "transfer_model": {
                    key: value
                    for key, value in transferred.items()
                    if key not in {"logistic_score", "boosted_score"}
                },
                "better_transfer_model_descriptive": best,
                "corresponding_domain_trained_model": corresponding,
                "summary": summary,
                "bootstrap": _bootstrap(
                    target_rows,
                    target_spec,
                    scores,
                    best,
                    corresponding,
                    draws=draws,
                    seed=SEED + 2017 * fold,
                ),
                "predictions": predictions,
                "caution": target_spec.caution,
            }
        )
    acquisition_wins = max(
        sum(item["summary"][method]["aurc"] < item["summary"]["acquisition_qc"]["aurc"] for item in results)
        for method in ("transfer_logistic", "transfer_boosted")
    )
    better_aurc_wins = sum(
        item["summary"][item["better_transfer_model_descriptive"]]["aurc"]
        < item["summary"]["nostos"]["aurc"]
        for item in results
    )
    better_risk_wins = sum(
        item["summary"][item["better_transfer_model_descriptive"]]["matched_risk"]
        <= item["summary"]["nostos"]["matched_risk"]
        for item in results
    )
    within_domain_oracle = sum(
        item["summary"][item["better_transfer_model_descriptive"]]["aurc"]
        <= item["summary"][item["corresponding_domain_trained_model"]]["aurc"] + 0.02
        for item in results
    )
    acquisition_interval_wins = sum(
        item["bootstrap"]["contrasts"]["acquisition_qc"]["aurc"]["ci95"][0] > 0
        for item in results
    )
    no_leakage = all(item["held_out_development_absent"] for item in results)
    label_blind = all(item["transfer_model"]["label_blind"] for item in results)
    gates = {
        "one_transfer_model_beats_acquisition_qc_in_at_least_four_domains": acquisition_wins >= 4,
        "better_transfer_beats_nostos_aurc_in_at_least_three_domains": better_aurc_wins >= 3,
        "better_transfer_matched_risk_no_higher_than_nostos_in_at_least_three_domains": better_risk_wins >= 3,
        "better_transfer_within_0_02_of_domain_trained_in_at_least_three_domains": within_domain_oracle >= 3,
        "two_domains_acquisition_qc_minus_transfer_aurc_ci_above_zero": acquisition_interval_wins >= 2,
        "held_out_development_absent_in_all_folds": no_leakage,
        "confirmation_geometry_is_label_blind": label_blind,
    }
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "protocol": protocol_path,
        "protocol_sha256": _sha256_file(protocol),
        "baseline": baseline_path,
        "baseline_sha256": _sha256_file(baseline_file),
        "status_before_repeat_gate": "pass" if all(gates.values()) else "fail",
        "domains": results,
        "cross_domain": {
            "domains": len(results),
            "best_single_transfer_model_acquisition_qc_aurc_wins": acquisition_wins,
            "better_transfer_nostos_aurc_wins": better_aurc_wins,
            "better_transfer_nostos_matched_risk_wins": better_risk_wins,
            "better_transfer_within_0_02_of_domain_trained": within_domain_oracle,
            "acquisition_qc_minus_transfer_ci_above_zero": acquisition_interval_wins,
        },
        "success_gates_before_repeat": gates,
        "scope": (
            "Retrospective leave-one-domain-out transfer on frozen public-data partitions; "
            "not prospective, distribution-free, biological, clinical or intraoperative validation."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


__all__ = ["CHANNELS", "build_cross_domain_risk_transfer", "shared_risk_geometry"]
