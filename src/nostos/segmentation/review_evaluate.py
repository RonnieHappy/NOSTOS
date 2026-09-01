"""Evaluate a blinded cartilage proposal against independent reviewed masks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

from nostos.features.spatial_fft import extract_spatial_fft


PROTOCOL = "nostos-cartilage-mask-review-evaluation/1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _binary(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        values = np.asarray(opened.convert("L"))
    return values > 0


def _verify_review_audit(audit_path: Path, *, case_id: str, reference_path: Path, row: object) -> dict:
    if not audit_path.is_file():
        raise ValueError(f"Missing signed review audit for {case_id}: {audit_path}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    expected = {
        "case_id": case_id,
        "source_sha256": row.prepared_image_sha256,
        "proposal_sha256": row.proposal_sha256,
        "reference_mask_sha256": _sha256(reference_path),
    }
    for key, value in expected.items():
        if audit.get(key) != value:
            raise ValueError(f"Review audit {key} mismatch for {case_id}")
    if audit.get("completed_review") is not True or not str(audit.get("reviewer_id", "")).strip() or not str(audit.get("completed_utc", "")).strip():
        raise ValueError(f"Incomplete reviewer attestation for {case_id}")
    return audit


def _surface(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return np.zeros_like(mask)
    return mask ^ ndimage.binary_erosion(mask)


def _surface_distances(a: np.ndarray, b: np.ndarray, spacing_um: float) -> np.ndarray:
    sa, sb = _surface(a), _surface(b)
    if not sa.any() or not sb.any():
        return np.asarray([np.inf])
    da = ndimage.distance_transform_edt(~sa, sampling=spacing_um)
    db = ndimage.distance_transform_edt(~sb, sampling=spacing_um)
    return np.concatenate((db[sa], da[sb])).astype(float)


def _column_boundaries(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = mask.any(axis=0)
    top = np.full(mask.shape[1], np.nan)
    bottom = np.full(mask.shape[1], np.nan)
    if valid.any():
        top[valid] = np.argmax(mask[:, valid], axis=0)
        bottom[valid] = mask.shape[0] - 1 - np.argmax(mask[::-1, valid], axis=0)
    return valid, top, bottom


def _boundary_errors(a: np.ndarray, b: np.ndarray, spacing_um: float) -> tuple[float, float, float]:
    va, ta, ba = _column_boundaries(a)
    vb, tb, bb = _column_boundaries(b)
    common = va & vb
    if not common.any():
        return float("inf"), float("inf"), 0.0
    return (
        float(np.median(np.abs(ta[common] - tb[common])) * spacing_um),
        float(np.median(np.abs(ba[common] - bb[common])) * spacing_um),
        float(common.mean()),
    )


def _tiles(mask: np.ndarray, tile_px: int, coverage: float) -> np.ndarray:
    ny, nx = mask.shape[0] // tile_px, mask.shape[1] // tile_px
    result = np.zeros((ny, nx), dtype=bool)
    for iy in range(ny):
        for ix in range(nx):
            tile = mask[iy * tile_px:(iy + 1) * tile_px, ix * tile_px:(ix + 1) * tile_px]
            result[iy, ix] = float(tile.mean()) >= coverage
    return result


def _tile_entropy(image: np.ndarray, mask: np.ndarray, tile_px: int, coverage: float, spacing_um: float) -> list[float]:
    selected = _tiles(mask, tile_px, coverage)
    values: list[float] = []
    for iy, ix in np.argwhere(selected):
        tile = image[iy * tile_px:(iy + 1) * tile_px, ix * tile_px:(ix + 1) * tile_px]
        if min(tile.shape) < 32 or np.ptp(tile) == 0:
            continue
        try:
            values.append(float(extract_spatial_fft(tile, pixel_size_um=spacing_um).angular_entropy))
        except ValueError:
            continue
    return values


def evaluate_case(image: np.ndarray, proposal: np.ndarray, reference: np.ndarray, *, spacing_um: float,
                  tile_size_um: float = 250.0, tile_coverage: float = 0.50) -> dict[str, float | int]:
    if proposal.shape != reference.shape or image.shape[:2] != reference.shape:
        raise ValueError("Image, proposal and reference shapes must match.")
    intersection = int(np.logical_and(proposal, reference).sum())
    union = int(np.logical_or(proposal, reference).sum())
    denominator = int(proposal.sum() + reference.sum())
    dice = 2 * intersection / denominator if denominator else 1.0
    iou = intersection / union if union else 1.0
    distances = _surface_distances(proposal, reference, spacing_um)
    surface_error, tidemark_error, comparable_columns = _boundary_errors(proposal, reference, spacing_um)
    tile_px = max(32, int(round(tile_size_um / spacing_um)))
    proposal_tiles = _tiles(proposal, tile_px, tile_coverage)
    reference_tiles = _tiles(reference, tile_px, tile_coverage)
    tile_union = int(np.logical_or(proposal_tiles, reference_tiles).sum())
    tile_intersection = int(np.logical_and(proposal_tiles, reference_tiles).sum())
    tile_agreement = float((proposal_tiles == reference_tiles).mean()) if proposal_tiles.size else float("nan")
    tile_iou = tile_intersection / tile_union if tile_union else 1.0
    grayscale = np.asarray(Image.fromarray(image).convert("L"), dtype=float)
    proposal_entropy = _tile_entropy(grayscale, proposal, tile_px, tile_coverage, spacing_um)
    reference_entropy = _tile_entropy(grayscale, reference, tile_px, tile_coverage, spacing_um)
    return {
        "dice": float(dice), "iou": float(iou),
        "surface_hd95_um": float(np.percentile(distances, 95)),
        "surface_mean_distance_um": float(np.mean(distances)),
        "articular_surface_median_error_um": surface_error,
        "tidemark_median_error_um": tidemark_error,
        "comparable_column_fraction": comparable_columns,
        "tile_agreement": tile_agreement, "tile_iou": float(tile_iou),
        "proposal_tile_count": int(proposal_tiles.sum()), "reference_tile_count": int(reference_tiles.sum()),
        "proposal_median_angular_entropy": float(np.median(proposal_entropy)) if proposal_entropy else float("nan"),
        "reference_median_angular_entropy": float(np.median(reference_entropy)) if reference_entropy else float("nan"),
        "angular_entropy_absolute_difference": float(abs(np.median(proposal_entropy) - np.median(reference_entropy))) if proposal_entropy and reference_entropy else float("nan"),
    }


def evaluate_review_packet(packet: Path, output: Path) -> dict:
    review = pd.read_csv(packet / "review_manifest.csv", dtype=str).fillna("")
    crosswalk = pd.read_csv(packet / "case_crosswalk.csv", dtype={"participant_id": str})
    merged = review.merge(crosswalk, on="case_id", validate="one_to_one")
    required = {"case_id", "review_status", "artifact_burden", "prepared_image", "proposal_mask", "pixel_size_um"}
    missing = required - set(merged.columns)
    if missing:
        raise ValueError(f"Missing review fields: {sorted(missing)}")
    rows: list[dict] = []
    incomplete: list[str] = []
    for row in merged.itertuples(index=False):
        case_id = str(row.case_id)
        if str(row.review_status).lower() not in {"complete", "adjudicated"}:
            incomplete.append(case_id); continue
        adjudicated = bool(getattr(row, "adjudicated_mask", ""))
        reference_rel = getattr(row, "adjudicated_mask", "") or getattr(row, "reviewed_mask", "")
        audit_rel = getattr(row, "adjudication_audit", "") if adjudicated else getattr(row, "review_audit", "")
        reference_path = packet / reference_rel
        if not reference_path.is_file():
            incomplete.append(case_id); continue
        image_path, proposal_path = Path(row.prepared_image), Path(row.proposal_mask)
        if _sha256(image_path) != row.prepared_image_sha256 or _sha256(proposal_path) != row.proposal_sha256:
            raise ValueError(f"Source hash mismatch for {case_id}")
        audit = _verify_review_audit(packet / audit_rel, case_id=case_id, reference_path=reference_path, row=row)
        with Image.open(image_path) as opened:
            image = np.asarray(opened.convert("RGB"))
        proposal_values = np.asarray(Image.open(proposal_path).convert("L"))
        proposal = proposal_values == 1 if np.any(proposal_values == 1) else proposal_values > 0
        reference = _binary(reference_path)
        metrics = evaluate_case(image, proposal, reference, spacing_um=float(row.pixel_size_um))
        rows.append({
            "case_id": case_id, "participant_id": str(row.participant_id).zfill(3),
            "stain": row.stain, "site": row.site, "artifact_burden": row.artifact_burden,
            "reference_mask_sha256": _sha256(reference_path), **metrics,
            "reviewer_id": audit["reviewer_id"], "adjudicated": adjudicated,
        })
    if incomplete:
        raise ValueError(f"Review packet is incomplete for {len(incomplete)} cases: {incomplete[:8]}")
    frame = pd.DataFrame(rows).sort_values("case_id")
    output.mkdir(parents=True, exist_ok=True)
    metrics_path = output / "case_metrics.csv"
    frame.to_csv(metrics_path, index=False)
    numeric = ["dice", "iou", "surface_hd95_um", "articular_surface_median_error_um", "tidemark_median_error_um", "tile_agreement", "tile_iou", "angular_entropy_absolute_difference"]
    summaries = {name: {metric: float(group[metric].median()) for metric in numeric} for name, group in frame.groupby("stain")}
    valid_fraction = float(np.mean(np.isfinite(frame["surface_hd95_um"])))
    gates = {
        "median_dice_at_least_0_90": float(frame.dice.median()) >= 0.90,
        "median_iou_at_least_0_82": float(frame.iou.median()) >= 0.82,
        "median_hd95_at_most_100_um": float(frame.surface_hd95_um.median()) <= 100.0,
        "valid_fraction_at_least_0_85": valid_fraction >= 0.85,
        "no_stain_median_dice_below_0_85": all(values["dice"] >= 0.85 for values in summaries.values()),
    }
    receipt = {
        "protocol_version": PROTOCOL, "status": "pass" if all(gates.values()) else "fail",
        "case_count": int(len(frame)), "participant_count": int(frame.participant_id.nunique()),
        "statistical_unit": "section with participant-level counts reported separately",
        "gates": gates, "overall_medians": {metric: float(frame[metric].median()) for metric in numeric},
        "stratified_by_stain": summaries,
        "metrics_sha256": _sha256(metrics_path),
        "claim_boundary": "A pass validates the frozen cartilage proposal against supplied human reference masks; it does not validate pathology outcomes or clinical use.",
    }
    (output / "review_evaluation_receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a completed blinded cartilage-mask review packet.")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_review_packet(args.packet.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
