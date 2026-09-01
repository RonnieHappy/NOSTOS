from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def _participant_site_stain_means(frame: pd.DataFrame, feature: str) -> pd.DataFrame:
    required = {"participant_id", "site", "stain", feature}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    clean = frame.loc[:, list(required)].dropna()
    return clean.groupby(["participant_id", "site", "stain"], as_index=False)[feature].mean()


def cross_stain_spearman(
    frame: pd.DataFrame,
    feature: str,
    *,
    stains: tuple[str, ...] = ("HE", "SafO", "PLM"),
    iterations: int = 2000,
    seed: int = 240826,
) -> list[dict[str, float | int | str]]:
    """Pair adjacent-section features by participant/site and bootstrap participants."""
    if iterations < 100:
        raise ValueError("at least 100 bootstrap iterations are required")
    grouped = _participant_site_stain_means(frame, feature)
    wide = grouped.pivot(index=["participant_id", "site"], columns="stain", values=feature)
    rng = np.random.default_rng(seed)
    results: list[dict[str, float | int | str]] = []
    for first, second in combinations(stains, 2):
        paired = wide.loc[:, [first, second]].dropna().reset_index()
        participants = paired["participant_id"].unique()
        if len(participants) < 3:
            results.append({"stain_a": first, "stain_b": second, "participant_count": len(participants), "rho": float("nan"), "ci_95_lower": float("nan"), "ci_95_upper": float("nan")})
            continue
        rho = float(spearmanr(paired[first], paired[second]).statistic)
        samples = np.empty(iterations, dtype=float)
        for index in range(iterations):
            selected_ids = rng.choice(participants, size=len(participants), replace=True)
            pieces = []
            for draw, participant in enumerate(selected_ids):
                piece = paired[paired["participant_id"] == participant].copy()
                piece["bootstrap_draw"] = draw
                pieces.append(piece)
            sampled = pd.concat(pieces, ignore_index=True)
            samples[index] = spearmanr(sampled[first], sampled[second]).statistic
        finite = samples[np.isfinite(samples)]
        lower, upper = np.quantile(finite, [0.025, 0.975]) if finite.size else (np.nan, np.nan)
        results.append({"stain_a": first, "stain_b": second, "participant_count": len(participants), "paired_site_count": len(paired), "rho": rho, "ci_95_lower": float(lower), "ci_95_upper": float(upper)})
    return results


def medial_lateral_differences(frame: pd.DataFrame, feature: str) -> pd.DataFrame:
    """Return one medial-minus-lateral contrast per participant and stain."""
    grouped = _participant_site_stain_means(frame, feature)
    wide = grouped.pivot(index=["participant_id", "stain"], columns="site", values=feature)
    if not {"Medial", "Lateral"}.issubset(wide.columns):
        return pd.DataFrame(columns=["participant_id", "stain", "medial_minus_lateral"])
    paired = wide.loc[:, ["Medial", "Lateral"]].dropna()
    result = (paired["Medial"] - paired["Lateral"]).rename("medial_minus_lateral").reset_index()
    return result


def benjamini_hochberg(p_values: list[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or np.any((values < 0) | (values > 1)):
        raise ValueError("p-values must be a one-dimensional vector in [0, 1]")
    order = np.argsort(values)
    ranked = values[order] * len(values) / np.arange(1, len(values) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty_like(ranked)
    adjusted[order] = np.minimum(ranked, 1.0)
    return adjusted

