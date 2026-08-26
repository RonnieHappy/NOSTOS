"""Cross-domain same-specimen retrieval under frozen acquisition shifts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image
from scipy import ndimage

from nostos.features.canonical_geometry import canonical_response_blocks
from nostos.features.stability_weighting import StabilityWeightModel, apply_stability_weights, fit_stability_weights
from nostos.features.universal import analyze_response_geometry
from nostos.validation.canonical_confirmation_v3 import _gamma, _illumination, _shot_noise
from nostos.validation.comparators import _ordered_responses, conventional_vector
from nostos.validation.perturbations import _center_crop_or_pad


DOMAINS = ("pshg", "nuclei", "mycelium", "collagen")
REPRESENTATIONS = ("conventional", "collapsed", "raw", "canonical")
PROTOCOL_SHA256 = "e6c45e2f2edcd2fdae155dd81e772c65001b823420051c68ec9543de61a8a653"


def _standardize(image: np.ndarray) -> np.ndarray:
    source = np.asarray(image, dtype=float)
    factors = (128 / source.shape[0], 128 / source.shape[1])
    values = ndimage.zoom(source, factors, order=1, mode="reflect")
    values = _center_crop_or_pad(values, (128, 128))
    values = (values - np.median(values)) / max(float(np.std(values)), np.finfo(float).eps)
    return np.clip(values, -5, 5).astype(np.float32)


def _read(path: Path) -> np.ndarray:
    if path.suffix.lower() in {".tif", ".tiff"}:
        values = tifffile.imread(path)
    else:
        values = np.asarray(Image.open(path).convert("L"))
    if values.ndim > 2:
        values = values[..., :3].mean(axis=-1)
    return _standardize(values)


def _pshg(root: Path) -> list[tuple[str, np.ndarray]]:
    rows = []
    for roi in sorted(path for path in root.iterdir() if path.is_dir()):
        frames = sorted(roi.glob("*_FSHG_p*.tif"))
        if len(frames) == 10:
            rows.append((roi.name, _standardize(np.mean([tifffile.imread(path) for path in frames], axis=0))))
    return rows


def _select(rows: list[tuple[str, np.ndarray]], count: int = 30) -> list[tuple[str, np.ndarray]]:
    return sorted(rows, key=lambda row: hashlib.sha256(row[0].encode()).hexdigest())[:count]


def load_cases(pshg_root: Path, nuclei_root: Path, mycelium_root: Path, collagen_root: Path) -> list[dict]:
    sources: dict[str, list[tuple[str, np.ndarray]]] = {
        "pshg": _pshg(pshg_root),
        "nuclei": [(path.stem, _read(path)) for path in sorted((nuclei_root / "images" / "images").glob("*.tif"))],
        "mycelium": [(f"{path.parent.parent.name}/{path.stem}", _read(path))
                      for path in sorted(mycelium_root.rglob("*")) if path.is_file() and path.parent.name == "image" and path.suffix.lower() in {".jpg", ".png", ".tif"}],
        "collagen": [(path.stem, _read(path)) for path in sorted((collagen_root / "final_train_test" / "test" / "images").glob("*.png"))],
    }
    cases = []
    for domain in DOMAINS:
        selected = _select(sources[domain])
        if len(selected) < 30:
            raise ValueError(f"{domain}: expected at least 30 cases, found {len(selected)}")
        for index, (identifier, image) in enumerate(selected):
            split = "development" if index < 15 else "confirmation"
            cases.append({"domain": domain, "identifier": identifier, "split": split, "image": image})
    return cases


def _perturb(image: np.ndarray, identifier: str, split: str) -> np.ndarray:
    seed = int(hashlib.sha256(f"{split}/{identifier}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    values = np.asarray(image, dtype=float)
    if split == "development":
        values = ndimage.rotate(values, 19.0, reshape=False, order=1, mode="reflect")
        values = ndimage.gaussian_filter(values, .55, mode="reflect")
        values = _gamma(values, 1.18)
        values = _shot_noise(values, 120.0, rng)
    else:
        values = ndimage.rotate(values, 61.0, reshape=False, order=1, mode="reflect")
        values = ndimage.gaussian_filter(values, sigma=(.8, 1.6), mode="reflect")
        values = _center_crop_or_pad(ndimage.zoom(values, (.72, 1.18), order=1, mode="reflect"), (128, 128))
        values = ndimage.shift(values, (7.0, -9.0), order=1, mode="reflect")
        values = _gamma(values, .65)
        values = _illumination(values, .35, .8)
        values = _shot_noise(values, 45.0, rng)
    return _standardize(values)


def _join(blocks: dict[str, np.ndarray]) -> np.ndarray:
    return np.concatenate([blocks[name] for name in sorted(blocks)])


def _features(image: np.ndarray) -> dict[str, np.ndarray]:
    geometry = analyze_response_geometry(image, spacing_um=(1, 1), mask=None,
                                         scales_um=(2, 4, 8, 16), separations_um=(1, 2, 4, 8, 16, 24))
    blocks: dict[str, list[np.ndarray]] = {}
    collapsed = []
    for name, values in _ordered_responses(geometry):
        blocks.setdefault(name.split(".", 1)[0], []).append(values)
        collapsed.extend((float(values.mean()), float(values.std()), float(values.min()), float(values.max())))
    raw = {name: np.concatenate(values) for name, values in blocks.items()}
    return {"conventional": conventional_vector(image, None),
            "collapsed": np.asarray(collapsed),
            "raw": _join(raw),
            "canonical": _join(canonical_response_blocks(geometry))}


def _orbit_blocks(image: np.ndarray) -> dict[str, np.ndarray]:
    orbit = []
    for angle in (0.0, 45.0, 90.0, 135.0):
        rotated = ndimage.rotate(image, angle, reshape=False, order=1, mode="reflect")
        geometry = analyze_response_geometry(rotated, spacing_um=(1, 1), mask=None,
                                             scales_um=(2, 4, 8, 16), separations_um=(1, 2, 4, 8, 16, 24))
        orbit.append(canonical_response_blocks(geometry))
    return {module: np.mean([row[module] for row in orbit], axis=0) for module in orbit[0]}


def _scale_fit(reference: np.ndarray, query: np.ndarray) -> dict:
    envelope = np.vstack([reference, query])
    location = envelope.mean(axis=0)
    scale = envelope.std(axis=0, ddof=1)
    scale[scale <= np.finfo(float).eps] = 1.0
    return {"location": location.tolist(), "scale": scale.tolist()}


def _scale_apply(values: np.ndarray, model: dict) -> np.ndarray:
    return (values - np.asarray(model["location"])) / np.asarray(model["scale"])


def _retrieve(reference: np.ndarray, query: np.ndarray, domains: np.ndarray, metric: str = "euclidean") -> dict:
    ranks = np.empty(len(reference), dtype=int)
    for index in range(len(reference)):
        candidates = np.flatnonzero(domains == domains[index])
        if metric == "cosine":
            numerator = reference[candidates] @ query[index]
            denominator = np.linalg.norm(reference[candidates], axis=1) * max(np.linalg.norm(query[index]), np.finfo(float).eps)
            distances = 1 - numerator / np.maximum(denominator, np.finfo(float).eps)
        else:
            distances = np.linalg.norm(reference[candidates] - query[index], axis=1)
        order = candidates[np.argsort(distances, kind="stable")]
        ranks[index] = int(np.flatnonzero(order == index)[0]) + 1
    per_domain = {str(domain): float(np.mean(ranks[domains == domain] == 1)) for domain in np.unique(domains)}
    return {"top1_macro": float(np.mean(list(per_domain.values()))), "top1_by_domain": per_domain,
            "mean_reciprocal_rank": float(np.mean(1 / ranks)), "median_rank": float(np.median(ranks)),
            "ranks": ranks.tolist()}


def run_development(cases: list[dict], output: Path) -> dict:
    selected = [row for row in cases if row["split"] == "development"]
    reference_features = [_features(row["image"]) for row in selected]
    query_features = [_features(_perturb(row["image"], row["identifier"], "development")) for row in selected]
    domains = np.asarray([row["domain"] for row in selected])
    models, results = {}, {}
    for name in REPRESENTATIONS:
        reference = np.stack([row[name] for row in reference_features]); query = np.stack([row[name] for row in query_features])
        model = _scale_fit(reference, query); models[name] = model
        scaled_reference, scaled_query = _scale_apply(reference, model), _scale_apply(query, model)
        results[name] = _retrieve(scaled_reference, scaled_query, domains)
        results[f"{name}_cosine"] = _retrieve(scaled_reference, scaled_query, domains, metric="cosine")
    canonical_reference = np.stack([row["canonical"] for row in reference_features])
    canonical_query = np.stack([row["canonical"] for row in query_features])
    stability = fit_stability_weights(canonical_reference, canonical_query)
    results["stability_weighted_canonical"] = _retrieve(apply_stability_weights(canonical_reference, stability),
                                                          apply_stability_weights(canonical_query, stability), domains)
    results["stability_weighted_canonical_cosine"] = _retrieve(apply_stability_weights(canonical_reference, stability),
                                                                 apply_stability_weights(canonical_query, stability), domains,
                                                                 metric="cosine")
    payload = {"protocol_version": "nostos-biological-retrieval-development/1.0", "status": "development_only",
               "design": "Four biological domains; 15 hash-selected development identities per domain; train-free same-specimen retrieval under a mild acquisition shift.",
               "cases": [{key: row[key] for key in ("domain", "identifier", "split")} for row in selected],
               "results": results, "scalers": models, "stability_model": stability.to_dict()}
    output.mkdir(parents=True, exist_ok=True)
    (output / "biological_retrieval_development.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _bootstrap(ranks: np.ndarray, domains: np.ndarray, comparator_ranks: np.ndarray | None = None) -> list[float]:
    rng = np.random.default_rng(8262601)
    groups = [np.flatnonzero(domains == domain) for domain in np.unique(domains)]
    values = np.empty(10000)
    first = ranks == 1
    second = None if comparator_ranks is None else comparator_ranks == 1
    for draw in range(len(values)):
        estimates = []
        for group in groups:
            selected = group[rng.integers(0, len(group), len(group))]
            estimate = np.mean(first[selected])
            if second is not None:
                estimate -= np.mean(second[selected])
            estimates.append(estimate)
        values[draw] = np.mean(estimates)
    return [float(value) for value in np.quantile(values, (.025, .975))]


def run_confirmation(cases: list[dict], development_receipt: Path, output: Path) -> dict:
    development = json.loads(development_receipt.read_text(encoding="utf-8"))
    selected = [row for row in cases if row["split"] == "confirmation"]
    reference_features = [_features(row["image"]) for row in selected]
    query_features = [_features(_perturb(row["image"], row["identifier"], "confirmation")) for row in selected]
    domains = np.asarray([row["domain"] for row in selected])
    results = {}
    for name in REPRESENTATIONS:
        reference = np.stack([row[name] for row in reference_features]); query = np.stack([row[name] for row in query_features])
        model = development["scalers"][name]
        scaled_reference, scaled_query = _scale_apply(reference, model), _scale_apply(query, model)
        results[name] = _retrieve(scaled_reference, scaled_query, domains)
        results[f"{name}_cosine"] = _retrieve(scaled_reference, scaled_query, domains, metric="cosine")
    stability = StabilityWeightModel(**development["stability_model"])
    canonical_reference = np.stack([row["canonical"] for row in reference_features])
    canonical_query = np.stack([row["canonical"] for row in query_features])
    weighted_reference = apply_stability_weights(canonical_reference, stability)
    weighted_query = apply_stability_weights(canonical_query, stability)
    primary = _retrieve(weighted_reference, weighted_query, domains)
    results["stability_weighted_canonical"] = primary
    module_slices = {"hessian": (0, 12), "spatial": (12, 24), "spectral": (24, 27), "tensor": (27, 39)}
    ablations = {}
    for module, (start, stop) in module_slices.items():
        keep = np.r_[0:start, stop:weighted_reference.shape[1]]
        ablations[f"without_{module}"] = _retrieve(weighted_reference[:, keep], weighted_query[:, keep], domains)
    primary_ranks = np.asarray(primary["ranks"])
    intervals = {"primary_top1_macro": _bootstrap(primary_ranks, domains)}
    for comparator in ("conventional_cosine", "collapsed_cosine", "raw_cosine"):
        intervals[f"primary_minus_{comparator}"] = _bootstrap(primary_ranks, domains, np.asarray(results[comparator]["ranks"]))
    domain_passes = sum(value >= .25 for value in primary["top1_by_domain"].values())
    gates = {"exactly_60_cases_15_per_domain": len(selected) == 60 and all(np.sum(domains == domain) == 15 for domain in DOMAINS),
             "effective_coordinates_ge_15": stability.effective_coordinates >= 15,
             "top1_macro_ge_0_35": primary["top1_macro"] >= .35,
             "top1_bootstrap_lower_ge_0_20": intervals["primary_top1_macro"][0] >= .20,
             "mean_reciprocal_rank_ge_0_55": primary["mean_reciprocal_rank"] >= .55,
             "at_least_three_domains_top1_ge_0_25": domain_passes >= 3,
             "noninferior_to_conventional_cosine_margin_0_05": intervals["primary_minus_conventional_cosine"][0] > -.05,
             "noninferior_to_collapsed_cosine_margin_0_05": intervals["primary_minus_collapsed_cosine"][0] > -.05,
             "noninferior_to_raw_cosine_margin_0_05": intervals["primary_minus_raw_cosine"][0] > -.05}
    payload = {"protocol_version": "nostos-biological-retrieval-confirmation/1.0",
               "protocol_sha256": PROTOCOL_SHA256,
               "development_receipt_sha256": hashlib.sha256(development_receipt.read_bytes()).hexdigest(),
               "status": "pass" if all(gates.values()) else "fail",
               "design": "Train-free same-specimen retrieval in four biological domains under a disjoint compound acquisition shift.",
               "primary": primary, "comparators": results, "ablations": ablations,
               "bootstrap95": intervals, "success_gates": gates,
               "scope": "Shared label-free comparison geometry for controlled same-specimen retrieval; not phenotype, scanner or clinical validation.",
               "cases": [{key: row[key] for key in ("domain", "identifier", "split")} for row in selected]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "biological_retrieval_confirmation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def run_orbit_redesign_development(cases: list[dict], output: Path) -> dict:
    """Post-failure development only; confirmation cases are explicitly opened."""
    selected = [row for row in cases if row["split"] == "confirmation"]
    references = [_orbit_blocks(row["image"]) for row in selected]
    queries = [_orbit_blocks(_perturb(row["image"], row["identifier"], "confirmation")) for row in selected]
    domains = np.asarray([row["domain"] for row in selected])
    results = {}
    for omitted in (None, "tensor", "spatial", "spectral", "hessian"):
        name = "orbit_canonical" if omitted is None else f"orbit_without_{omitted}"
        reference = np.stack([_join({key: value for key, value in row.items() if key != omitted}) for row in references])
        query = np.stack([_join({key: value for key, value in row.items() if key != omitted}) for row in queries])
        model = _scale_fit(reference, query)
        scaled_reference, scaled_query = _scale_apply(reference, model), _scale_apply(query, model)
        results[name] = _retrieve(scaled_reference, scaled_query, domains)
        stability = fit_stability_weights(reference, query)
        results[f"{name}_stability"] = _retrieve(apply_stability_weights(reference, stability),
                                                   apply_stability_weights(query, stability), domains)
    payload = {"protocol_version": "nostos-orbit-redesign-development/1.0", "status": "development_only",
               "design": "Post-failure orbit-averaged canonical geometry on the opened 60-case confirmation cohort; optimistic and not confirmatory.",
               "results": results}
    output.mkdir(parents=True, exist_ok=True)
    (output / "orbit_redesign_development.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
