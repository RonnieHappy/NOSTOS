"""Frozen external transfer of selective FFT orientation to annotated SHG collagen."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.metrics import roc_auc_score

from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees
from nostos.validation.selective_fft_confirmation import THRESHOLD, _wilson
from nostos.validation.selective_fft_development import self_perturbation_score


PROTOCOL_SHA256 = "e341937021cd9b9eb545dba2080e0c9f058b22dc2824d815a4065d1b0ce13b8a"
DATASET_DOI = "10.5281/zenodo.7243211"
ARCHIVE_MD5 = "fad5956015f7802d27b3d312bfddc8ec"


def _index(test_root: Path) -> dict[str, str]:
    rows = {}
    for line in (test_root / "index2fname.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            number, identifier = line.split(maxsplit=1)
            rows[number] = identifier.strip()
    return rows


def _load(path: Path, *, nearest: bool = False) -> np.ndarray:
    with Image.open(path) as opened:
        image = opened.convert("L").resize(
            (128, 128), Image.Resampling.NEAREST if nearest else Image.Resampling.BILINEAR
        )
        values = np.asarray(image)
    return (values > 0) if nearest else values.astype(np.float32) / 255.0


def _cluster_interval(rows: list[dict], *, draws: int = 10000, seed: int = 7243211) -> list[float]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["source_group"], []).append(row)
    names = sorted(groups)
    rng = np.random.default_rng(seed)
    risks = []
    for _ in range(draws):
        sampled = [row for name in rng.choice(names, size=len(names), replace=True) for row in groups[name]]
        accepted = [row for row in sampled if row["accepted"]]
        if accepted:
            risks.append(float(np.mean([row["invalid"] for row in accepted])))
    if not risks:
        return [0.0, 1.0]
    return [float(value) for value in np.quantile(risks, (0.025, 0.975))]


def run_transfer(dataset_root: Path, output: Path) -> dict:
    test_root = dataset_root / "final_train_test" / "test"
    identifiers = _index(test_root)
    rows = []
    for number in sorted(identifiers, key=int):
        image_path = test_root / "images" / f"{number}.png"
        label_path = test_root / "labels" / f"{number}.png"
        image, label = _load(image_path), _load(label_path, nearest=True)
        score, diagnostics = self_perturbation_score(image, 1.0)
        image_measurement = diagnostics["measurement"]
        reference = extract_spatial_fft(label.astype(np.float32), pixel_size_um=1.0)
        label_coverage = float(label.mean())
        eligible = label_coverage >= 0.001 and reference.anisotropy >= 0.15
        disagreement = axial_angular_error_degrees(
            image_measurement["orientation"], reference.orientation_degrees
        )
        identifier = identifiers[number]
        source_group = identifier.rsplit("_", 1)[0]
        accepted = bool(score <= THRESHOLD)
        legacy_accepted = not (
            image_measurement["snr"] < 3.0 or image_measurement["wavelength"] < 4.0
        )
        rows.append({
            "patch": int(number), "identifier": identifier, "source_group": source_group,
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "label_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest(),
            "label_coverage": label_coverage, "label_anisotropy": float(reference.anisotropy),
            "reference_orientation": float(reference.orientation_degrees),
            "reference_eligible": eligible,
            "image_orientation": float(image_measurement["orientation"]),
            "axial_disagreement_degrees": float(disagreement),
            "score": float(score), "accepted": accepted, "legacy_accepted": legacy_accepted,
            "invalid": bool(disagreement > 10.0) if eligible else None,
            "diagnostics": diagnostics,
        })
    eligible = [row for row in rows if row["reference_eligible"]]
    accepted = [row for row in eligible if row["accepted"]]
    legacy = [row for row in eligible if row["legacy_accepted"]]
    invalid_count = sum(bool(row["invalid"]) for row in accepted)
    coverage = len(accepted) / len(eligible) if eligible else 0.0
    risk = invalid_count / len(accepted) if accepted else 1.0
    risk_all = float(np.mean([row["invalid"] for row in eligible])) if eligible else 1.0
    legacy_coverage = len(legacy) / len(eligible) if eligible else 0.0
    legacy_risk = float(np.mean([row["invalid"] for row in legacy])) if legacy else 1.0
    labels = [bool(row["invalid"]) for row in eligible]
    auc = float(roc_auc_score(labels, [row["score"] for row in eligible])) if len(set(labels)) == 2 else None
    median_error = float(np.median([row["axial_disagreement_degrees"] for row in accepted])) if accepted else None
    cluster_interval = _cluster_interval(eligible) if eligible else [0.0, 1.0]
    eligible_groups = len({row["source_group"] for row in eligible})
    gates = {
        "eligible_patches_ge_100_and_groups_ge_50": len(eligible) >= 100 and eligible_groups >= 50,
        "selective_coverage_ge_0.50": coverage >= 0.50,
        "cluster_risk_upper_le_0.15": cluster_interval[1] <= 0.15,
        "accepted_median_disagreement_le_5_degrees": median_error is not None and median_error <= 5.0,
        "invalid_detection_auc_ge_0.75": auc is not None and auc >= 0.75,
        "lower_risk_than_unselected_and_legacy_or_legacy_low_coverage": risk < risk_all and (risk < legacy_risk or legacy_coverage < coverage / 2),
    }
    payload = {
        "protocol_version": "nostos-selective-shg-transfer/1.0",
        "protocol_sha256": PROTOCOL_SHA256,
        "dataset": {"doi": DATASET_DOI, "archive_md5": ARCHIVE_MD5, "split": "test only"},
        "frozen_threshold": THRESHOLD,
        "status": "pass" if all(gates.values()) else "fail",
        "summary": {
            "test_patches": len(rows), "test_source_groups": len({row["source_group"] for row in rows}),
            "reference_eligible": len(eligible), "eligible_source_groups": eligible_groups,
            "accepted": len(accepted), "selective_coverage": coverage,
            "selective_risk": risk, "selective_risk_wilson95": _wilson(invalid_count, len(accepted)),
            "selective_risk_cluster_bootstrap95": cluster_interval,
            "risk_all": risk_all, "invalid_detection_auc": auc,
            "legacy_coverage": legacy_coverage, "legacy_risk": legacy_risk,
            "accepted_median_axial_disagreement_degrees": median_error,
        },
        "success_gates": gates,
        "scope": "External annotated SHG test-set validation of global 2D orientation support only.",
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "selective_shg_transfer.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return payload
